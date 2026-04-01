"""
Gestão de documentos (PDFs) dos terapeutas.
Upload, listagem e remoção de materiais usados na base de conhecimento do agente.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File

from src.core.auth import verificar_admin_token
from src.core.supabase_client import get_supabase
from src.models.schemas import DocumentoResponse
from src.rag.processor import processar_pdf

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documentos",
    tags=["Documentos"],
    dependencies=[Depends(verificar_admin_token)],
)

# Tamanho máximo de upload: 20 MB
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
TIPOS_PERMITIDOS = ["application/pdf"]
BUCKET_NAME = "pdfs"


# =============================================
# UPLOAD DE DOCUMENTO
# =============================================

@router.post(
    "/upload/{terapeuta_id}",
    response_model=DocumentoResponse,
    status_code=201,
    summary="Fazer upload de um PDF",
)
async def upload_documento(
    terapeuta_id: UUID,
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(..., description="Arquivo PDF para upload"),
):
    """
    Recebe um arquivo PDF do terapeuta e inicia o processamento para RAG.

    Fluxo:
    1. Valida o arquivo (tipo e tamanho)
    2. Salva no Supabase Storage (bucket 'pdfs', path: terapeuta_id/filename)
    3. Cria registro na tabela 'documentos'
    4. Dispara processamento em background (chunking + embedding)
    5. Retorna o documento_id com status 'processando'
    """
    supabase = get_supabase()

    # --- Validações ---

    # Verificar se o terapeuta existe e está ativo
    terapeuta = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not terapeuta.data or len(terapeuta.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} não encontrado",
        )

    # Validar tipo do arquivo
    if arquivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não suportado: {arquivo.content_type}. Envie apenas PDF.",
        )

    # Ler o conteúdo do arquivo
    try:
        conteudo_arquivo = await arquivo.read()
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de upload: {e}")
        raise HTTPException(status_code=400, detail="Erro ao ler o arquivo enviado")

    tamanho_bytes = len(conteudo_arquivo)

    # Validar tamanho
    if tamanho_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo muito grande ({tamanho_bytes / 1024 / 1024:.1f} MB). "
                   f"Máximo permitido: {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB.",
        )

    if tamanho_bytes == 0:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    # --- Upload para Supabase Storage ---

    # Gerar nome único para evitar colisões
    nome_original = arquivo.filename or "documento.pdf"
    documento_id = str(uuid4())
    storage_path = f"{terapeuta_id}/{documento_id}_{nome_original}"

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=conteudo_arquivo,
            file_options={"content-type": "application/pdf"},
        )
        logger.info(f"PDF salvo no Storage: {storage_path}")
    except Exception as e:
        logger.error(f"Erro ao fazer upload para Supabase Storage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao salvar arquivo no storage. Tente novamente.",
        )

    # --- Criar registro na tabela 'documentos' ---

    agora = datetime.now(timezone.utc).isoformat()
    registro_documento = {
        "id": documento_id,
        "terapeuta_id": str(terapeuta_id),
        "nome_arquivo": nome_original,
        "tipo": "pdf",
        "tamanho_bytes": tamanho_bytes,
        "storage_path": storage_path,
        "total_chunks": 0,
        "processado": False,
        "criado_em": agora,
    }

    try:
        resultado = supabase.table("documentos").insert(registro_documento).execute()
    except Exception as e:
        logger.error(f"Erro ao criar registro do documento: {e}")
        # Tentar limpar o arquivo do storage em caso de falha
        try:
            supabase.storage.from_(BUCKET_NAME).remove([storage_path])
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail="Erro ao registrar documento no banco de dados",
        )

    if not resultado.data:
        raise HTTPException(status_code=500, detail="Falha ao inserir documento no banco")

    logger.info(
        f"Documento registrado: {documento_id} — "
        f"terapeuta={terapeuta_id}, arquivo={nome_original} ({tamanho_bytes} bytes)"
    )

    # --- Disparar processamento em background ---
    # O processamento faz: leitura do PDF → chunking → embedding → salvar no pgvector
    background_tasks.add_task(
        processar_pdf,
        caminho_pdf=storage_path,
        terapeuta_id=str(terapeuta_id),
        documento_id=documento_id,
    )

    logger.info(f"Processamento de PDF iniciado em background: {documento_id}")

    return resultado.data[0]


# =============================================
# LISTAR DOCUMENTOS DO TERAPEUTA
# =============================================

@router.get(
    "/{terapeuta_id}",
    response_model=list[DocumentoResponse],
    summary="Listar documentos de um terapeuta",
)
async def listar_documentos(terapeuta_id: UUID):
    """
    Retorna todos os documentos de um terapeuta específico.
    Ordenados por data de criação (mais recentes primeiro).
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe
    terapeuta = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not terapeuta.data or len(terapeuta.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} não encontrado",
        )

    try:
        resultado = (
            supabase.table("documentos")
            .select("*")
            .eq("terapeuta_id", str(terapeuta_id))
            .order("criado_em", desc=True)
            .execute()
        )
    except Exception as e:
        logger.error(f"Erro ao listar documentos do terapeuta {terapeuta_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao buscar documentos")

    return resultado.data or []


# =============================================
# REMOVER DOCUMENTO
# =============================================

@router.delete(
    "/{terapeuta_id}/{documento_id}",
    summary="Remover documento e seus embeddings",
)
async def remover_documento(terapeuta_id: UUID, documento_id: UUID):
    """
    Remove um documento completamente:
    1. Remove os embeddings (chunks) do pgvector
    2. Remove o arquivo do Supabase Storage
    3. Remove o registro da tabela 'documentos'

    Exige terapeuta_id na URL para garantir isolamento multi-tenant.
    """
    supabase = get_supabase()

    # Buscar o documento COM filtro de terapeuta (multi-tenancy)
    documento = (
        supabase.table("documentos")
        .select("*")
        .eq("id", str(documento_id))
        .eq("terapeuta_id", str(terapeuta_id))
        .limit(1)
        .execute()
    )

    if not documento.data or len(documento.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Documento {documento_id} não encontrado",
        )

    doc = documento.data[0]
    storage_path = doc.get("storage_path", "")

    # 1. Remover embeddings associados ao documento (filtro duplo por seguranca)
    try:
        supabase.table("embeddings").delete().eq(
            "documento_id", str(documento_id)
        ).eq(
            "terapeuta_id", str(terapeuta_id)
        ).execute()
        logger.info(f"Embeddings removidos para documento {documento_id}")
    except Exception as e:
        logger.error(f"Erro ao remover embeddings do documento {documento_id}: {e}")
        # Continuar mesmo com erro — melhor remover parcialmente que não remover nada

    # 2. Remover arquivo do Supabase Storage
    if storage_path:
        try:
            supabase.storage.from_(BUCKET_NAME).remove([storage_path])
            logger.info(f"Arquivo removido do Storage: {storage_path}")
        except Exception as e:
            logger.error(f"Erro ao remover arquivo do Storage ({storage_path}): {e}")

    # 3. Remover registro da tabela 'documentos'
    try:
        supabase.table("documentos").delete().eq(
            "id", str(documento_id)
        ).execute()
        logger.info(f"Registro do documento removido: {documento_id}")
    except Exception as e:
        logger.error(f"Erro ao remover registro do documento {documento_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao remover documento do banco",
        )

    return {
        "status": "removido",
        "documento_id": str(documento_id),
        "mensagem": "Documento, arquivo e embeddings removidos com sucesso",
    }
