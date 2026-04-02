"""
Agente Roteador — usa Claude Haiku para classificar intenção com precisão.
Substitui a detecção por keywords quando a mensagem é ambígua.
Haiku é 10x mais rápido e 5x mais barato que Sonnet — ideal para roteamento.

Estratégia de dois caminhos:
- Mensagens ÓBVIAS (curtas + keyword clara): classifica localmente, sem LLM — <10ms
- Mensagens AMBÍGUAS (>20 chars sem keyword clara): chama Haiku — <1500ms
"""

import logging
from typing import Optional

import anthropic

from src.core.config import get_settings
from src.core.prompts import ModoOperacao, detectar_modo, PALAVRAS_MODO

logger = logging.getLogger(__name__)

# Modelo Haiku para roteamento — rápido e barato
_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Singleton do cliente Anthropic para o roteador
_router_client: Optional[anthropic.AsyncAnthropic] = None

# Limiar de caracteres acima do qual a mensagem é considerada "ambígua"
# e merece classificação por LLM em vez de keywords simples
_LIMIAR_AMBIGUIDADE = 20

# Palavras-chave consideradas "claras" — se a mensagem as contém,
# a detecção local é suficiente (sem precisar do Haiku)
_KEYWORDS_OBVIAS_CONSULTA = {
    "paciente", "caso", "anamnese", "diagnostico", "diagnóstico",
    "meu paciente", "minha paciente", "protocolo para", "floral para",
    "queixa", "sintoma", "atendi", "atendendo",
    # Expansão: termos clínicos adicionais
    "cliente", "atendimento", "sessão", "sessao", "consulta",
    "histórico", "historico", "trauma", "bloqueio", "padrão", "padrao",
    "família", "familia", "relacionamento", "ansiedade", "depressão", "depressao",
    "dificuldade", "problema", "quero trazer", "vou trazer", "trouxe um",
    "situação", "situacao", "moça", "moca", "rapaz", "pessoa que",
    "ela não consegue", "ele não consegue", "está passando", "tá passando",
    # Mapa astral / natal — parte do método alquímico nível 5
    "mapa astral", "mapa natal", "calcular mapa", "calcula mapa",
    "mapa astrológico", "mapa astrologico", "gerar mapa", "gera mapa",
    "fazer mapa", "faz mapa",
    # Dados de nascimento standalone — sinalizam pedido de mapa ou caso clínico
    "data de nascimento", "hora de nascimento", "local de nascimento",
    "nasceu em", "nascida em", "nascido em",
}
_KEYWORDS_OBVIAS_PESQUISA = {
    "o que e", "o que é", "explica", "me explica", "me fala sobre",
    "como funciona", "quero entender", "diferenca entre", "diferença entre",
    "significado", "conceito",
    # Expansão: termos metodológicos e formas de pesquisa
    "método", "metodo", "alquimia", "alquímico", "joel", "aleixo",
    "técnica", "tecnica", "ferramenta", "abordagem", "terapia",
    "o que é", "como se aplica", "me conta sobre", "fala sobre",
}
_KEYWORDS_OBVIAS_CONTEUDO = {
    "criar post", "cria post", "criar conteudo", "cria conteúdo",
    "instagram", "legenda", "stories", "carrossel", "reels",
    "post sobre", "escrever", "escreve",
}
_KEYWORDS_OBVIAS_SAUDACAO = {
    "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
    "hey", "eae", "tudo bem", "hello", "hi",
}
_KEYWORDS_EMERGENCIA = {
    "suicidio", "suicídio", "suicida", "se matar", "risco de vida",
    "tentativa de suicidio", "ideacao suicida", "ideação suicida",
    "autolesao", "automutilação",
}


def _get_router_client() -> anthropic.AsyncAnthropic:
    """Retorna instância singleton do cliente Anthropic para o roteador."""
    global _router_client
    if _router_client is None:
        settings = get_settings()
        _router_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _router_client


