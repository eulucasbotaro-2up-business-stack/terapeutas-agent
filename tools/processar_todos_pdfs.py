"""
Script standalone para processar TODOS os PDFs da Escola de Alquimia Joel Aleixo.
Extrai texto, gera embeddings e indexa no Supabase para RAG.
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from supabase import create_client

# ── Configurações ──────────────────────────────────────────────
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"
PDF_DIR = Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\material Joel Aleixo")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_BATCH_SIZE = 100
DB_INSERT_BATCH_SIZE = 50

# ── Inicialização dos clientes ─────────────────────────────────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def extrair_texto_pdf(caminho: Path) -> list[dict]:
    """Extrai texto de cada página do PDF. Retorna lista de {pagina, texto}."""
    doc = fitz.open(str(caminho))
    paginas = []
    for i, page in enumerate(doc):
        texto = page.get_text()
        # Remover caracteres nulos que causam erro no PostgreSQL
        texto = texto.replace("\x00", "")
        if texto.strip():
            paginas.append({"pagina": i + 1, "texto": texto})
    doc.close()
    return paginas


def criar_chunks(paginas: list[dict], nome_arquivo: str) -> list[dict]:
    """Divide o texto em chunks e mantém metadata (página)."""
    chunks = []
    chunk_index = 0
    for pag in paginas:
        splits = text_splitter.split_text(pag["texto"])
        for split in splits:
            chunks.append({
                "conteudo": split,
                "chunk_index": chunk_index,
                "metadata": {
                    "nome_arquivo": nome_arquivo,
                    "pagina": pag["pagina"],
                },
            })
            chunk_index += 1
    return chunks


def gerar_embeddings_batch(textos: list[str]) -> list[list[float]]:
    """Gera embeddings em lote usando OpenAI."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=textos,
    )
    return [item.embedding for item in response.data]


def processar_pdf(caminho: Path) -> dict:
    """Processa um único PDF: extrai, chunkeia, embeda e insere no Supabase."""
    nome_arquivo = caminho.name
    tamanho_bytes = caminho.stat().st_size

    print(f"\n{'='*60}")
    print(f"  Processando: {nome_arquivo}")
    print(f"  Tamanho: {tamanho_bytes / 1024:.1f} KB")
    print(f"{'='*60}")

    # 1. Extrair texto
    print("  [1/5] Extraindo texto do PDF...")
    paginas = extrair_texto_pdf(caminho)
    texto_total = sum(len(p["texto"]) for p in paginas)
    print(f"         {len(paginas)} páginas, {texto_total} caracteres")

    if not paginas:
        print("  AVISO: PDF sem texto extraível. Pulando.")
        return {"nome": nome_arquivo, "status": "sem_texto", "chunks": 0}

    # 2. Criar chunks
    print("  [2/5] Dividindo em chunks...")
    chunks = criar_chunks(paginas, nome_arquivo)
    print(f"         {len(chunks)} chunks criados")

    # 3. Criar registro do documento no Supabase
    print("  [3/5] Registrando documento no Supabase...")
    doc_data = {
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": nome_arquivo,
        "tipo": "pdf",
        "tamanho_bytes": tamanho_bytes,
        "storage_path": f"materiais/{TERAPEUTA_ID}/{nome_arquivo}",
        "total_chunks": len(chunks),
        "processado": False,
        "status": "processando",
    }
    doc_result = supabase.table("documentos").insert(doc_data).execute()
    documento_id = doc_result.data[0]["id"]
    print(f"         documento_id = {documento_id}")

    # 4. Gerar embeddings em lotes
    print("  [4/5] Gerando embeddings...")
    all_embeddings = []
    textos = [c["conteudo"] for c in chunks]
    for i in range(0, len(textos), EMBEDDING_BATCH_SIZE):
        batch = textos[i : i + EMBEDDING_BATCH_SIZE]
        embs = gerar_embeddings_batch(batch)
        all_embeddings.extend(embs)
        print(f"         Lote {i // EMBEDDING_BATCH_SIZE + 1}: {len(batch)} embeddings gerados")
    print(f"         Total: {len(all_embeddings)} embeddings")

    # 5. Inserir chunks + embeddings no Supabase em lotes
    print("  [5/5] Inserindo no Supabase...")
    rows = []
    for chunk, emb in zip(chunks, all_embeddings):
        rows.append({
            "terapeuta_id": TERAPEUTA_ID,
            "documento_id": documento_id,
            "conteudo": chunk["conteudo"],
            "embedding": emb,
            "chunk_index": chunk["chunk_index"],
            "metadata": chunk["metadata"],
        })

    inserted = 0
    for i in range(0, len(rows), DB_INSERT_BATCH_SIZE):
        batch = rows[i : i + DB_INSERT_BATCH_SIZE]
        supabase.table("embeddings").insert(batch).execute()
        inserted += len(batch)
        print(f"         Inseridos {inserted}/{len(rows)} chunks")

    # 6. Atualizar status do documento
    supabase.table("documentos").update({
        "processado": True,
        "status": "ativo",
    }).eq("id", documento_id).execute()

    print(f"  CONCLUIDO: {nome_arquivo} -> {len(chunks)} chunks indexados")
    return {"nome": nome_arquivo, "status": "ok", "chunks": len(chunks)}


def main():
    print("=" * 60)
    print("  PROCESSAMENTO DE PDFs - Escola de Alquimia Joel Aleixo")
    print(f"  Terapeuta ID: {TERAPEUTA_ID}")
    print(f"  Diretório: {PDF_DIR}")
    print("=" * 60)

    # Listar PDFs (excluir .docx)
    pdfs = sorted([f for f in PDF_DIR.iterdir() if f.suffix.lower() == ".pdf"])
    print(f"\nEncontrados {len(pdfs)} PDFs para processar:\n")
    for i, pdf in enumerate(pdfs, 1):
        print(f"  {i:2d}. {pdf.name}")

    # Processar cada PDF
    resultados = []
    total_chunks = 0
    erros = 0
    inicio = time.time()

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n>>> [{i}/{len(pdfs)}] {pdf.name}")
        try:
            resultado = processar_pdf(pdf)
            resultados.append(resultado)
            total_chunks += resultado["chunks"]
        except Exception as e:
            print(f"  ERRO ao processar {pdf.name}: {e}")
            traceback.print_exc()
            resultados.append({"nome": pdf.name, "status": "erro", "chunks": 0, "erro": str(e)})
            erros += 1

    # Resumo final
    elapsed = time.time() - inicio
    print("\n" + "=" * 60)
    print("  RESUMO FINAL")
    print("=" * 60)
    print(f"  Total de PDFs processados: {len(pdfs)}")
    print(f"  Sucesso: {len(pdfs) - erros}")
    print(f"  Erros: {erros}")
    print(f"  Total de chunks criados: {total_chunks}")
    print(f"  Tempo total: {elapsed:.1f} segundos")
    print()

    for r in resultados:
        status_icon = "OK" if r["status"] == "ok" else ("VAZIO" if r["status"] == "sem_texto" else "ERRO")
        print(f"  [{status_icon:5s}] {r['nome']} -> {r['chunks']} chunks")
        if r.get("erro"):
            print(f"          Erro: {r['erro']}")

    print("\n" + "=" * 60)
    print("  Processamento concluído!")
    print("=" * 60)


if __name__ == "__main__":
    main()
