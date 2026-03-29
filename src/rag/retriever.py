"""
Busca vetorial para o sistema de RAG.

Recebe a pergunta do paciente, gera embedding e busca os chunks mais
relevantes no Supabase pgvector, filtrados por terapeuta_id (multi-tenant).

Suporta busca híbrida: vetorial + filtro por tags para maior precisão.
Detecta automaticamente tags relevantes na pergunta e filtra chunks.
Se a busca filtrada retornar poucos resultados, faz fallback sem filtro.
"""

import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Singleton do cliente OpenAI (inicializado sob demanda)
_openai_client: Optional[AsyncOpenAI] = None

# Threshold mínimo de similaridade — chunks abaixo disso são descartados
# Reduzido de 0.15 para 0.05 para aceitar mais chunks relevantes sobre
# florais específicos (Trapoeraba, Manjericão, Rosa, etc.) e termos
# alquímicos específicos que tinham similaridade baixa e estavam sendo filtrados
SIMILARIDADE_MINIMA = 0.05

# Mínimo de chunks filtrados para considerar a busca com tags válida.
# Se retornar menos que isso, faz fallback para busca sem filtro.
MINIMO_CHUNKS_COM_TAG = 2

# ============================================================
# Mapeamento de termos na pergunta → tags para filtro
# ============================================================
# Cada entrada: (padrão regex case-insensitive, lista de tags)
# A detecção é aditiva — se múltiplos padrões casam, todas as tags
# são combinadas para o filtro (operador overlap: qualquer tag em comum).
# ============================================================
MAPA_TERMOS_TAGS: list[tuple[str, list[str]]] = [
    # DNA e cores
    (r"\bdna\b", ["dna"]),
    (r"\bdna\s+alqu[ií]mico", ["dna", "dna_leitura"]),
    (r"\b7\s*cores?\b|sete\s+cores?", ["dna"]),
    (r"\bcor\s+(vermelh|laranj|amarel|verde|azul|[ií]ndigo|violet)", ["dna"]),
    (r"\bleitura\s+de\s+dna\b|leitura\s+alqu[ií]mica", ["dna", "dna_leitura"]),
    (r"\brefer[eê]ncia\s+do\s+dna\b", ["dna", "dna_referencia"]),

    # Chakras
    (r"\bchakra|chacra|chackra", ["chakra"]),
    (r"\bchakra\s+base\b|chakra\s+ra[ií]z", ["chakra", "chakra_base"]),
    (r"\bchakra\s+sacral\b", ["chakra", "chakra_sacral"]),
    (r"\bplexo\s+solar\b", ["chakra", "chakra_plexo"]),
    (r"\bchakra\s+card[ií]aco\b|chakra\s+cora[çc][aã]o", ["chakra", "chakra_cardiaco"]),
    (r"\bchakra\s+lar[ií]ngeo\b|chakra\s+garganta", ["chakra", "chakra_laringeo"]),
    (r"\bchakra\s+frontal\b|terceiro\s+olho", ["chakra", "chakra_frontal"]),
    (r"\bchakra\s+coron[aá]rio\b", ["chakra", "chakra_coronario"]),

    # Elementos
    (r"\b4\s*elementos|quatro\s+elementos", ["elementos"]),
    (r"\belemento\s+terra\b", ["elementos", "elemento_terra"]),
    (r"\belemento\s+[aá]gua\b", ["elementos", "elemento_agua"]),
    (r"\belemento\s+fogo\b", ["elementos", "elemento_fogo"]),
    (r"\belemento\s+ar\b", ["elementos", "elemento_ar"]),
    (r"\bpl[eé]tora\b", ["elementos", "pletora"]),
    (r"\bphoenix\b|f[eê]nix", ["elementos", "phoenix"]),

    # Transmutação
    (r"\bnigredo\b", ["transmutacao", "nigredo"]),
    (r"\brubedo\b", ["transmutacao", "rubedo"]),
    (r"\balbedo\b", ["transmutacao", "albedo"]),
    (r"\btransmuta[çc][aã]o\b", ["transmutacao"]),
    (r"\bal+iastrum\b", ["transmutacao", "alliastrum"]),
    (r"\btrindade\b", ["trindade"]),
    (r"\btartarus\b|t[aá]rtaro", ["tartarus"]),

    # Matrix e traumas
    (r"\bmatrix\b|matriz", ["matrix"]),
    (r"\btrauma\b|traum[aá]tic", ["matrix", "matrix_trauma"]),
    (r"\bpadr[aã]o\s+(repetitivo|familiar|emocional)", ["matrix", "matrix_padrao"]),
    (r"\bheran[çc]a\b|herdad", ["matrix", "matrix_heranca"]),
    (r"\bmiasma\b", ["miasma"]),
    (r"\bserpente\b|serpentes\b", ["matrix_padrao", "matrix_heranca"]),

    # Astrologia
    (r"\bastrolog", ["astrologia"]),
    (r"\bmapa\s+astral\b|mapa\s+astrol[oó]gic", ["astrologia", "astro_mapa"]),
    (r"\bsigno\b|signos\b", ["astrologia"]),
    (r"\bciclo\b|ciclos\b", ["astro_ciclo"]),
    (r"\bregente\b", ["astrologia", "astro_regente"]),
    (r"\bcasa\s+astrol[oó]gica\b", ["astrologia", "astro_casa"]),
    (r"\bcorpus\s+celestes?\b", ["floral", "astrologia", "kit_primus"]),

    # Biorritmo
    (r"\bbiorr[ií]tmo|biorritmo", ["biorritmo"]),

    # Fluxus
    (r"\bfluxus\b|john\s+dee", ["fluxus"]),

    # Florais
    (r"\bfloral\b|florais\b", ["floral"]),
    (r"\bflor\s+alqu[ií]mic|flores\s+alqu[ií]mic", ["floral"]),
    (r"\baura\s+d(as|os)\s+flor", ["floral", "floral_aura"]),
    (r"\bessência\s+floral\b|ess[eê]ncia", ["floral"]),
    (r"\btrapoeraba\b", ["floral", "kit_primus"]),
    (r"\bmanjeric[aã]o\b", ["floral", "kit_primus"]),
    (r"\brosa\b.*\bfloral\b|\bfloral\b.*\brosa\b", ["floral", "kit_primus"]),
    (r"\bbabosa\b", ["floral", "kit_primus"]),
    (r"\bpic[aã]o\b", ["floral", "kit_primus"]),
    (r"\blótus\b|lotus\b", ["floral"]),
    (r"\bmagnólia\b|magnolia\b", ["floral"]),

    # Protocolos
    (r"\bprotocolo\b", ["protocolo"]),
    (r"\bkit\s+primus\b|kite\s+primus", ["protocolo", "kit_primus"]),
    (r"\bkit\s+matrix\b|kit\s+materlux\b|materlux\b", ["matrix", "matrix_trauma", "floral"]),
    (r"\bkit\s+torus\b", ["torus", "floral"]),
    (r"\bkit\s+dna\b", ["dna", "dna_leitura"]),

    # Vitriol e Torus
    (r"\bvitriol\b", ["vitriol"]),
    (r"\btorus\b", ["torus"]),

    # Fundamentos / pesquisa
    (r"\bprimeiro\s+passo\b|como\s+come[çc]ar", ["fundamentos"]),
    (r"\bpesquisa\b", ["pesquisa"]),
]


