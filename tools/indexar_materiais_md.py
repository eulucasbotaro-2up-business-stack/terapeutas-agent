"""
Script para indexar arquivos .md de materiais (NotebookLM) no Supabase.
Faz chunking, gera embeddings e insere na tabela embeddings.
"""

import os
import sys
import time
import traceback
from pathlib import Path

# ── Env vars ──────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from supabase import create_client

# ── Configurações ──────────────────────────────────────────────
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

# Arquivos .md para indexar e seus nomes amigáveis
MATERIAIS = [
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\joel_voz_youtube.md"),
        "fonte": "NotebookLM - Voz e Estilo do Joel",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_florais.md"),
        "fonte": "NotebookLM - Tipos de Florais Alquimicos",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\mapeamento_diagnostico.md"),
        "fonte": "NotebookLM - Mapeamento Diagnostico Alquimico",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_diagnostico.md"),
        "fonte": "NotebookLM - Como Joel Diagnostica",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_matrix_heranca.md"),
        "fonte": "NotebookLM - Matrix e Heranca Ancestral",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_sintomas_causas.md"),
        "fonte": "NotebookLM - Tabela Sintomas e Causas Alquimicas",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_rodada2.md"),
        "fonte": "NotebookLM - Conhecimento Avancado Joel",
    },
    {
        "caminho": Path(r"C:\Users\VENDATECH01\Desktop\terapeutas-agent\materiais\notebooklm_rodada3.md"),
        "fonte": "NotebookLM - Conhecimento Especializado Joel",
    },
]

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_BATCH_SIZE = 100
DB_INSERT_BATCH_SIZE = 50

# ── Clientes ──────────────────────────────────────────────────
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def gerar_embeddings_batch(textos: list[str]) -> list[list[float]]:
    """Gera embeddings em lote usando OpenAI."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=textos,
    )
    return [item.embedding for item in response.data]


def processar_md(caminho: Path, fonte: str) -> dict:
    """Processa um arquivo .md: lê, chunkeia, embeda e insere no Supabase."""
    nome_arquivo = caminho.name
    tamanho_bytes = caminho.stat().st_size

    print(f"\n{'='*60}")
    print(f"  Processando: {nome_arquivo}")
    print(f"  Fonte: {fonte}")
    print(f"  Tamanho: {tamanho_bytes / 1024:.1f} KB")
    print(f"{'='*60}")

    # 1. Ler conteudo do .md
    print("  [1/5] Lendo arquivo .md...")
    texto = caminho.read_text(encoding="utf-8")
    # Remover caracteres nulos
    texto = texto.replace("\x00", "")
    print(f"         {len(texto)} caracteres")

    if not texto.strip():
        print("  AVISO: Arquivo vazio. Pulando.")
        return {"nome": nome_arquivo, "fonte": fonte, "status": "vazio", "chunks": 0}

    # 2. Criar chunks
    print("  [2/5] Dividindo em chunks...")
    splits = text_splitter.split_text(texto)
    chunks = []
    for i, split in enumerate(splits):
        chunks.append({
            "conteudo": split,
            "chunk_index": i,
            "metadata": {
                "arquivo_fonte": fonte,
                "tipo_fonte": "notebooklm_md",
            },
        })
    print(f"         {len(chunks)} chunks criados")

    # 3. Registrar documento no Supabase
    print("  [3/5] Registrando documento no Supabase...")
    doc_data = {
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": fonte,
        "tipo": "md",
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
    textos_chunks = [c["conteudo"] for c in chunks]
    for i in range(0, len(textos_chunks), EMBEDDING_BATCH_SIZE):
        batch = textos_chunks[i : i + EMBEDDING_BATCH_SIZE]
        embs = gerar_embeddings_batch(batch)
        all_embeddings.extend(embs)
        print(f"         Lote {i // EMBEDDING_BATCH_SIZE + 1}: {len(batch)} embeddings gerados")
    print(f"         Total: {len(all_embeddings)} embeddings")

    # 5. Inserir chunks + embeddings no Supabase
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

    print(f"  CONCLUIDO: {fonte} -> {len(chunks)} chunks indexados")
    return {"nome": nome_arquivo, "fonte": fonte, "status": "ok", "chunks": len(chunks)}


def main():
    print("=" * 60)
    print("  INDEXACAO DE MATERIAIS .MD (NotebookLM)")
    print(f"  Terapeuta ID: {TERAPEUTA_ID}")
    print("=" * 60)

    # Verificar arquivos
    print("\nVerificando arquivos...\n")
    for m in MATERIAIS:
        existe = "OK" if m["caminho"].exists() else "NAO ENCONTRADO"
        print(f"  [{existe}] {m['caminho'].name} -> {m['fonte']}")

    # Processar cada arquivo
    resultados = []
    total_chunks = 0
    erros = 0
    inicio = time.time()

    for i, material in enumerate(MATERIAIS, 1):
        if not material["caminho"].exists():
            print(f"\n  PULANDO: {material['caminho'].name} (nao encontrado)")
            resultados.append({"nome": material["caminho"].name, "fonte": material["fonte"], "status": "nao_encontrado", "chunks": 0})
            erros += 1
            continue

        print(f"\n>>> [{i}/{len(MATERIAIS)}] {material['caminho'].name}")
        try:
            resultado = processar_md(material["caminho"], material["fonte"])
            resultados.append(resultado)
            total_chunks += resultado["chunks"]
        except Exception as e:
            print(f"  ERRO ao processar {material['caminho'].name}: {e}")
            traceback.print_exc()
            resultados.append({"nome": material["caminho"].name, "fonte": material["fonte"], "status": "erro", "chunks": 0, "erro": str(e)})
            erros += 1

    # Resumo final
    elapsed = time.time() - inicio
    print("\n" + "=" * 60)
    print("  RESUMO FINAL")
    print("=" * 60)
    print(f"  Total de arquivos: {len(MATERIAIS)}")
    print(f"  Sucesso: {len(MATERIAIS) - erros}")
    print(f"  Erros: {erros}")
    print(f"  Total de chunks criados: {total_chunks}")
    print(f"  Tempo total: {elapsed:.1f} segundos")
    print()

    for r in resultados:
        status_icon = "OK" if r["status"] == "ok" else ("VAZIO" if r["status"] == "vazio" else "ERRO")
        print(f"  [{status_icon:5s}] {r['fonte']} -> {r['chunks']} chunks")
        if r.get("erro"):
            print(f"          Erro: {r['erro']}")

    print("\n" + "=" * 60)
    print("  Indexacao concluida!")
    print("=" * 60)


if __name__ == "__main__":
    main()
