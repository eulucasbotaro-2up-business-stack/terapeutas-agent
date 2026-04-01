"""
Geracao de respostas com Claude API para o sistema de RAG.

Usa o system prompt especifico da Escola de Alquimia Joel Aleixo,
com contexto organizado por nivel de maturidade diagnostica.
Temperature 0 para eliminar alucinacoes.
Suporta historico de conversa para consultas multi-turno.

Retry com backoff exponencial para erros transientes da API (429, 5xx).
Timeout configuravel para evitar requests pendurados.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional

import anthropic

from src.core.config import get_settings
from src.core.prompts import (
    ModoOperacao,
    montar_prompt,
    extrair_fontes_resposta,
    detectar_modo,
)
from src.core.retry import retry_async
from src.core.ux_rules import verificar_grounding

logger = logging.getLogger(__name__)

# Singleton do cliente Anthropic (inicializado sob demanda)
_anthropic_client: Optional[anthropic.AsyncAnthropic] = None

# Max tokens por modo de operacao
# CONSULTA precisa de mais tokens (anamnese + diagnostico + indicacao terapeutica)
# CRIACAO_CONTEUDO precisa de mais tokens (2 variantes + hashtags + material de aprofundamento)
# PESQUISA pode ser longa quando cruza multiplos materiais
MAX_TOKENS_POR_MODO: dict[ModoOperacao, int] = {
    ModoOperacao.CONSULTA: 6000,
    ModoOperacao.CRIACAO_CONTEUDO: 3072,
    ModoOperacao.PESQUISA: 2048,
    ModoOperacao.SAUDACAO: 256,
    ModoOperacao.FORA_ESCOPO: 256,
    ModoOperacao.EMERGENCIA: 512,
}
MAX_TOKENS_DEFAULT = 1536


# Mantemos IntencaoMensagem e classificar_intencao para retrocompatibilidade
# (usado no webhook.py para logging adicional)
class IntencaoMensagem(str, Enum):
    """Classificacao de intencao da mensagem da terapeuta (legado, usado para logging)."""
    CONSULTA_CASO = "CONSULTA_CASO"
    DUVIDA_MATERIAL = "DUVIDA_MATERIAL"
    PROTOCOLO = "PROTOCOLO"
    ESCALA_NIVEL = "ESCALA_NIVEL"
    EMERGENCIA = "EMERGENCIA"
    SAUDACAO = "SAUDACAO"
    FORA_ESCOPO = "FORA_ESCOPO"
    DUVIDA_GERAL = "DUVIDA_GERAL"
    AGENDAMENTO = "AGENDAMENTO"
    URGENCIA = "URGENCIA"


# Prompt para classificacao de intencao (usa Haiku por ser rapido e barato)
PROMPT_CLASSIFICACAO = """Classifique a intencao da mensagem abaixo em UMA das categorias:

- CONSULTA_CASO: Quer orientacao sobre um caso/paciente especifico
- DUVIDA_MATERIAL: Pergunta sobre conteudo dos materiais da escola
- PROTOCOLO: Quer saber sobre protocolo, floral, composto, aplicacao
- ESCALA_NIVEL: Pergunta sobre em qual nivel do processo o paciente esta
- EMERGENCIA: Paciente em risco, precisa encaminhamento imediato
- SAUDACAO: Saudacao simples (oi, bom dia, ola, etc.)
- FORA_ESCOPO: Assunto nao relacionado a Escola de Alquimia

Responda APENAS com a categoria, sem explicacao.

