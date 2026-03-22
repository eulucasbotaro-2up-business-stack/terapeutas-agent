"""
Busca vetorial para o sistema de RAG.

Recebe a pergunta do paciente, gera embedding e busca os chunks mais
relevantes no Supabase pgvector, filtrados por terapeuta_id (multi-tenant).
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Singleton do cliente OpenAI (inicializado sob demanda)
_openai_client: Optional[AsyncOpenAI] = None

# Threshold mínimo de similaridade — chunks abaixo disso são descartados
SIMILARIDADE_MINIMA = 0.3


def _get_openai_client() -> AsyncOpenAI:
    """Retorna instância singleton do cliente OpenAI para embeddings."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def gerar_embedding_pergunta(pergunta: str) -> list[float]:
    """
    Gera o embedding de uma pergunta do paciente.

    Args:
        pergunta: Texto da pergunta.

    Returns:
        Vetor de embedding com 1536 dimensões.
    """
    settings = get_settings()
    client = _get_openai_client()

    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=pergunta,
    )

    embedding = response.data[0].embedding
    logger.debug(f"Embedding gerado para pergunta ({len(embedding)} dimensões)")
    return embedding


async def buscar_contexto(
    pergunta: str,
    terapeuta_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Busca os chunks mais relevantes para a pergunta do paciente.

    Usa a função RPC 'buscar_chunks' do Supabase (pgvector) para encontrar
    os chunks com maior similaridade semântica, filtrados pelo terapeuta_id.

    Args:
        pergunta: Texto da pergunta do paciente.
        terapeuta_id: UUID do terapeuta (isolamento multi-tenant).
        top_k: Quantidade máxima de chunks a retornar (padrão: 5).

    Returns:
        Lista de dicionários com os chunks relevantes:
        [
            {
                "conteudo": str,
                "similaridade": float,
                "documento_id": str,
                "chunk_index": int,
            },
            ...
        ]
        Retorna lista vazia se nenhum chunk relevante for encontrado.
    """
    settings = get_settings()
    supabase = get_supabase()

    # Usa top_k do parâmetro ou o padrão do settings
    quantidade = top_k or settings.RAG_TOP_K

    try:
        # 1. Gera embedding da pergunta
        embedding_pergunta = await gerar_embedding_pergunta(pergunta)

        # 2. Chama a RPC do Supabase para busca vetorial
        # A função 'buscar_chunks' já existe no banco e faz:
        # - Busca por similaridade coseno no pgvector
        # - Filtra por terapeuta_id
        # - Retorna os top_k chunks mais similares
        resultado = supabase.rpc(
            "buscar_chunks",
            {
                "query_embedding": embedding_pergunta,
                "p_terapeuta_id": terapeuta_id,
                "match_count": quantidade,
            },
        ).execute()

        if not resultado.data:
            logger.info(f"Nenhum chunk encontrado para terapeuta {terapeuta_id}")
            return []

        # 3. Filtra chunks com similaridade abaixo do threshold
        # Inclui arquivo_fonte (vindo da tabela documentos via JOIN na RPC)
        # para que o prompts.py consiga identificar o nivel de cada chunk
        chunks_relevantes = [
            {
                "conteudo": chunk["conteudo"],
                "similaridade": chunk["similaridade"],
                "documento_id": chunk.get("documento_id", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "arquivo_fonte": chunk.get("arquivo_fonte", chunk.get("nome_arquivo", "")),
            }
            for chunk in resultado.data
            if chunk.get("similaridade", 0) >= SIMILARIDADE_MINIMA
        ]

        logger.info(
            f"Busca vetorial: {len(resultado.data)} chunks encontrados, "
            f"{len(chunks_relevantes)} acima do threshold ({SIMILARIDADE_MINIMA})"
        )

        return chunks_relevantes

    except Exception as e:
        logger.error(f"Erro na busca vetorial para terapeuta {terapeuta_id}: {e}", exc_info=True)
        raise


async def formatar_contexto(chunks: list[dict]) -> str:
    """
    Formata os chunks retornados em texto para inserir no prompt.

    Concatena os conteúdos dos chunks separados por linha,
    ordenados por similaridade (mais relevante primeiro).

    Args:
        chunks: Lista de chunks retornados por buscar_contexto().

    Returns:
        Texto formatado com todos os chunks concatenados.
        Retorna string vazia se não houver chunks.
    """
    if not chunks:
        return ""

    # Ordena por similaridade decrescente (mais relevante primeiro)
    chunks_ordenados = sorted(chunks, key=lambda c: c["similaridade"], reverse=True)

    # Formata cada chunk com numeração
    partes = []
    for i, chunk in enumerate(chunks_ordenados, start=1):
        partes.append(f"[Trecho {i}] (relevância: {chunk['similaridade']:.2f})\n{chunk['conteudo']}")

    contexto = "\n\n---\n\n".join(partes)
    logger.debug(f"Contexto formatado: {len(contexto)} caracteres de {len(chunks_ordenados)} chunks")

    return contexto
