"""
Processamento de PDFs para o sistema de RAG.

Extrai texto de PDFs, divide em chunks, gera embeddings e salva no Supabase.
Cada documento é associado a um terapeuta_id (multi-tenant).
"""

import logging
import tempfile
import os
from typing import Optional

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Singleton do cliente OpenAI (inicializado sob demanda)
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """Retorna instância singleton do cliente OpenAI para embeddings."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def extrair_texto_pdf(caminho_pdf: str) -> str:
    """
    Extrai todo o texto de um arquivo PDF usando PyMuPDF.

    Args:
        caminho_pdf: Caminho do arquivo PDF no sistema de arquivos.

    Returns:
        Texto completo extraído do PDF.

    Raises:
        FileNotFoundError: Se o arquivo não for encontrado.
        Exception: Se houver erro na leitura do PDF.
    """
    logger.info(f"Extraindo texto do PDF: {caminho_pdf}")

    doc = fitz.open(caminho_pdf)
    texto_completo = ""

    for num_pagina, pagina in enumerate(doc, start=1):
        texto_pagina = pagina.get_text("text")
        if texto_pagina.strip():
            texto_completo += texto_pagina + "\n\n"
            logger.debug(f"Página {num_pagina}: {len(texto_pagina)} caracteres extraídos")

    num_paginas = doc.page_count
    doc.close()

    logger.info(f"Total extraído: {len(texto_completo)} caracteres de {num_paginas} páginas")
    return texto_completo.strip()


def dividir_em_chunks(texto: str) -> list[str]:
    """
    Divide o texto em chunks usando RecursiveCharacterTextSplitter.

    Usa as configurações de CHUNK_SIZE e CHUNK_OVERLAP definidas no settings.

    Args:
        texto: Texto completo a ser dividido.

    Returns:
        Lista de chunks de texto.
    """
    settings = get_settings()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(texto)
    logger.info(f"Texto dividido em {len(chunks)} chunks (tamanho={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP})")

    return chunks


async def gerar_embeddings(textos: list[str]) -> list[list[float]]:
    """
    Gera embeddings para uma lista de textos usando OpenAI text-embedding-3-small.

    Processa em lotes para respeitar limites da API.

    Args:
        textos: Lista de textos para gerar embeddings.

    Returns:
        Lista de vetores de embedding (cada um com 1536 dimensões).
    """
    settings = get_settings()
    client = _get_openai_client()

    # OpenAI aceita até ~8000 tokens por request em batch
    # Processamos em lotes de 100 para segurança
    TAMANHO_LOTE = 100
    todos_embeddings: list[list[float]] = []

    for i in range(0, len(textos), TAMANHO_LOTE):
        lote = textos[i : i + TAMANHO_LOTE]
        logger.debug(f"Gerando embeddings para lote {i // TAMANHO_LOTE + 1} ({len(lote)} textos)")

        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=lote,
        )

        # Extrai os vetores na ordem correta
        embeddings_lote = [item.embedding for item in response.data]
        todos_embeddings.extend(embeddings_lote)

    logger.info(f"Gerados {len(todos_embeddings)} embeddings com modelo {settings.EMBEDDING_MODEL}")
    return todos_embeddings


async def salvar_chunks_no_supabase(
    chunks: list[str],
    embeddings: list[list[float]],
    terapeuta_id: str,
    documento_id: str,
) -> int:
    """
    Salva chunks e seus embeddings na tabela 'embeddings' do Supabase.

    Args:
        chunks: Lista de textos dos chunks.
        embeddings: Lista de vetores correspondentes.
        terapeuta_id: UUID do terapeuta dono do documento.
        documento_id: UUID do documento de origem.

    Returns:
        Quantidade de chunks salvos com sucesso.
    """
    supabase = get_supabase()

    # Monta registros para inserção em batch
    registros = [
        {
            "terapeuta_id": terapeuta_id,
            "documento_id": documento_id,
            "conteudo": chunk,
            "embedding": embedding,
            "chunk_index": idx,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    # Insere em lotes de 50 para evitar timeout
    TAMANHO_LOTE = 50
    total_inseridos = 0

    for i in range(0, len(registros), TAMANHO_LOTE):
        lote = registros[i : i + TAMANHO_LOTE]
        resultado = supabase.table("embeddings").insert(lote).execute()
        total_inseridos += len(resultado.data)
        logger.debug(f"Inseridos {len(resultado.data)} chunks (lote {i // TAMANHO_LOTE + 1})")

    logger.info(f"Total de {total_inseridos} chunks salvos no Supabase para documento {documento_id}")
    return total_inseridos


async def atualizar_status_documento(documento_id: str, status: str, erro: str | None = None) -> None:
    """
    Atualiza o status de processamento de um documento no Supabase.

    Args:
        documento_id: UUID do documento.
        status: Novo status ('processando', 'ativo', 'erro').
        erro: Mensagem de erro, se aplicável.
    """
    supabase = get_supabase()

    dados = {"status": status}
    if erro:
        dados["erro_processamento"] = erro

    supabase.table("documentos").update(dados).eq("id", documento_id).execute()
    logger.info(f"Documento {documento_id} atualizado para status: {status}")


def _baixar_pdf_do_storage(storage_path: str) -> str:
    """
    Baixa um PDF do Supabase Storage para um arquivo temporário local.

    Args:
        storage_path: Caminho do arquivo no bucket 'pdfs' do Supabase Storage.

    Returns:
        Caminho do arquivo temporário local.

    Raises:
        Exception: Se houver erro no download.
    """
    supabase = get_supabase()
    BUCKET_NAME = "pdfs"

    logger.info(f"Baixando PDF do Storage: {storage_path}")

    conteudo = supabase.storage.from_(BUCKET_NAME).download(storage_path)

    # Salva em arquivo temporário
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.write(conteudo)
    temp_file.close()

    logger.info(f"PDF salvo em arquivo temporário: {temp_file.name} ({len(conteudo)} bytes)")
    return temp_file.name


async def processar_pdf(caminho_pdf: str, terapeuta_id: str, documento_id: str) -> dict:
    """
    Pipeline completo de processamento de um PDF.

    1. Baixa o PDF do Supabase Storage (se for um storage path)
    2. Extrai texto do PDF
    3. Divide em chunks
    4. Gera embeddings com OpenAI
    5. Salva no Supabase (tabela embeddings)
    6. Atualiza status do documento

    Args:
        caminho_pdf: Caminho do arquivo PDF local OU path no Supabase Storage.
                     Se contém '/' e não existe localmente, tenta baixar do Storage.
        terapeuta_id: UUID do terapeuta dono do documento.
        documento_id: UUID do documento no banco.

    Returns:
        Dicionário com resultado do processamento:
        {
            "documento_id": str,
            "total_chunks": int,
            "status": str
        }
    """
    logger.info(f"Iniciando processamento do PDF: documento_id={documento_id}, terapeuta_id={terapeuta_id}")

    # Variável para rastrear arquivo temporário (para limpeza)
    arquivo_temporario = None

    try:
        # Marca documento como "processando"
        await atualizar_status_documento(documento_id, "processando")

        # Se o caminho não existe localmente, baixar do Supabase Storage
        if not os.path.isfile(caminho_pdf):
            logger.info(f"Arquivo não encontrado localmente, baixando do Storage: {caminho_pdf}")
            arquivo_temporario = _baixar_pdf_do_storage(caminho_pdf)
            caminho_pdf = arquivo_temporario

        # 1. Extrai texto do PDF
        texto = extrair_texto_pdf(caminho_pdf)
        if not texto:
            raise ValueError("PDF não contém texto extraível. Pode ser um PDF escaneado/imagem.")

        # 2. Divide em chunks
        chunks = dividir_em_chunks(texto)
        if not chunks:
            raise ValueError("Não foi possível dividir o texto em chunks.")

        logger.info(f"PDF processado: {len(chunks)} chunks gerados")

        # 3. Gera embeddings
        embeddings = await gerar_embeddings(chunks)

        # 4. Salva no Supabase
        total_salvos = await salvar_chunks_no_supabase(
            chunks=chunks,
            embeddings=embeddings,
            terapeuta_id=terapeuta_id,
            documento_id=documento_id,
        )

        # 5. Marca documento como "ativo"
        await atualizar_status_documento(documento_id, "ativo")

        resultado = {
            "documento_id": documento_id,
            "total_chunks": total_salvos,
            "status": "ativo",
        }
        logger.info(f"Processamento concluído com sucesso: {resultado}")
        return resultado

    except Exception as e:
        # Em caso de erro, atualiza status e re-lança exceção
        mensagem_erro = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Erro ao processar PDF {documento_id}: {mensagem_erro}", exc_info=True)

        try:
            await atualizar_status_documento(documento_id, "erro", erro=mensagem_erro)
        except Exception as e_status:
            logger.error(f"Erro ao atualizar status do documento: {e_status}")

        raise

    finally:
        # Limpa o arquivo temporário se foi criado
        if arquivo_temporario and os.path.isfile(arquivo_temporario):
            try:
                os.unlink(arquivo_temporario)
                logger.debug(f"Arquivo temporário removido: {arquivo_temporario}")
            except OSError as e:
                logger.warning(f"Não foi possível remover arquivo temporário: {e}")