def detectar_tags(pergunta: str) -> list[str]:
    """
    Detecta tags relevantes a partir do texto da pergunta.

    Usa regex case-insensitive para encontrar termos-chave e
    retorna a lista de tags correspondentes (sem duplicatas).

    Args:
        pergunta: Texto da pergunta do paciente.

    Returns:
        Lista de tags detectadas (pode ser vazia).
    """
    tags_encontradas: set[str] = set()
    texto = pergunta.lower()

    for padrao, tags in MAPA_TERMOS_TAGS:
        if re.search(padrao, texto, re.IGNORECASE):
            tags_encontradas.update(tags)

    tags_list = sorted(tags_encontradas)
    if tags_list:
        logger.info(f"Tags detectadas na pergunta: {tags_list}")
    return tags_list


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

    Usa busca híbrida: vetorial (cosine similarity) + filtro por tags.
    1. Detecta tags na pergunta (regex sobre termos-chave)
    2. Se tags detectadas, usa buscar_chunks_v2 com filtro de tags
    3. Se poucos resultados com filtro, faz fallback sem filtro
    4. Fallback final: buscar_chunks original (sem tags)

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
                "arquivo_fonte": str,
                "tags": list[str],
                "modulo": int,
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

        # 2. Detecta tags na pergunta para filtro opcional
        tags_detectadas = detectar_tags(pergunta)

        # 3. Tenta busca com tags (se detectadas)
        resultado = None
        usou_tags = False

        if tags_detectadas:
            try:
                resultado = supabase.rpc(
                    "buscar_chunks_v2",
                    {
                        "query_embedding": embedding_pergunta,
                        "p_terapeuta_id": terapeuta_id,
                        "match_count": quantidade,
                        "p_tags": tags_detectadas,
                    },
                ).execute()
                usou_tags = True

                # Fallback: se poucos resultados com filtro, busca sem filtro
                if not resultado.data or len(resultado.data) < MINIMO_CHUNKS_COM_TAG:
                    logger.info(
                        f"Busca com tags retornou {len(resultado.data) if resultado.data else 0} chunks "
                        f"(mínimo: {MINIMO_CHUNKS_COM_TAG}), fazendo fallback sem tags"
                    )
                    resultado = None
                    usou_tags = False

            except Exception as e:
                logger.warning(f"Erro na busca com tags, fazendo fallback: {e}")
                resultado = None
                usou_tags = False

        # 4. Fallback: busca sem filtro de tags (buscar_chunks_v2 com p_tags=NULL)
        if resultado is None:
            try:
                resultado = supabase.rpc(
                    "buscar_chunks_v2",
                    {
                        "query_embedding": embedding_pergunta,
                        "p_terapeuta_id": terapeuta_id,
                        "match_count": quantidade,
                        "p_tags": None,
                    },
                ).execute()
            except Exception:
                # Fallback final: usa a função original buscar_chunks
                logger.warning("buscar_chunks_v2 falhou, usando buscar_chunks original")
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

        # 5. Filtra chunks com similaridade abaixo do threshold
        chunks_relevantes = [
            {
                "conteudo": chunk["conteudo"],
                "similaridade": chunk["similaridade"],
                "documento_id": chunk.get("documento_id", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "arquivo_fonte": chunk.get("arquivo_fonte", chunk.get("nome_arquivo", "")),
                "tags": chunk.get("tags", []),
                "modulo": chunk.get("modulo"),
            }
            for chunk in resultado.data
            if chunk.get("similaridade", 0) >= SIMILARIDADE_MINIMA
        ]

        logger.info(
            f"Busca vetorial: {len(resultado.data)} chunks encontrados, "
            f"{len(chunks_relevantes)} acima do threshold ({SIMILARIDADE_MINIMA})"
            f"{' [COM filtro de tags: ' + str(tags_detectadas) + ']' if usou_tags else ' [SEM filtro de tags]'}"
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
