"""
Geracao de respostas com Claude API para o sistema de RAG.

Usa o system prompt especifico da Escola de Alquimia Joel Aleixo,
com contexto organizado por nivel de maturidade diagnostica.
Temperature 0 para eliminar alucinacoes.
Suporta historico de conversa para consultas multi-turno.
"""

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

logger = logging.getLogger(__name__)

# Singleton do cliente Anthropic (inicializado sob demanda)
_anthropic_client: Optional[anthropic.AsyncAnthropic] = None

# Max tokens por modo de operacao
# CONSULTA precisa de mais tokens (anamnese + diagnostico + indicacao terapeutica)
# CRIACAO_CONTEUDO precisa de mais tokens (2 variantes + hashtags + material de aprofundamento)
# PESQUISA pode ser longa quando cruza multiplos materiais
MAX_TOKENS_POR_MODO: dict[ModoOperacao, int] = {
    ModoOperacao.CONSULTA: 2048,
    ModoOperacao.CRIACAO_CONTEUDO: 2048,
    ModoOperacao.PESQUISA: 1536,
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


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Retorna instancia singleton do cliente Anthropic."""
    global _anthropic_client
    if _anthropic_client is None:
        settings = get_settings()
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def gerar_resposta(
    pergunta: str,
    terapeuta_id: str,
    contexto_chunks: list[dict],
    config_terapeuta: dict,
    historico_mensagens: list[dict] | None = None,
    modo_override: ModoOperacao | None = None,
    contexto_personalizado: str | None = None,
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

    Returns:
        Texto da resposta gerada pelo Claude, formatada para WhatsApp,
        com fontes citadas no final.
    """
    settings = get_settings()
    client = _get_anthropic_client()

    # Detectar modo para determinar max_tokens
    modo = modo_override or detectar_modo(pergunta)
    max_tokens = MAX_TOKENS_POR_MODO.get(modo, MAX_TOKENS_DEFAULT)

    # Monta o system prompt da Alquimia com contexto organizado por nivel
    system_prompt = montar_prompt(
        terapeuta=config_terapeuta,
        contexto_chunks=contexto_chunks,
        mensagem=pergunta,
        modo_override=modo_override,
        historico_mensagens=historico_mensagens,
        contexto_personalizado=contexto_personalizado,
    )

    try:
        logger.info(
            f"Gerando resposta Alquimia para terapeuta {terapeuta_id} | "
            f"Modo: {modo.value} | Chunks: {len(contexto_chunks)} | "
            f"Modelo: {settings.CLAUDE_MODEL} | MaxTokens: {max_tokens} | "
            f"Historico: {len(historico_mensagens) if historico_mensagens else 0} msgs | "
            f"Temperature: 0 (anti-delirio)"
        )

        # O system prompt ja contem todas as instrucoes anti-delirio, regras e contexto.
        # A mensagem do usuario contem apenas a pergunta, sem repeticao de instrucoes
        # (repetir instrucoes no user message desperdicava ~50 tokens sem ganho).
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=0,  # ZERO criatividade = ZERO delirio
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": pergunta,
                }
            ],
        )

        # Extrai o texto da resposta
        resposta = response.content[0].text

        # Adiciona fontes ao final da resposta para rastreabilidade
        fontes = extrair_fontes_resposta(contexto_chunks)
        if fontes:
            resposta += fontes

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


async def classificar_intencao(mensagem: str) -> IntencaoMensagem:
    """
    Classifica a intencao da mensagem usando Claude Haiku (rapido e barato).
    Usado para logging adicional no webhook. A deteccao principal de modo e
    feita por detectar_modo() em prompts.py (por palavras-chave, sem custo de API).

    Args:
        mensagem: Texto da mensagem recebida.

    Returns:
        IntencaoMensagem com a classificacao.
    """
    client = _get_anthropic_client()
    prompt = PROMPT_CLASSIFICACAO.format(mensagem=mensagem)

    try:
        response = await client.messages.create(
            model="claude-haiku-4-20250414",
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
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

    except Exception as e:
        logger.error(f"Erro ao classificar intencao: {e}", exc_info=True)
        return IntencaoMensagem.DUVIDA_GERAL
