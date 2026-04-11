"""
OCR do PDF "A Aura das Flores" usando Claude Vision API.

Renderiza cada página como imagem e envia para Claude Haiku
extrair o texto em português. Resultado salvo em knowledge_base/02_florais/.
"""

import asyncio
import base64
import io
import json
import os
import sys
import time

import anthropic
import fitz  # PyMuPDF

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.config import get_settings

PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "materiais", "material Joel Aleixo", "A Aura das flores.pdf"
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base", "02_florais"
)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "kit_primus_99_flores_ocr.md")

# Claude Haiku para custo baixo (~$0.50 para 159 páginas)
MODEL = "claude-haiku-4-5-20251001"
DPI = 200  # Balanceio qualidade vs custo
MAX_CONCURRENT = 5  # Paralelismo nas chamadas


def render_page_to_base64(doc, page_num: int) -> str:
    """Renderiza uma página do PDF como PNG base64."""
    page = doc[page_num]
    # Render at specified DPI
    zoom = DPI / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pix.tobytes("png")
    return base64.standard_b64encode(img_bytes).decode("utf-8")


async def extract_text_from_page(client, page_b64: str, page_num: int) -> str:
    """Envia imagem para Claude e extrai texto."""
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": page_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extraia TODO o texto desta pagina de livro em portugues brasileiro. "
                            "Mantenha a formatacao original (titulos, paragrafos, listas). "
                            "Se houver nomes de florais, mantenha a grafia exata. "
                            "Retorne APENAS o texto extraido, sem comentarios."
                        ),
                    },
                ],
            }],
        )
        text = response.content[0].text.strip()
        return text
    except Exception as e:
        return f"[ERRO OCR pagina {page_num + 1}: {e}]"


async def process_batch(client, doc, page_nums: list[int], results: dict):
    """Processa um lote de páginas em paralelo."""
    tasks = []
    for pn in page_nums:
        b64 = render_page_to_base64(doc, pn)
        tasks.append(extract_text_from_page(client, b64, pn))

    batch_results = await asyncio.gather(*tasks)
    for pn, text in zip(page_nums, batch_results):
        results[pn] = text
        status = "OK" if not text.startswith("[ERRO") else "ERRO"
        print(f"  Pag {pn + 1:3d}/159 [{status}] {len(text)} chars")


async def main():
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    print(f"PDF: {PDF_PATH}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Modelo: {MODEL}")
    print(f"DPI: {DPI}")
    print()

    doc = fitz.open(PDF_PATH)
    total_pages = doc.page_count
    print(f"Total de paginas: {total_pages}")
    print(f"Processando em lotes de {MAX_CONCURRENT}...\n")

    results = {}
    all_pages = list(range(total_pages))

    for i in range(0, len(all_pages), MAX_CONCURRENT):
        batch = all_pages[i:i + MAX_CONCURRENT]
        print(f"Lote {i // MAX_CONCURRENT + 1}/{(len(all_pages) + MAX_CONCURRENT - 1) // MAX_CONCURRENT}:")
        await process_batch(client, doc, batch, results)
        # Rate limiting
        if i + MAX_CONCURRENT < len(all_pages):
            await asyncio.sleep(1)

    doc.close()

    # Monta o markdown final
    print(f"\nMontando arquivo final...")

    md_content = """---
id: kit_primus_99_flores
titulo: "A Aura das Flores - Kit Primus 99 Florais Sutis"
categoria: florais
fonte_original: "A Aura das flores.pdf"
total_paginas: {total}
tags: ["florais", "kit primus", "florais sutis", "aura das flores", "99 flores"]
ocr_modelo: "{model}"
ocr_data: "{date}"
---

# A Aura das Flores — Kit Primus (99 Florais Sutis)

> Fonte original: `A Aura das flores.pdf` ({total} paginas)
> OCR realizado via {model}

---

""".format(total=total_pages, model=MODEL, date=time.strftime("%Y-%m-%d"))

    for pn in sorted(results.keys()):
        text = results[pn]
        md_content += f"\n## Pagina {pn + 1}\n\n{text}\n\n---\n"

    # Salva
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)

    total_chars = sum(len(results[k]) for k in results)
    erros = sum(1 for k in results if results[k].startswith("[ERRO"))

    print(f"\nOCR CONCLUIDO!")
    print(f"Paginas processadas: {len(results)}")
    print(f"Erros: {erros}")
    print(f"Total caracteres: {total_chars:,}")
    print(f"Arquivo salvo: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