def _historico_tem_caso_ativo(historico: list[dict]) -> bool:
    """
    Verifica se o histórico recente indica um caso clínico em andamento.
    Retorna True se a última mensagem do agente contém sinais de diagnóstico
    ativo (pergunta clínica, análise em andamento, pedido de informação do caso).

    Isso evita que respostas curtas do terapeuta ("Falante", "sim", "dor nas pernas")
    sejam classificadas como SAUDACAO quando são continuação de um caso.
    """
    if not historico:
        return False

    # Procura a última mensagem do agente (assistant) no histórico
    ultima_agente = ""
    for msg in reversed(historico):
        role = msg.get("role", "")
        if role in ("agente", "assistant"):
            ultima_agente = (msg.get("content", "") or msg.get("conteudo", "") or msg.get("mensagem", "") or "").lower()
            break

    if not ultima_agente:
        return False

    # Sinais de que o agente fez uma pergunta clínica ou está no meio de uma análise
    _SINAIS_CASO_ATIVO = [
        # Perguntas clínicas diretas
        "?",
        # Termos que indicam análise em andamento
        "paciente", "caso", "diagnóstico", "diagnostico", "mapa",
        "elemento", "camada", "floral", "serpente", "substância", "substancia",
        "terra", "fogo", "água", "agua", "enxofre", "mercúrio", "mercurio",
        # Perguntas sobre observação clínica
        "agitado", "falante", "calado", "fechado", "pesado",
        "tipo", "comportamento", "observou", "percebeu", "notou",
        "como ele", "como ela", "quando você", "quando voce",
        # Continuação de análise
        "me conta", "me diz", "me fala", "descreve", "detalha",
        "preciso saber", "importante saber", "ajuda a entender",
    ]

    return any(sinal in ultima_agente for sinal in _SINAIS_CASO_ATIVO)


