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
}
_KEYWORDS_OBVIAS_PESQUISA = {
    "o que e", "o que é", "explica", "me explica", "me fala sobre",
    "como funciona", "quero entender", "diferenca entre", "diferença entre",
    "significado", "conceito",
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


def _classificar_localmente(texto: str) -> Optional[ModoOperacao]:
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

    # Saudação: só para mensagens curtas (≤4 palavras) com keyword óbvia
    if num_palavras <= 4:
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
    # → quase sempre é um nome ou saudação informal — tratar como SAUDACAO
    # sem chamar LLM (economiza custo + latência)
    if num_palavras == 1 and len(texto) <= 15:
        logger.info(f"[ROUTER] Mensagem muito curta/nome-like → SAUDACAO local: '{texto}'")
        return ModoOperacao.SAUDACAO

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

    prompt_sistema = (
        "Você é um roteador de intenções para um assistente de terapeutas da Escola de Alquimia do Joel Aleixo."
        + nome_contexto
        + "\n\nClassifique a mensagem do terapeuta em UMA das categorias:\n"
        "- CONSULTA_CASO: terapeuta quer ajuda com um paciente específico (anamnese, diagnóstico, protocolo)\n"
        "- PESQUISA_METODO: quer entender conceitos, técnicas ou ensinamentos do método do Joel\n"
        "- CRIACAO_CONTEUDO: quer criar post, texto, vídeo, story ou material para redes sociais\n"
        "- SAUDACAO: cumprimento simples, início de conversa, sem pedido específico\n"
        "- EMERGENCIA: menciona risco de vida, suicídio, crise severa\n"
        "- FORA_ESCOPO: completamente fora da Escola de Alquimia\n\n"
        "Responda APENAS com a categoria, sem explicação."
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

    Returns:
        ModoOperacao correspondente à intenção detectada.
    """
    if not texto or not texto.strip():
        logger.info("[ROUTER] Texto vazio — retornando SAUDACAO")
        return ModoOperacao.SAUDACAO

    # Etapa 1: tentar classificação local (sem LLM)
    modo_local = _classificar_localmente(texto)
    if modo_local is not None:
        logger.info(f"[ROUTER] Classificação local: {modo_local.value} para '{texto[:50]}'")
        return modo_local

    # Etapa 2: mensagem ambígua — chamar Haiku
    logger.info(f"[ROUTER] Mensagem ambígua, consultando Haiku: '{texto[:50]}'")
    modo_haiku = await _classificar_com_haiku(texto, historico, nome_usuario)
    return modo_haiku
