"""
Pesquisa vetorial nos materiais da Escola de Alquimia do Joel Aleixo.
"""

import os
import json
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from openai import OpenAI
from supabase import create_client

TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"
EMBEDDING_MODEL = "text-embedding-3-small"

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def gerar_embedding(texto: str) -> list[float]:
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texto)
    return response.data[0].embedding


def buscar(query: str, top_k: int = 15) -> list[dict]:
    emb = gerar_embedding(query)
    resultado = supabase.rpc(
        "buscar_chunks",
        {
            "query_embedding": emb,
            "p_terapeuta_id": TERAPEUTA_ID,
            "match_count": top_k,
        },
    ).execute()
    return resultado.data or []


queries = [
    "DNA alquimico 7 cores significado vermelho laranja amarelo verde azul indigo violeta",
    "DNA alquimico cor vermelha base chakra raiz terra pai significado",
    "DNA alquimico cor laranja esplenico segundo chakra sacral significado",
    "DNA alquimico cor amarela plexo solar familia ligacoes significado",
    "DNA alquimico cor verde coracao quarto chakra significado",
    "DNA alquimico cor azul garganta quinto chakra comunicacao significado",
    "DNA alquimico cor indigo sexto chakra terceiro olho intuicao significado",
    "DNA alquimico cor violeta setimo chakra coronario espiritualidade significado",
    "chakras alquimia significado cada chakra Joel Aleixo",
    "sete chakras corpo energetico bloqueio desbloqueio",
    "dificuldade financeira falta de terra ausencia pai DNA vermelho causa alquimica",
    "relacao doenca causa alquimica sintoma significado emocional",
    "problema emocional causa raiz alquimica diagnostico",
    "multiplas causas alquimicas doenca varias origens",
    "Matrix alquimica diagnostico mapeamento o que e",
    "matrix alquimia Joel ferramenta analise",
    "Vitriol alquimia conceito significado aplicacao",
    "VITRIOL visita interior terrae",
    "Fluxus Continuum conceito alquimia significado",
    "fluxus continuum fluxo continuo energia",
    "florais astrologicos tratamento alquimico indicacao",
    "florais sutis quanticos tratamento",
    "florais quatro elementos terra agua fogo ar tratamento",
    "tratamento alquimico tipos formas floral essencia",
    "elementos terra agua fogo ar significado alquimia",
    "diagnostico alquimico como fazer mapeamento paciente",
    "escola alquimia Joel Aleixo metodo tecnica",
    "DNA volatil morbido doencas significado",
    "DNA fixo estavel significado alquimia",
    "setenios ativacao chakras DNA ritmo ciclo vida",
    "enxofre sal mercurio tres principios alquimia tria prima",
    "aura corpo energetico camadas cores vibracao",
]

if __name__ == "__main__":
    all_results = {}
    for i, q in enumerate(queries):
        sys.stderr.write(f"[{i+1}/{len(queries)}] {q[:60]}...\n")
        sys.stderr.flush()
        chunks = buscar(q, top_k=12)
        all_results[q] = chunks
        time.sleep(0.3)

    output_path = Path(__file__).resolve().parent.parent / "materiais" / "pesquisa_bruta.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"\nSalvo em: {output_path}\n")
    sys.stderr.write(f"Total queries: {len(all_results)}\n")
    total_chunks = sum(len(v) for v in all_results.values())
    sys.stderr.write(f"Total chunks: {total_chunks}\n")