def _classificar_localmente(texto: str, is_audio: bool = False, historico: list[dict] | None = None) -> Optional[ModoOperacao]:
    """
    Tenta classificar a mensagem localmente por keywords conhecidas.
    Retorna None se a mensagem for ambígua e precisar do Haiku.

    Prioridade: EMERGENCIA > CONSULTA > CRIACAO_CONTEUDO > PESQUISA > SAUDACAO
    """
    texto_lower = texto.lower().strip()
    palavras = texto_lower.split()
    num_palavras = len(palavras)

    # Emergência: prioridade máxima, sempre local (urgente)
    for kw in _KEYWORDS_EMERGENCIA:
        if kw in texto_lower:
            logger.warning(f"[ROUTER] EMERGENCIA detectada localmente: '{texto[:60]}'")
            return ModoOperacao.EMERGENCIA

    # Pedido de imagem/gráfico de mapa astral → CONSULTA
    # O webhook vai re-usar dados do histórico para gerar e reenviar a imagem
    _PALAVRAS_IMG = {"imagem", "gráfico", "grafico", "foto", "figura", "gerar imagem", "me gere"}
    _PALAVRAS_MAPA_CTX = {"mapa", "astral", "natal"}
    if (any(p in texto_lower for p in _PALAVRAS_IMG)
            and any(p in texto_lower for p in _PALAVRAS_MAPA_CTX)):
        logger.info(f"[ROUTER] Pedido de imagem de mapa → CONSULTA: '{texto[:60]}'")
        return ModoOperacao.CONSULTA

    # Mensagens meta sobre áudio/mídia: nunca são saudação — o usuário está reportando
    # algo sobre o fluxo ("mandei um áudio", "não consegui enviar", etc.)
    # Tratar como PESQUISA para não repetir o loop de saudação
    _PALAVRAS_META_AUDIO = {"áudio", "audio", "mandei", "gravei", "gravando"}
    if num_palavras <= 6 and sum(1 for p in _PALAVRAS_META_AUDIO if p in texto_lower) >= 2:
        logger.info(f"[ROUTER] Meta-mensagem sobre áudio → PESQUISA local: '{texto[:60]}'")
        return ModoOperacao.PESQUISA

    # Áudio: nunca classifica como SAUDACAO — transcrições sempre têm conteúdo intencional
    if is_audio:
        # Mantém apenas emergência (já tratada acima) e continua para outros modos
        pass

    # Saudação: só para mensagens curtas (≤4 palavras) com keyword óbvia — e nunca para áudio
    # REGRA CRÍTICA: se há caso ativo no histórico, NÃO classificar como SAUDACAO
    # mesmo que a mensagem pareça uma saudação ("oi", "tudo bem") — pode ser
    # continuação natural da conversa
    if not is_audio and num_palavras <= 4:
        for kw in _KEYWORDS_OBVIAS_SAUDACAO:
            if kw in texto_lower:
                # Garantir que não há keywords de outros modos na mesma mensagem
                tem_outro = any(
                    kw2 in texto_lower
                    for grupo in [
                        _KEYWORDS_OBVIAS_CONSULTA,
                        _KEYWORDS_OBVIAS_PESQUISA,
                        _KEYWORDS_OBVIAS_CONTEUDO,
                    ]
                    for kw2 in grupo
                )
                if not tem_outro:
                    # Se há caso ativo, redirecionar para CONSULTA em vez de SAUDACAO
                    if _historico_tem_caso_ativo(historico or []):
                        logger.info(f"[ROUTER] Mensagem parece SAUDACAO mas há caso ativo → CONSULTA: '{texto[:60]}'")
                        return ModoOperacao.CONSULTA
                    logger.info(f"[ROUTER] SAUDACAO detectada localmente: '{texto[:60]}'")
                    return ModoOperacao.SAUDACAO

    # Para mensagens longas, keywords menos confiáveis — deixar para Haiku
    if len(texto) > _LIMIAR_AMBIGUIDADE:
        # Mas se a keyword é muito forte e inequívoca, ainda classifica local
        # CONSULTA: keywords de caso clínico são muito específicas
        for kw in _KEYWORDS_OBVIAS_CONSULTA:
            if kw in texto_lower:
                logger.info(f"[ROUTER] CONSULTA detectada localmente (keyword forte): '{texto[:60]}'")
                return ModoOperacao.CONSULTA

        # CRIACAO_CONTEUDO: keywords de canais/formatos são muito específicas
        for kw in _KEYWORDS_OBVIAS_CONTEUDO:
            if kw in texto_lower:
                logger.info(f"[ROUTER] CRIACAO_CONTEUDO detectada localmente (keyword forte): '{texto[:60]}'")
                return ModoOperacao.CRIACAO_CONTEUDO

        # Mensagem ambígua longa: deixar para Haiku
        return None

    # Mensagem curta sem saudação: tentar outros modos
    for kw in _KEYWORDS_OBVIAS_CONSULTA:
        if kw in texto_lower:
            return ModoOperacao.CONSULTA

    for kw in _KEYWORDS_OBVIAS_CONTEUDO:
        if kw in texto_lower:
            return ModoOperacao.CRIACAO_CONTEUDO

    for kw in _KEYWORDS_OBVIAS_PESQUISA:
        if kw in texto_lower:
            return ModoOperacao.PESQUISA

    # Mensagem curta sem keyword clara: também deixar para Haiku se tiver >3 palavras
    if num_palavras > 3:
        return None

    # Mensagem muito curta (1 palavra ≤15 chars) sem keyword reconhecível
    # REGRA CRÍTICA: se há caso ativo no histórico, a palavra curta é quase
    # certamente uma RESPOSTA à pergunta do agente (ex: "Falante", "sim",
    # "calado", "dor") — deve ir para CONSULTA, NÃO para SAUDACAO.
    # Exceção: áudio nunca é SAUDACAO, mesmo se transcrição for curta
    if not is_audio and num_palavras == 1 and len(texto) <= 15:
        if _historico_tem_caso_ativo(historico or []):
            logger.info(f"[ROUTER] Mensagem curta com caso ativo → CONSULTA: '{texto}'")
            return ModoOperacao.CONSULTA
        logger.info(f"[ROUTER] Mensagem muito curta/nome-like → SAUDACAO local: '{texto}'")
        return ModoOperacao.SAUDACAO

    # Mensagem de 2-3 palavras sem keywords mas com caso ativo → CONSULTA
    if num_palavras <= 3 and _historico_tem_caso_ativo(historico or []):
        logger.info(f"[ROUTER] Mensagem curta ({num_palavras} palavras) com caso ativo → CONSULTA: '{texto[:60]}'")
        return ModoOperacao.CONSULTA

    return None


def _mapear_categoria_haiku(categoria_raw: str) -> ModoOperacao:
    """
    Mapeia a resposta textual do Haiku para o enum ModoOperacao.
    Tolerante a variações de capitalização e espaços.
    """
    categoria = categoria_raw.strip().upper()

    mapeamento = {
        "CONSULTA_CASO": ModoOperacao.CONSULTA,
        "CONSULTA": ModoOperacao.CONSULTA,
        "PESQUISA_METODO": ModoOperacao.PESQUISA,
        "PESQUISA": ModoOperacao.PESQUISA,
        "CRIACAO_CONTEUDO": ModoOperacao.CRIACAO_CONTEUDO,
        "CRIACAO": ModoOperacao.CRIACAO_CONTEUDO,
        "SAUDACAO": ModoOperacao.SAUDACAO,
        "EMERGENCIA": ModoOperacao.EMERGENCIA,
        "FORA_ESCOPO": ModoOperacao.FORA_ESCOPO,
    }

    modo = mapeamento.get(categoria)
    if modo is None:
        # Tentar correspondência parcial (ex: "CONSULTA_CASO: ..." com explicação)
        for chave, valor in mapeamento.items():
            if categoria.startswith(chave):
                return valor
        logger.warning(f"[ROUTER] Haiku retornou categoria desconhecida: '{categoria_raw}'. Usando PESQUISA.")
        return ModoOperacao.PESQUISA

    return modo


