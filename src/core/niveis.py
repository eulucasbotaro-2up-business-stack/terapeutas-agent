"""
Sistema de niveis de acesso por modulo — Escola de Alquimia.

Cada terapeuta/aluno avanca progressivamente nos modulos.
O agente so responde com base nos materiais do nivel atual ou inferior.
"""

import logging
from src.core.prompts import NIVEIS_MATERIAIS

logger = logging.getLogger(__name__)


# =============================================
# MAPEAMENTO DE MODULOS COM NOMES DESCRITIVOS
# =============================================

MODULOS: dict[int, dict] = {
    1: {
        "nome": "Fundamentos",
        "descricao": "Pesquisa, Perguntas Frequentes",
    },
    2: {
        "nome": "Elementos e Matrix",
        "descricao": "4 Elementos, Pletora, Matrix/Traumas, Miasmas",
    },
    3: {
        "nome": "DNA Alquimico",
        "descricao": "DNA, Referencia DNA",
    },
    4: {
        "nome": "Transmutacao",
        "descricao": "Nigredo, Rubedo, Alquimia Avancada, Aliastrum, Matrix",
    },
    5: {
        "nome": "Astrologia e Ciclos",
        "descricao": "Fluxus, Astrologia, Biorritmos, Chakras",
    },
    6: {
        "nome": "Protocolos e Aplicacao",
        "descricao": "Protocolos, Kit Primus, Florais, Cosmeticos",
    },
}


def obter_nome_modulo(nivel: int) -> str:
    """Retorna o nome descritivo de um modulo pelo nivel."""
    modulo = MODULOS.get(nivel)
    if modulo:
        return modulo["nome"]
    return f"Nivel {nivel}"


def obter_nivel_chunk(chunk: dict) -> int:
    """
    Identifica o nivel de um chunk com base no arquivo_fonte.
    Usa o mapeamento NIVEIS_MATERIAIS de prompts.py.

    Retorna 0 se nao conseguir identificar (chunk sera permitido por padrao).
    """
    nome_arquivo = chunk.get("arquivo_fonte", "")
    if not nome_arquivo:
        return 0

    # Busca exata
    if nome_arquivo in NIVEIS_MATERIAIS:
        return NIVEIS_MATERIAIS[nome_arquivo]

    # Busca parcial (variacoes de nome)
    nome_lower = nome_arquivo.lower()
    for pdf, nivel in NIVEIS_MATERIAIS.items():
        if pdf.lower() in nome_lower or nome_lower in pdf.lower():
            return nivel

    return 0


def filtrar_chunks_por_nivel(
    chunks: list[dict],
    nivel_terapeuta: int,
) -> tuple[list[dict], int | None]:
    """
    Filtra chunks removendo os que pertencem a materiais acima do nivel do terapeuta.

    Args:
        chunks: Lista de chunks retornados pelo RAG.
        nivel_terapeuta: Nivel de acesso atual do terapeuta (1-6).

    Returns:
        Tupla com:
        - chunks_permitidos: Lista de chunks filtrados.
        - nivel_bloqueado: Menor nivel bloqueado encontrado, ou None se nada bloqueado.
    """
    chunks_permitidos = []
    nivel_bloqueado_min = None

    for chunk in chunks:
        nivel_chunk = obter_nivel_chunk(chunk)

        # Chunks sem nivel identificado (0) sao permitidos por padrao
        if nivel_chunk == 0 or nivel_chunk <= nivel_terapeuta:
            chunks_permitidos.append(chunk)
        else:
            logger.info(
                f"Chunk bloqueado: arquivo='{chunk.get('arquivo_fonte', '?')}' "
                f"nivel_chunk={nivel_chunk} > nivel_terapeuta={nivel_terapeuta}"
            )
            if nivel_bloqueado_min is None or nivel_chunk < nivel_bloqueado_min:
                nivel_bloqueado_min = nivel_chunk

    logger.info(
        f"Filtro de nivel: {len(chunks)} chunks recebidos, "
        f"{len(chunks_permitidos)} permitidos (nivel terapeuta: {nivel_terapeuta})"
    )

    return chunks_permitidos, nivel_bloqueado_min


def mensagem_nivel_bloqueado(nivel_necessario: int, nivel_atual: int) -> str:
    """
    Gera mensagem informando que o conteudo esta bloqueado.

    Args:
        nivel_necessario: Nivel minimo para acessar o conteudo.
        nivel_atual: Nivel atual do terapeuta.

    Returns:
        Mensagem amigavel de bloqueio.
    """
    nome_necessario = obter_nome_modulo(nivel_necessario)
    nome_atual = obter_nome_modulo(nivel_atual)

    return (
        f"Esse conteudo faz parte do modulo *{nome_necessario}* (nivel {nivel_necessario}). "
        f"Voce esta no modulo *{nome_atual}* (nivel {nivel_atual}). "
        f"Complete o modulo atual pra desbloquear."
    )
