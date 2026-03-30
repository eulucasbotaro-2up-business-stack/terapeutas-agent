"""
Indexar PDF Primus.pdf no RAG — usa httpx direto com Supabase REST API.
"""

import os
import sys
import time
import json
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
import httpx

TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

PDF_FILES = [
    Path(r"C:\Users\Lucas Botaro\Downloads\Primus.pdf"),
]

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_BATCH_SIZE = 100
DB_INSERT_BATCH_SIZE = 50

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

client = httpx.Client(timeout=60.0, verify=False)


def sb_get(table, params=""):
    r = client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def sb_insert(table, data):
    r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()


def sb_delete(table, params):
    r = client.delete(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=HEADERS)
    r.raise_for_status()
    return r


def sb_update(table, params, data):
    h = {**HEADERS, "Prefer": "return=representation"}
    r = client.patch(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=h, json=data)
    r.raise_for_status()
    return r.json()


def extrair_texto_pdf(caminho):
    doc = fitz.open(str(caminho))
    paginas = []
    for i, page in enumerate(doc):
        texto = page.get_text().replace("\x00", "")
        if texto.strip():
            paginas.append({"pagina": i + 1, "texto": texto})
    doc.close()
    return paginas


def criar_chunks(paginas, nome_arquivo):
    chunks = []
    idx = 0
    for pag in paginas:
        splits = text_splitter.split_text(pag["texto"])
        for split in splits:
            chunks.append({
                "conteudo": split,
                "chunk_index": idx,
                "metadata": {
                    "arquivo_fonte": nome_arquivo,
                    "pagina": pag["pagina"],
                    "tags": ["florais", "primus", "chakras", "zodiaco"],
                },
            })
            idx += 1
    return chunks


def gerar_embeddings_batch(textos):
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=textos)
    return [item.embedding for item in response.data]


def processar_pdf(caminho):
    nome = caminho.name
    tam = caminho.stat().st_size

    print(f"\n{'='*60}")
    print(f"  Processando: {nome} ({tam / 1024:.1f} KB)")
    print(f"{'='*60}")

    # Checar se ja existe
    existing = sb_get("documentos", f"terapeuta_id=eq.{TERAPEUTA_ID}&nome_arquivo=eq.{nome}&select=id")
    if existing:
        doc_id = existing[0]["id"]
        print(f"  Removendo dados antigos (id={doc_id})...")
        sb_delete("embeddings", f"documento_id=eq.{doc_id}")
        sb_delete("documentos", f"id=eq.{doc_id}")

    paginas = extrair_texto_pdf(caminho)
    print(f"  [1/5] {len(paginas)} paginas extraidas")

    if not paginas:
        print("  AVISO: PDF sem texto. Pulando.")
        return {"nome": nome, "chunks": 0}

    chunks = criar_chunks(paginas, nome)
    print(f"  [2/5] {len(chunks)} chunks criados")

    doc_id = str(uuid4())
    sb_insert("documentos", {
        "id": doc_id,
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": nome,
        "tipo": "pdf",
        "tamanho_bytes": tam,
        "storage_path": f"materiais/{TERAPEUTA_ID}/{nome}",
        "total_chunks": len(chunks),
        "processado": False,
        "status": "processando",
    })
    print(f"  [3/5] documento_id = {doc_id}")

    all_embeddings = []
    textos = [c["conteudo"] for c in chunks]
    for i in range(0, len(textos), EMBEDDING_BATCH_SIZE):
        batch = textos[i : i + EMBEDDING_BATCH_SIZE]
        embs = gerar_embeddings_batch(batch)
        all_embeddings.extend(embs)
        print(f"  [4/5] Lote {i // EMBEDDING_BATCH_SIZE + 1}: {len(batch)} embeddings")

    inserted = 0
    rows = []
    for chunk, emb in zip(chunks, all_embeddings):
        rows.append({
            "terapeuta_id": TERAPEUTA_ID,
            "documento_id": doc_id,
            "conteudo": chunk["conteudo"],
            "embedding": emb,
            "chunk_index": chunk["chunk_index"],
            "metadata": chunk["metadata"],
        })

    for i in range(0, len(rows), DB_INSERT_BATCH_SIZE):
        batch = rows[i : i + DB_INSERT_BATCH_SIZE]
        sb_insert("embeddings", batch)
        inserted += len(batch)
        print(f"  [5/5] Inseridos {inserted}/{len(rows)} chunks")

    sb_update("documentos", f"id=eq.{doc_id}", {"processado": True, "status": "ativo"})

    print(f"  CONCLUIDO: {nome} -> {len(chunks)} chunks indexados")
    return {"nome": nome, "chunks": len(chunks)}


def main():
    print("=" * 60)
    print("  INDEXACAO PDF PRIMUS - Florais Sutis")
    print("=" * 60)

    inicio = time.time()
    for pdf in PDF_FILES:
        if pdf.exists():
            processar_pdf(pdf)
        else:
            print(f"  Arquivo nao encontrado: {pdf}")

    print(f"\n  Tempo total: {time.time() - inicio:.1f}s")
    print("  Concluido!")


if __name__ == "__main__":
    main()