async def _classificar_com_haiku(
    texto: str,
    historico: list[dict],
    nome_usuario: Optional[str],
    is_audio: bool = False,
) -> ModoOperacao:
    """
    Chama Claude Haiku para classificar a intenção da mensagem.
    Inclui até 3 turnos de histórico para contexto.
    Retorna ModoOperacao. Em caso de falha, retorna o resultado de detectar_modo().
    """
    client = _get_router_client()

    # Montar contexto de histórico (máximo 3 turnos = 6 mensagens)
    historico_resumo = ""
    if historico:
        turnos_recentes = historico[-6:]
        linhas = []
        for msg in turnos_recentes:
            role = msg.get("role", "")
            content = msg.get("content", "")[:100]  # Truncar para não inflar o prompt
            if role in ("terapeuta", "user"):
                linhas.append(f"Terapeuta: {content}")
            elif role in ("agente", "assistant"):
                linhas.append(f"Agente: {content}")
        if linhas:
            historico_resumo = "\n\nHistórico recente:\n" + "\n".join(linhas)

    nome_contexto = f" O nome do terapeuta é {nome_usuario}." if nome_usuario else ""

    _aviso_audio = (
        "\n\nIMPORTANTE: Esta mensagem foi transcrita de um áudio. "
        "Nunca classifique como SAUDACAO — sempre trate como conteúdo real."
        if is_audio
        else ""
    )

    prompt_sistema = (
        "Você é um roteador de intenções para um assistente de terapeutas da Escola de Alquimia do Joel Aleixo."
        + nome_contexto
        + "\n\nClassifique a mensagem do terapeuta em UMA das categorias:\n"
        "- CONSULTA_CASO: terapeuta quer ajuda com um paciente, mapa astral/natal, diagnóstico alquímico, protocolo de florais\n"
        "- PESQUISA_METODO: quer entender conceitos, técnicas, elementos, serpentes ou ensinamentos do método do Joel\n"
        "- CRIACAO_CONTEUDO: quer criar post, texto, vídeo, story ou material para redes sociais\n"
        "- SAUDACAO: cumprimento simples, início de conversa, sem pedido específico\n"
        "- EMERGENCIA: menciona risco de vida, suicídio, crise severa\n"
        "- FORA_ESCOPO: APENAS para temas sem nenhuma relação com terapia, alquimia, saúde mental ou conteúdo profissional (ex: receita de bolo, esportes, política)\n\n"
        "REGRA CRÍTICA: em caso de dúvida, prefira CONSULTA_CASO ou PESQUISA_METODO. Use FORA_ESCOPO raramente.\n\n"
        "Exemplos:\n"
        "- \"Tenho uma paciente que não consegue se relacionar\" → CONSULTA_CASO\n"
        "- \"Quero trazer um caso de uma moça com bloqueios\" → CONSULTA_CASO\n"
        "- \"Preciso gerar um mapa astral\" → CONSULTA_CASO\n"
        "- \"Consegue calcular um mapa natal?\" → CONSULTA_CASO\n"
        "- \"Quero um mapa astral\" → CONSULTA_CASO\n"
        "- \"Me faz um mapa\" → CONSULTA_CASO\n"
        "- \"Quero fazer o mapa astrológico de uma paciente\" → CONSULTA_CASO\n"
        "- \"18 de novembro às 14 horas em Araguari MG\" → CONSULTA_CASO\n"
        "- \"O que é o método alquímico?\" → PESQUISA_METODO\n"
        "- \"Me explica sobre trauma ancestral\" → PESQUISA_METODO\n"
        "- \"O que são as serpentes?\" → PESQUISA_METODO\n"
        "- \"Cria um post sobre ansiedade\" → CRIACAO_CONTEUDO\n"
        "- \"Oi tudo bem\" → SAUDACAO\n"
        "- \"Receita de bolo\" → FORA_ESCOPO\n"
        "- \"Quem ganhou o jogo ontem\" → FORA_ESCOPO\n\n"
        "Responda APENAS com a categoria, sem explicação."
        + _aviso_audio
    )

    mensagem_usuario = f"Mensagem: {texto}{historico_resumo}"

    try:
        response = await client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=10,
            temperature=0,
            system=prompt_sistema,
            messages=[{"role": "user", "content": mensagem_usuario}],
        )
        categoria_raw = response.content[0].text.strip() if response.content else ""
        modo = _mapear_categoria_haiku(categoria_raw)
        # Áudio nunca deve ser SAUDACAO — sobrescrever para CONSULTA se necessário
        if is_audio and modo == ModoOperacao.SAUDACAO:
            logger.info(
                f"[ROUTER] Haiku retornou SAUDACAO para áudio — sobrescrevendo para CONSULTA: '{texto[:50]}'"
            )
            modo = ModoOperacao.CONSULTA
        # Caso ativo no histórico: SAUDACAO → CONSULTA (resposta curta à pergunta clínica)
        if modo == ModoOperacao.SAUDACAO and _historico_tem_caso_ativo(historico):
            logger.info(
                f"[ROUTER] Haiku retornou SAUDACAO mas há caso ativo → CONSULTA: '{texto[:50]}'"
            )
            modo = ModoOperacao.CONSULTA
        logger.info(
            f"[ROUTER] Haiku classificou '{texto[:50]}' → {categoria_raw} → {modo.value}"
        )
        return modo

    except anthropic.APIError as e:
        logger.error(f"[ROUTER] Erro na API Haiku: {e}. Caindo para detectar_modo().")
        return detectar_modo(texto)
    except Exception as e:
        logger.error(f"[ROUTER] Falha inesperada no Haiku: {e}. Caindo para detectar_modo().")
        return detectar_modo(texto)


