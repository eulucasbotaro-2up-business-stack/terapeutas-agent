"""
Baixa todas as transcrições do canal do Joel Aleixo no YouTube
e salva em arquivos para indexação no RAG.
"""

import json
import os
import time
from pathlib import Path

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Diretório para salvar as transcrições
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "materiais" / "youtube_transcricoes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNEL_URL = "https://www.youtube.com/@alquimistajoelaleixo"
CHANNEL_HANDLE = "alquimistajoelaleixo"


def listar_videos():
    """Lista todos os vídeos do canal."""
    print(f"Buscando videos do canal @{CHANNEL_HANDLE}...")
    videos = list(scrapetube.get_channel(channel_url=CHANNEL_URL))
    print(f"Encontrados {len(videos)} videos.")
    return videos


def baixar_transcricao(video_id: str, titulo: str) -> str | None:
    """Baixa a transcrição de um vídeo."""
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=["pt", "pt-BR", "en"])
        formatter = TextFormatter()
        texto = formatter.format_transcript(transcript)
        return texto
    except Exception as e:
        print(f"  Sem transcricao: {titulo[:50]} - {e}")
        return None


def main():
    videos = listar_videos()

    total = 0
    erros = 0

    for i, video in enumerate(videos):
        video_id = video["videoId"]
        titulo = video.get("title", {}).get("runs", [{}])[0].get("text", f"video_{video_id}")

        # Nome do arquivo seguro
        nome_seguro = "".join(c if c.isalnum() or c in " -_" else "" for c in titulo)[:80]
        arquivo = OUTPUT_DIR / f"{nome_seguro}.txt"

        # Pular se já existe
        if arquivo.exists():
            print(f"  [{i+1}/{len(videos)}] Ja existe: {titulo[:50]}")
            total += 1
            continue

        print(f"  [{i+1}/{len(videos)}] Baixando: {titulo[:50]}...")
        texto = baixar_transcricao(video_id, titulo)

        if texto:
            # Salvar com metadata
            conteudo = f"TITULO: {titulo}\nVIDEO_ID: {video_id}\nFONTE: YouTube - Joel Aleixo\n\n{texto}"
            arquivo.write_text(conteudo, encoding="utf-8")
            total += 1
        else:
            erros += 1

        # Rate limiting
        time.sleep(0.5)

    print(f"\nConcluido! {total} transcricoes salvas, {erros} sem transcricao.")
    print(f"Diretorio: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
