"""
Script de seed: insere 5 Mapas Alquimicos para pacientes demo.
Usa mapa_json para armazenar o tipo e dados alquimicos.

Uso: python scripts/seed_mapas_alquimicos.py
"""

import json
import uuid
import requests

SUPABASE_URL = "https://vtcjuaiuyjizkuyqfhtj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ0Y2p1YWl1eWppemt1eXFmaHRqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE4Mzk4OCwiZXhwIjoyMDg5NzU5OTg4fQ.Ie1RAfW4TBFX1GKB2_5vTUKCpVV6SWWW1qa5bJoYetQ"
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def api_post(table, data):
    """Insere dados no Supabase via REST API."""
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    if r.status_code not in (200, 201):
        print(f"  ERRO em {table}: {r.status_code} - {r.text}")
        return None
    return r.json()


def main():
    print("=== Seed: Mapas Alquimicos ===\n")

    # 5 pacientes que ja existem no seed demo
    # hora_nascimento diferente do Mapa Natal para evitar unique constraint
    # (terapeuta_id, numero_telefone, data_nascimento, hora_nascimento)
    pacientes = [
        {
            "tel": "5511900000001",
            "nome": "Ana Carolina",
            "data_nasc": "1989-03-15",
            "hora_nasc": "08:31",
            "cidade": "Sao Paulo, SP",
            "mapa_alquimico": {
                "tipo": "Mapa Alquimico",
                "elemento_dominante": "Fogo",
                "elemento_carente": "Agua",
                "dna_comprometido": "Linhagem paterna — padroes de raiva reprimida e dificuldade de expressao emocional",
                "serpentes_ativas": [
                    "Serpente da Impaciencia — ativacao cronica no plexo solar",
                    "Serpente do Controle — tensao constante nos ombros e nuca",
                ],
                "setenio": "5o Setenio (28-35 anos) — fase de individuacao e proposito",
                "fase_alquimica": "Calcinatio — processo de purificacao pelo fogo interior",
            },
        },
        {
            "tel": "5511900000003",
            "nome": "Juliana",
            "data_nasc": "1982-11-08",
            "hora_nasc": "10:16",
            "cidade": "Rio de Janeiro, RJ",
            "mapa_alquimico": {
                "tipo": "Mapa Alquimico",
                "elemento_dominante": "Agua",
                "elemento_carente": "Terra",
                "dna_comprometido": "Linhagem materna — padroes de codependencia e anulacao de si mesma",
                "serpentes_ativas": [
                    "Serpente da Culpa — ativacao no peito e garganta",
                    "Serpente do Abandono — medo cronico de rejeicao, tensao no estomago",
                ],
                "setenio": "6o Setenio (35-42 anos) — fase de maturidade e colheita",
                "fase_alquimica": "Solutio — dissolucao de velhos padroes emocionais pela agua",
            },
        },
        {
            "tel": "5511900000005",
            "nome": "Beatriz",
            "data_nasc": "1997-06-12",
            "hora_nasc": "14:01",
            "cidade": "Belo Horizonte, MG",
            "mapa_alquimico": {
                "tipo": "Mapa Alquimico",
                "elemento_dominante": "Ar",
                "elemento_carente": "Fogo",
                "dna_comprometido": "Linhagem mista — padroes de indecisao e medo de se posicionar, heranca de silenciamento",
                "serpentes_ativas": [
                    "Serpente da Duvida — hiperatividade mental, dificuldade de foco",
                    "Serpente da Superficialidade — fuga de conexoes profundas, dispersao",
                ],
                "setenio": "4o Setenio (21-28 anos) — fase de autonomia e escolhas",
                "fase_alquimica": "Sublimatio — elevacao e refinamento do pensamento",
            },
        },
        {
            "tel": "5511900000006",
            "nome": "Rafael",
            "data_nasc": "1986-09-03",
            "hora_nasc": "16:46",
            "cidade": "Curitiba, PR",
            "mapa_alquimico": {
                "tipo": "Mapa Alquimico",
                "elemento_dominante": "Terra",
                "elemento_carente": "Ar",
                "dna_comprometido": "Linhagem paterna — padroes de rigidez, perfeccionismo e dificuldade de adaptacao",
                "serpentes_ativas": [
                    "Serpente da Rigidez — tensao cronica na coluna e mandibula",
                    "Serpente do Perfeccionismo — autocritica excessiva, bloqueio criativo",
                    "Serpente da Escassez — medo de nao ter o suficiente, acumulacao",
                ],
                "setenio": "5o Setenio (28-35 anos) — fase de individuacao e proposito",
                "fase_alquimica": "Coagulatio — materializacao e concretizacao de propositos",
            },
        },
        {
            "tel": "5511900000009",
            "nome": "Fernanda",
            "data_nasc": "1988-08-07",
            "hora_nasc": "12:31",
            "cidade": "Porto Alegre, RS",
            "mapa_alquimico": {
                "tipo": "Mapa Alquimico",
                "elemento_dominante": "Agua",
                "elemento_carente": "Fogo",
                "dna_comprometido": "Linhagem materna — padroes de vitimismo e auto-sabotagem, dificuldade de agir",
                "serpentes_ativas": [
                    "Serpente da Vitima — passividade e espera por salvacao externa",
                    "Serpente da Procrastinacao — paralisia diante de decisoes importantes",
                ],
                "setenio": "5o Setenio (28-35 anos) — fase de individuacao e proposito",
                "fase_alquimica": "Mortificatio — morte simbolica do ego e renascimento",
            },
        },
    ]

    total = 0
    for p in pacientes:
        nome_url = p["nome"].replace(" ", "+")
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "numero_telefone": p["tel"],
            "nome": p["nome"],
            "data_nascimento": p["data_nasc"],
            "hora_nascimento": p["hora_nasc"],
            "cidade_nascimento": p["cidade"],
            "mapa_json": json.dumps(p["mapa_alquimico"], ensure_ascii=False),
            "imagem_url": f"https://placehold.co/600x600/1a0a2e/D4AF37?text=Mapa+Alquimico%0A{nome_url}",
            "criado_em": "2026-03-12T14:00:00-03:00",
        }
        result = api_post("mapas_astrais", data)
        if result:
            total += 1
            print(f"  OK: Mapa Alquimico — {p['nome']}")
        else:
            print(f"  FALHA: {p['nome']}")

    print(f"\nTotal: {total}/5 mapas alquimicos inseridos.")


if __name__ == "__main__":
    main()
