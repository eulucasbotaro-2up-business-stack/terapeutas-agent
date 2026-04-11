"""
Indexa a base de conhecimento oficial da metodologia AlkhemyLab/Joel Aleixo no RAG.

Lê os arquivos Markdown da pasta knowledge_base/ (extraídos dos PDFs originais por _extrator.py)
e faz upload para o Supabase como embeddings associados ao terapeuta Joel Aleixo.

Uso:
    python scripts/indexar_base_alkhemylab.py

Ou no Railway:
    railway run python scripts/indexar_base_alkhemylab.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Adiciona o root do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.rag.processor import dividir_em_chunks, gerar_embeddings, salvar_chunks_no_supabase
import uuid

# Terapeuta Joel Aleixo — ID fixo de produção
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

# Pasta raiz da base de conhecimento
KB_ROOT = Path(__file__).parent.parent / "knowledge_base"

# Arquivos a indexar: (caminho_relativo, titulo_para_o_banco)
ARQUIVOS = [
    # Florais — placeholder enquanto o OCR do "A Aura das Flores" está pendente
    ("02_florais/kit_primus_status.md", "Kit Primus — Status e Princípios (A Aura das Flores)"),

    # Protocolos clínicos
    ("03_protocolos/como_usar_protocolos.md", "Protocolos AlkhemyLab — Como Usar"),

    # Fundamentos teóricos
    ("04_fundamentos/4_elementos_pletora.md", "Quatro Elementos e Pletora"),
    ("04_fundamentos/7_chakras_aprofundamento.md", "Aprofundamento nos 7 Chakras"),
    ("04_fundamentos/dna_heranca_energetica.md", "DNA — Herança Energética"),
    ("04_fundamentos/matrix_e_traumas.md", "Matrix e Traumas"),
    ("04_fundamentos/astrologia.md", "Astrologia Aplicada ao Sistema AlkhemyLab"),

    # Apostilas
    ("05_apostilas/fluxus_continuum_john_dee.md", "O Fluxus Continuum de John Dee"),

    # FAQ
    ("06_faq/faq_geral.md", "FAQ Geral — Compostos e Florais Sutis"),
    ("06_faq/faq_4_elementos_pletora.md", "FAQ — 4 Elementos e Pletora"),
]


def criar_documento_no_banco(titulo: str, tamanho_bytes: int) -> str:
    """Cria registro na tabela documentos e retorna o ID."""
    supabase = get_supabase()
    doc_id = str(uuid.uuid4())

    supabase.table("documentos").insert({
        "id": doc_id,
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": titulo,
        "tipo": "pdf",
        "tamanho_bytes": tamanho_bytes,
        "storage_path": f"knowledge_base/{doc_id}.md",
        "total_chunks": 0,
        "processado": True,
    }).execute()

    print(f"  [+] Documento criado: {doc_id} — {titulo}")
    return doc_id


def remover_documento_antigo(titulo: str) -> None:
    """Remove documento e chunks anteriores com o mesmo título."""
    supabase = get_supabase()

    resultado = (
        supabase.table("documentos")
        .select("id")
        .eq("terapeuta_id", TERAPEUTA_ID)
        .eq("nome_arquivo", titulo)
        .execute()
    )

    for doc in resultado.data:
        doc_id = doc["id"]
        supabase.table("embeddings").delete().eq("documento_id", doc_id).execute()
        supabase.table("documentos").delete().eq("id", doc_id).execute()
        print(f"  [-] Removido documento anterior: {doc_id}")


async def indexar_arquivo(caminho_rel: str, titulo: str) -> None:
    """Lê um arquivo markdown, chunka e indexa no Supabase."""
    caminho = KB_ROOT / caminho_rel

    if not caminho.exists():
        print(f"  [!] ARQUIVO NÃO ENCONTRADO: {caminho}")
        return

    conteudo = caminho.read_text(encoding="utf-8")
    # Remove null bytes que o PostgreSQL não aceita (artefatos de extração de PDF)
    conteudo = conteudo.replace("\x00", "")
    tamanho = len(conteudo.encode("utf-8"))

    print(f"\n{'='*60}")
    print(f"Indexando: {titulo}")
    print(f"Arquivo: {caminho_rel} ({tamanho:,} bytes)")
    print(f"{'='*60}")

    # Remove versão anterior
    remover_documento_antigo(titulo)

    # Cria novo documento
    doc_id = criar_documento_no_banco(titulo, tamanho)

    # Chunking
    chunks = dividir_em_chunks(conteudo)
    print(f"  [+] {len(chunks)} chunks gerados")

    # Embeddings
    print(f"  [~] Gerando embeddings...")
    embeddings = await gerar_embeddings(chunks)
    print(f"  [+] {len(embeddings)} embeddings gerados")

    # Salva no Supabase
    total = await salvar_chunks_no_supabase(chunks, embeddings, TERAPEUTA_ID, doc_id)
    print(f"  [+] {total} chunks salvos")


async def main():
    settings = get_settings()
    print(f"\nConectando ao Supabase: {settings.SUPABASE_URL[:40]}...")
    print(f"Terapeuta ID: {TERAPEUTA_ID}")
    print(f"Base de conhecimento: {KB_ROOT}")
    print(f"\nTotal de arquivos a indexar: {len(ARQUIVOS)}")

    total_chunks = 0
    erros = []

    for caminho_rel, titulo in ARQUIVOS:
        try:
            await indexar_arquivo(caminho_rel, titulo)
        except Exception as e:
            print(f"  [ERRO] {titulo}: {e}")
            erros.append((titulo, str(e)))

    print(f"\n{'='*60}")
    print(f"INDEXAÇÃO CONCLUÍDA!")
    print(f"Arquivos processados: {len(ARQUIVOS) - len(erros)}/{len(ARQUIVOS)}")
    if erros:
        print(f"\nErros ({len(erros)}):")
        for titulo, erro in erros:
            print(f"  - {titulo}: {erro}")
    print(f"{'='*60}")

    print("\n[!] ATENCAO — Kit Primus (A Aura das Flores) esta PENDENTE de OCR.")
    print("    Veja knowledge_base/PENDENCIAS_OCR.md para instrucoes.")
    print("    Ate la, o agente usara os principios gerais do Kit Primus.")


if __name__ == "__main__":
    asyncio.run(main())