async def rotear_mensagem(
    texto: str,
    historico: list[dict],
    nome_usuario: Optional[str],
    is_audio: bool = False,
    onboarding_just_completed: bool = False,
) -> ModoOperacao:
    """
    Roteia a mensagem para o modo de operação correto.

    Para mensagens ÓBVIAS (saudação curta, keywords claras): classifica localmente
    sem chamar nenhum LLM — tempo de resposta <10ms.

    Para mensagens AMBÍGUAS (>20 chars sem keyword clara): chama Claude Haiku
    com max_tokens=10 — tempo de resposta <1500ms.

    Em caso de falha do Haiku, cai graciosamente para detectar_modo() (keywords).

    Args:
        texto: Texto da mensagem da terapeuta.
        historico: Últimas mensagens da conversa (até 6 turnos).
        nome_usuario: Nome do terapeuta, se disponível.
        is_audio: Se True, a mensagem é transcrição de áudio — nunca classificar como SAUDACAO.
        onboarding_just_completed: Se True, o usuário acabou de completar o onboarding
            (step 13 → 14). Força CONSULTA para que a primeira mensagem real seja
            tratada como caso/pedido, não como saudação.

    Returns:
        ModoOperacao correspondente à intenção detectada.
    """
    if not texto or not texto.strip():
        logger.info("[ROUTER] Texto vazio — retornando SAUDACAO")
        return ModoOperacao.SAUDACAO

    # Se o usuário acabou de completar o onboarding, forçar CONSULTA
    # para que a primeira mensagem (ex: "mapa natal", "caso clínico") seja
    # processada pelo RAG, e não descartada como saudação
    if onboarding_just_completed:
        logger.info(f"[ROUTER] Onboarding recém-concluído — forçando CONSULTA: '{texto[:50]}'")
        return ModoOperacao.CONSULTA

    # Etapa 1: tentar classificação local (sem LLM)
    modo_local = _classificar_localmente(texto, is_audio=is_audio, historico=historico)
    if modo_local is not None:
        logger.info(f"[ROUTER] Classificação local: {modo_local.value} para '{texto[:50]}'")
        return modo_local

    # Etapa 2: mensagem ambígua — chamar Haiku
    logger.info(f"[ROUTER] Mensagem ambígua, consultando Haiku: '{texto[:50]}'")
    modo_haiku = await _classificar_com_haiku(texto, historico, nome_usuario, is_audio=is_audio)
    return modo_haiku
