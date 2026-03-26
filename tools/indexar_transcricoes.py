"""
Indexa transcrições do YouTube no Supabase pgvector para o sistema RAG.

Lê os arquivos .txt de materiais/youtube_transcricoes/, faz chunking,
gera embeddings com OpenAI e insere na tabela embeddings do Supabase.
"""

import os
import sys
import time
from pathlib import Path

# ── Env vars (carrega do .env) ──────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from supabase import create_client

# ── Configurações ──────────────────────────────────────────────
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"
TRANSCRICOES_DIR = Path(__file__).resolve().parent.parent / "materiais" / "youtube_transcricoes"

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_BATCH_SIZE = 100
DB_INSERT_BATCH_SIZE = 50

# ── Inicialização dos clientes ─────────────────────────────────
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── Text splitter ──────────────────────────────────────────────
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def listar_transcricoes() -> list[Path]:
    """Lista todos os .txt no diretório de transcrições."""
    if not TRANSCRICOES_DIR.exists():
        print(f"ERRO: Diretório não encontrado: {TRANSCRICOES_DIR}")
        sys.exit(1)

    arquivos = sorted(TRANSCRICOES_DIR.glob("*.txt"))
    print(f"Encontradas {len(arquivos)} transcrições em {TRANSCRICOES_DIR}")
    return arquivos


def extrair_nome_video(caminho: Path) -> str:
    """Extrai o título do vídeo a partir do cabeçalho do arquivo ou nome do arquivo."""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            primeira_linha = f.readline().strip()
            if primeira_linha.startswith("TITULO:"):
                return primeira_linha.replace("TITULO:", "").strip()
    except Exception:
        pass
    # Fallback: usa o nome do arquivo sem extensão
    return caminho.stem


def ler_conteudo(caminho: Path) -> str:
    """Lê o conteúdo de uma transcrição, removendo o cabeçalho de metadata."""
    with open(caminho, "r", encoding="utf-8") as f:
        texto = f.read()

    # Remove cabeçalho (TITULO:, VIDEO_ID:, FONTE:) se existir
    linhas = texto.split("\n")
    inicio = 0
    for i, linha in enumerate(linhas):
        if linha.startswith("TITULO:") or linha.startswith("VIDEO_ID:") or linha.startswith("FONTE:"):
            inicio = i + 1
        elif linha.strip() == "" and inicio > 0:
            inicio = i + 1
            break
        else:
            break

    conteudo = "\n".join(linhas[inicio:]).strip()
    return conteudo


def criar_chunks(texto: str, nome_video: str) -> list[dict]:
    """Divide o texto em chunks com metadata."""
    splits = text_splitter.split_text(texto)
    chunks = []
    for idx, split in enumerate(splits):
        chunks.append({
            "conteudo": split,
            "chunk_index": idx,
            "metadata": {
                "arquivo_fonte": f"YouTube - {nome_video}",
                "tipo": "transcricao_youtube",
            },
        })
    return chunks


def gerar_embeddings_batch(textos: list[str]) -> list[list[float]]:
    """Gera embeddings em lote usando OpenAI."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=textos,
    )
    return [item.embedding for item in response.data]


def processar_transcricao(caminho: Path) -> dict:
    """Processa uma única transcrição: lê, chunkeia, embeda e insere no Supabase."""
    nome_video = extrair_nome_video(caminho)
    arquivo_fonte = f"YouTube - {nome_video}"

    print(f"\n{'='*60}")
    print(f"  Processando: {nome_video}")
    print(f"{'='*60}")

    # 1. Ler conteúdo
    print("  [1/4] Lendo transcrição...")
    texto = ler_conteudo(caminho)
    if not texto or len(texto.strip()) < 50:
        print(f"  AVISO: Transcrição muito curta ({len(texto)} chars). Pulando.")
        return {"nome": nome_video, "status": "muito_curta", "chunks": 0}
    print(f"         {len(texto)} caracteres")

    # 2. Criar chunks
    print("  [2/4] Dividindo em chunks...")
    chunks = criar_chunks(texto, nome_video)
    print(f"         {len(chunks)} chunks criados")

    if not chunks:
        print("  AVISO: Nenhum chunk gerado. Pulando.")
        return {"nome": nome_video, "status": "sem_chunks", "chunks": 0}

    # 3. Gerar embeddings em lotes
    print("  [3/4] Gerando embeddings...")
    all_embeddings = []
    textos = [c["conteudo"] for c in chunks]
    for i in range(0, len(textos), EMBEDDING_BATCH_SIZE):
        batch = textos[i : i + EMBEDDING_BATCH_SIZE]
        embs = gerar_embeddings_batch(batch)
        all_embeddings.extend(embs)
        print(f"         Lote {i // EMBEDDING_BATCH_SIZE + 1}: {len(batch)} embeddings gerados")
    print(f"         Total: {len(all_embeddings)} embeddings")

    # 4. Inserir no Supabase (sem criar registro em documentos, direto nos embeddings)
    print("  [4/4] Inserindo no Supabase...")
    rows = []
    for chunk, emb in zip(chunks, all_embeddings):
        rows.append({
            "terapeuta_id": TERAPEUTA_ID,
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

    print(f"  CONCLUIDO: {nome_video} -> {len(chunks)} chunks indexados")
    return {"nome": nome_video, "status": "ok", "chunks": len(chunks)}


def main():
    print("=" * 60)
    print("  INDEXADOR DE TRANSCRIÇÕES YOUTUBE -> SUPABASE")
    print(f"  Terapeuta: {TERAPEUTA_ID}")
    print("=" * 60)

    # Listar transcrições
    arquivos = listar_transcricoes()

    if not arquivos:
        print("Nenhuma transcrição encontrada.")
        return

    # Processar cada transcrição
    resultados = []
    total_chunks = 0

    for i, arquivo in enumerate(arquivos):
        print(f"\n>>> [{i+1}/{len(arquivos)}] {arquivo.name}")
        try:
            resultado = processar_transcricao(arquivo)
            resultados.append(resultado)
            total_chunks += resultado["chunks"]
        except Exception as e:
            print(f"  ERRO ao processar {arquivo.name}: {e}")
            resultados.append({"nome": arquivo.name, "status": "erro", "chunks": 0})

        # Pequena pausa entre arquivos para não sobrecarregar a API
        time.sleep(0.3)

    # Relatório final
    print("\n" + "=" * 60)
    print("  RELATÓRIO FINAL")
    print("=" * 60)
    ok = [r for r in resultados if r["status"] == "ok"]
    erros = [r for r in resultados if r["status"] == "erro"]
    pulados = [r for r in resultados if r["status"] not in ("ok", "erro")]

    print(f"  Total de transcrições: {len(arquivos)}")
    print(f"  Indexadas com sucesso: {len(ok)}")
    print(f"  Puladas: {len(pulados)}")
    print(f"  Erros: {len(erros)}")
    print(f"  Total de chunks criados: {total_chunks}")

    if erros:
        print("\n  Transcrições com erro:")
        for r in erros:
            print(f"    - {r['nome']}")

    if pulados:
        print("\n  Transcrições puladas:")
        for r in pulados:
            print(f"    - {r['nome']} ({r['status']})")


if __name__ == "__main__":
    main()
