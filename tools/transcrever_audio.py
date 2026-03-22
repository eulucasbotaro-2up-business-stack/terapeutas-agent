"""
Ferramenta de transcrição de áudio usando OpenAI Whisper API.
Uso: python transcrever_audio.py <arquivo_audio> [arquivo2] [arquivo3] ...
"""
import sys
import os
from openai import OpenAI

# Chave da API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

def transcrever(caminho_audio):
    """Transcreve um arquivo de áudio usando Whisper API"""
    print(f"\n{'='*60}")
    print(f"Transcrevendo: {os.path.basename(caminho_audio)}")
    print(f"{'='*60}")

    with open(caminho_audio, "rb") as audio_file:
        transcricao = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt",
            response_format="text"
        )

    print(transcricao)
    return transcricao

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python transcrever_audio.py <arquivo1> [arquivo2] ...")
        sys.exit(1)

    resultados = []
    for arquivo in sys.argv[1:]:
        texto = transcrever(arquivo)
        resultados.append({"arquivo": arquivo, "texto": texto})

    # Salva resultado em arquivo
    with open("transcricoes.txt", "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(f"\n{'='*60}\n")
            f.write(f"Arquivo: {os.path.basename(r['arquivo'])}\n")
            f.write(f"{'='*60}\n")
            f.write(r["texto"] + "\n")

    print(f"\n\nTranscrições salvas em transcricoes.txt")