Mensagem: {mensagem}"""


# Timeout para chamadas a API do Claude (em segundos).
# Evita que requests fiquem pendurados indefinidamente em caso de lentidao.
_API_TIMEOUT_SECONDS = 120.0


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """
    Retorna instancia singleton do cliente Anthropic.

    Configura timeout padrao para todas as requests.
    O cliente e reutilizado em todas as chamadas para evitar
    overhead de criar conexoes HTTP repetidamente.
    """
    global _anthropic_client
    if _anthropic_client is None:
        settings = get_settings()
        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=_API_TIMEOUT_SECONDS,
        )
    return _anthropic_client


def _montar_mensagens_historico(
    historico_mensagens: list[dict] | None,
    pergunta_atual: str,
) -> list[dict]:
    """
    Converte o historico de conversa em formato de mensagens alternadas user/assistant
    para a API do Claude. Isso garante que o Claude VE toda a conversa anterior
    como se fosse uma conversa nativa, nao apenas texto colado no system prompt.

    Regras de formatacao:
    - 'terapeuta' ou 'user' -> role 'user'
    - 'agente' ou 'assistant' -> role 'assistant'
    - Mensagens consecutivas do mesmo role sao concatenadas (API exige alternancia)
    - A pergunta atual e adicionada como ultima mensagem 'user'

    Args:
        historico_mensagens: Lista de mensagens anteriores da conversa.
        pergunta_atual: Pergunta atual da terapeuta.

    Returns:
        Lista de mensagens formatadas para a API do Claude.
    """
    messages: list[dict] = []

    if historico_mensagens:
        for msg in historico_mensagens:
            role_original = msg.get("role", "")
            content = msg.get("content", "").strip()
            if not content:
                continue

            # Mapeia roles para o formato da API do Claude
            if role_original in ("terapeuta", "user"):
                role = "user"
            elif role_original in ("agente", "assistant"):
                role = "assistant"
            else:
                continue

            # Se a ultima mensagem tem o mesmo role, concatena (API exige alternancia)
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n\n" + content
            else:
                messages.append({"role": role, "content": content})

    # Adiciona a pergunta atual como ultima mensagem user
    if messages and messages[-1]["role"] == "user":
        # Se a ultima mensagem ja e user, concatena
        messages[-1]["content"] += "\n\n" + pergunta_atual
    else:
        messages.append({"role": "user", "content": pergunta_atual})

    # Garante que a primeira mensagem e sempre 'user' (exigencia da API)
    if messages and messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "[Inicio da conversa]"})

    return messages


async def gerar_resposta(
    pergunta: str,
    terapeuta_id: str,
    contexto_chunks: list[dict],
    config_terapeuta: dict,
    historico_mensagens: list[dict] | None = None,
    modo_override: ModoOperacao | None = None,
    contexto_personalizado: str | None = None,
    memoria_usuario: str | None = None,
    system_prompt_override: str | None = None,
) -> str:
    """
    Gera resposta do agente usando Claude API com o system prompt da Alquimia.

    Usa temperature=0 para eliminar criatividade/alucinacao.
    Organiza chunks por nivel de maturidade.
    Adiciona fontes ao final da resposta.
    Suporta historico de conversa para consultas multi-turno (anamnese).
    Suporta contexto personalizado de aprendizado continuo.

    Args:
        pergunta: Pergunta da terapeuta.
        terapeuta_id: UUID do terapeuta (para logging).
        contexto_chunks: Lista de chunks relevantes do retriever.
            Cada chunk deve ter: 'conteudo', 'arquivo_fonte'.
        config_terapeuta: Configuracoes do terapeuta (nome_terapeuta, contato, etc.).
        historico_mensagens: Lista de mensagens anteriores da conversa (opcional).
            Formato: [{"role": "terapeuta"|"agente", "content": "..."}]
        modo_override: Se fornecido, forca um modo especifico.
        contexto_personalizado: Texto de contexto personalizado do aprendizado continuo.
            Gerado por aprendizado.formatar_contexto_personalizado().
        system_prompt_override: Se fornecido, usa este system prompt diretamente em
            vez de chamar montar_prompt(). Usado pelos agentes especialistas.

    Returns:
        Texto da resposta gerada pelo Claude, formatada para WhatsApp,
        com fontes citadas no final.
    """
    settings = get_settings()
    client = _get_anthropic_client()

    # Detectar modo para determinar max_tokens
    modo = modo_override or detectar_modo(pergunta)
    max_tokens = MAX_TOKENS_POR_MODO.get(modo, MAX_TOKENS_DEFAULT)

    # Log de chunks recebidos para debug
    if not contexto_chunks:
        logger.warning(
            f"[GENERATOR] Nenhum chunk recebido para terapeuta {terapeuta_id}. "
            f"Pergunta: '{pergunta[:80]}'. O agente respondera sem contexto RAG."
        )
    else:
        logger.info(
            f"[GENERATOR] Recebidos {len(contexto_chunks)} chunks para terapeuta {terapeuta_id}. "
            f"Similaridades: {[round(c.get('similaridade', 0), 3) for c in contexto_chunks[:5]]}"
        )
        # Log dos primeiros 200 chars de cada chunk para debug de contexto RAG
        for i, chunk in enumerate(contexto_chunks[:5]):
            conteudo_preview = chunk.get("conteudo", "")[:200].replace("\n", " ")
            logger.info(
                f"[GENERATOR] Chunk {i+1}/{len(contexto_chunks)} "
                f"(sim={chunk.get('similaridade', 0):.3f}, "
                f"fonte={chunk.get('arquivo_fonte', 'N/A')}): "
                f"{conteudo_preview}..."
            )

    # Monta o system prompt: usa override de agente especialista se fornecido,
    # caso contrario usa o prompt generico da Alquimia via montar_prompt()
    if system_prompt_override:
        system_prompt = system_prompt_override
        logger.info(
            f"[GENERATOR] Usando system_prompt_override (agente especialista) "
            f"para terapeuta {terapeuta_id} | Modo: {modo.value}"
        )
    else:
        system_prompt = montar_prompt(
            terapeuta=config_terapeuta,
            contexto_chunks=contexto_chunks,
            mensagem=pergunta,
            modo_override=modo_override,
            historico_mensagens=historico_mensagens,
            contexto_personalizado=contexto_personalizado,
            memoria_usuario=memoria_usuario,
        )

    try:
        logger.info(
            f"Gerando resposta Alquimia para terapeuta {terapeuta_id} | "
            f"Modo: {modo.value} | Chunks: {len(contexto_chunks)} | "
            f"Modelo: {settings.CLAUDE_MODEL} | MaxTokens: {max_tokens} | "
            f"Historico: {len(historico_mensagens) if historico_mensagens else 0} msgs | "
            f"Temperature: 0 (anti-delirio)"
        )

        # Monta mensagens: historico completo como turnos alternados + pergunta atual.
        # Isso permite ao Claude LEMBRAR toda a conversa anterior (anamnese, dados do caso).
        # O system prompt contem instrucoes, contexto RAG e regras anti-delirio.
        messages = _montar_mensagens_historico(historico_mensagens, pergunta)

        # Chamada a API com retry automatico para erros transientes (429, 5xx)
        response = await _chamar_claude_com_retry(
            client=client,
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )

        # Extrai o texto da resposta (com guard contra resposta vazia)
        if not response.content or not hasattr(response.content[0], "text"):
            logger.error(
                f"[GENERATOR] Claude retornou resposta sem texto. "
                f"Content: {response.content}, stop_reason: {response.stop_reason}"
            )
            raise RuntimeError("Claude API retornou resposta vazia")
        resposta = response.content[0].text

        # Verificacao de grounding — detecta possiveis alucinacoes
        # Loga warnings quando a resposta cita informacoes nao presentes nos chunks
        resposta = verificar_grounding(resposta, contexto_chunks)

        # Fontes ficam apenas no log, NAO na resposta (quebra humanizacao)
        fontes = extrair_fontes_resposta(contexto_chunks)
        if fontes:
            logger.info(f"Fontes consultadas: {fontes}")

        logger.info(
            f"Resposta gerada: {len(resposta)} caracteres | "
            f"Tokens usados: input={response.usage.input_tokens}, output={response.usage.output_tokens}"
        )

        return resposta

    except anthropic.APIError as e:
        logger.error(f"Erro na API do Claude: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}", exc_info=True)
        raise


@retry_async(
    max_tentativas=3,
    delay_base=2.0,
    delay_max=10.0,
    excecoes=(anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.APITimeoutError),
    nome_operacao="Claude API (gerar_resposta)",
)
async def _chamar_claude_com_retry(
    client: anthropic.AsyncAnthropic,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict],
) -> anthropic.types.Message:
    """
    Chama a API do Claude com retry automatico via decorator.

    Retenta apenas erros transientes:
    - APIStatusError: inclui 429 (rate limit), 500, 502, 503, 529 (overloaded)
    - APIConnectionError: falha de rede
    - APITimeoutError: timeout da request

    Erros de autenticacao (401) e validacao (400) sao propagados
    imediatamente pelo decorator (nao estao na lista de excecoes retentaveis,
    mas APIStatusError os inclui — o raise dentro filtra por status code).

    Args:
        client: Cliente Anthropic async.
        model: Nome do modelo Claude a usar.
        max_tokens: Limite de tokens na resposta.
        system: System prompt completo.
        messages: Lista de mensagens no formato da API.

    Returns:
        Objeto Message da API do Claude.

    Raises:
        anthropic.APIStatusError: Se o erro nao for transiente ou todas as tentativas falharem.
        anthropic.APIConnectionError: Se a conexao falhar em todas as tentativas.
        anthropic.APITimeoutError: Se todas as tentativas excederem o timeout.
    """
    try:
        return await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,  # ZERO criatividade = ZERO delirio
            system=system,
            messages=messages,
        )
    except anthropic.APIStatusError as e:
        # Propaga imediatamente erros nao-transientes (400, 401, 403, 404)
        # para que o decorator NAO retente esses casos
        if e.status_code not in (429, 500, 502, 503, 529):
            raise RuntimeError(f"Claude API erro nao-transiente ({e.status_code}): {e}") from e
        raise  # Erros transientes sao retentados pelo decorator


async def classificar_intencao(mensagem: str) -> IntencaoMensagem:
    """
    Classifica a intencao da mensagem usando Claude Haiku (rapido e barato).

    Usado para logging adicional no webhook. A deteccao principal de modo e
    feita por detectar_modo() em prompts.py (por palavras-chave, sem custo de API).

    Tem timeout de 15s e fallback para DUVIDA_GERAL em caso de erro,
    pois a classificacao e apenas informativa e nao deve bloquear o fluxo.

    Args:
        mensagem: Texto da mensagem recebida.

    Returns:
        IntencaoMensagem com a classificacao. Retorna DUVIDA_GERAL em caso de erro.
    """
    client = _get_anthropic_client()
    prompt = PROMPT_CLASSIFICACAO.format(mensagem=mensagem)

    try:
        # Timeout de 15s — classificacao e acessoria, nao pode travar o fluxo
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=15.0,
        )

        classificacao_raw = response.content[0].text.strip().upper()

        try:
            intencao = IntencaoMensagem(classificacao_raw)
        except ValueError:
            logger.warning(
                f"Classificacao inesperada: '{classificacao_raw}'. "
                f"Assumindo DUVIDA_GERAL para mensagem: '{mensagem[:50]}...'"
            )
            intencao = IntencaoMensagem.DUVIDA_GERAL

        logger.info(f"Intencao classificada: {intencao.value} | Mensagem: '{mensagem[:80]}...'")
        return intencao

    except asyncio.TimeoutError:
        logger.warning(f"Timeout ao classificar intencao (15s). Mensagem: '{mensagem[:50]}...'")
        return IntencaoMensagem.DUVIDA_GERAL
    except Exception as e:
        logger.error(f"Erro ao classificar intencao: {e}", exc_info=True)
        return IntencaoMensagem.DUVIDA_GERAL
