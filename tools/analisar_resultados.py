"""Analisa resultados da pesquisa vetorial e gera output em UTF-8."""

import json
from pathlib import Path

with open(Path(__file__).resolve().parent.parent / "materiais" / "pesquisa_bruta.json", "r", encoding="utf-8") as f:
    data = json.load(f)

output_lines = []
seen = set()

for query, chunks in data.items():
    output_lines.append(f"\n===== QUERY: {query} =====\n")
    for c in chunks:
        content = c.get("conteudo", "")
        sim = c.get("similaridade", 0)
        key = content[:120]
        if key not in seen and sim >= 0.30:
            seen.add(key)
            output_lines.append(f"\n[sim={sim:.3f}]")
            output_lines.append(content)
            output_lines.append("---")

out_path = Path(__file__).resolve().parent.parent / "materiais" / "pesquisa_analise.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print(f"Salvo: {out_path} ({len(seen)} chunks unicos)")
