"""
Limpa todos os mapas e recria 2 por paciente (Natal + Alquimico).
Depois rode gerar_mapas_demo.py para gerar as imagens.
"""
import json
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

# 10 pacientes demo
PACIENTES = [
    {"tel": "5511900000001", "nome": "Ana Carolina Ribeiro", "nasc": "1989-03-15", "hora": "08:31", "cidade": "Sao Paulo, SP"},
    {"tel": "5511900000002", "nome": "Pedro Henrique Santos", "nasc": "1995-07-22", "hora": "09:01", "cidade": "Recife, PE"},
    {"tel": "5511900000003", "nome": "Juliana Ferreira Costa", "nasc": "1982-11-08", "hora": "10:16", "cidade": "Rio de Janeiro, RJ"},
    {"tel": "5511900000004", "nome": "Marcos Oliveira Lima", "nasc": "1988-01-10", "hora": "07:46", "cidade": "Curitiba"},
    {"tel": "5511900000005", "nome": "Beatriz Almeida Souza", "nasc": "1997-06-12", "hora": "14:01", "cidade": "Belo Horizonte, MG"},
    {"tel": "5511900000006", "nome": "Rafael Duarte Mendes", "nasc": "1986-09-03", "hora": "16:46", "cidade": "Curitiba, PR"},
    {"tel": "5511900000007", "nome": "Camila Rodrigues Neves", "nasc": "1993-12-25", "hora": "11:46", "cidade": "Fortaleza, CE"},
    {"tel": "5511900000008", "nome": "Lucas Gabriel Pinto", "nasc": "2000-04-18", "hora": "06:21", "cidade": "Salvador, BA"},
    {"tel": "5511900000009", "nome": "Fernanda Vieira Torres", "nasc": "1988-08-07", "hora": "22:10", "cidade": "Porto Alegre, RS"},
    {"tel": "5511900000010", "nome": "Thiago Barbosa Cardoso", "nasc": "1989-03-14", "hora": "20:01", "cidade": "Manaus"},
]

SIGNOS = ["Aries", "Touro", "Gemeos", "Cancer", "Leao", "Virgem", "Libra", "Escorpiao", "Sagitario", "Capricornio", "Aquario", "Peixes"]
ELEMENTOS = ["Fogo", "Terra", "Ar", "Agua"]

def gerar_mapa_json(nome, tipo, idx):
    """Gera mapa_json com dados astrológicos simulados."""
    sol_idx = (idx * 3) % 12
    lua_idx = (idx * 5 + 2) % 12
    asc_idx = (idx * 7 + 1) % 12
    elem_idx = idx % 4

    base = {
        "tipo": tipo,
        "sol": {"signo": SIGNOS[sol_idx], "casa": (idx % 12) + 1, "grau": round(5.0 + idx * 2.3, 1)},
        "lua": {"signo": SIGNOS[lua_idx], "casa": ((idx + 3) % 12) + 1, "grau": round(12.0 + idx * 1.7, 1)},
        "ascendente": {"signo": SIGNOS[asc_idx], "grau": round(18.0 + idx * 0.9, 1)},
        "elemento_dominante": ELEMENTOS[elem_idx],
        "posicoes": [
            {"planeta": "Sol", "grau": round(5.0 + idx * 2.3, 1), "signo": SIGNOS[sol_idx], "casa": f"C{(idx % 12) + 1}"},
            {"planeta": "Lua", "grau": round(12.0 + idx * 1.7, 1), "signo": SIGNOS[lua_idx], "casa": f"C{((idx + 3) % 12) + 1}"},
            {"planeta": "Mercurio", "grau": round(8.5 + idx * 1.2, 1), "signo": SIGNOS[(sol_idx + 1) % 12], "casa": f"C{((idx + 1) % 12) + 1}"},
            {"planeta": "Venus", "grau": round(15.3 + idx * 0.8, 1), "signo": SIGNOS[(lua_idx + 1) % 12], "casa": f"C{((idx + 4) % 12) + 1}"},
            {"planeta": "Marte", "grau": round(22.1 + idx * 1.5, 1), "signo": SIGNOS[(asc_idx + 2) % 12], "casa": f"C{((idx + 5) % 12) + 1}"},
            {"planeta": "Jupiter", "grau": round(3.7 + idx * 0.6, 1), "signo": SIGNOS[(sol_idx + 4) % 12], "casa": f"C{((idx + 8) % 12) + 1}"},
            {"planeta": "Saturno", "grau": round(10.6 + idx * 0.4, 1), "signo": SIGNOS[(lua_idx + 3) % 12], "casa": f"C{((idx + 11) % 12) + 1}"},
            {"planeta": "Urano", "grau": round(27.0 + idx * 0.3, 1), "signo": SIGNOS[(asc_idx + 5) % 12], "casa": f"C{((idx + 10) % 12) + 1}"},
            {"planeta": "Netuno", "grau": round(23.6 + idx * 0.2, 1), "signo": SIGNOS[(asc_idx + 5) % 12], "casa": f"C{((idx + 10) % 12) + 1}"},
            {"planeta": "Plutao", "grau": round(0.2 + idx * 0.5, 1), "signo": SIGNOS[(sol_idx + 3) % 12], "casa": f"C{((idx + 8) % 12) + 1}"},
        ],
        "aspectos": [
            {"planeta1": "Sol", "planeta2": "Jupiter", "aspecto": "Sextil", "orbe": f"{round(1.5 + idx * 0.3, 1)}°"},
            {"planeta1": "Lua", "planeta2": "Mercurio", "aspecto": "Sextil", "orbe": f"{round(0.8 + idx * 0.2, 1)}°"},
            {"planeta1": "Lua", "planeta2": "Venus", "aspecto": "Conjuncao", "orbe": f"{round(1.0 + idx * 0.1, 1)}°"},
            {"planeta1": "Lua", "planeta2": "Marte", "aspecto": "Trigono", "orbe": f"{round(4.5 + idx * 0.5, 1)}°"},
            {"planeta1": "Mercurio", "planeta2": "Venus", "aspecto": "Sextil", "orbe": f"{round(0.2 + idx * 0.1, 1)}°"},
            {"planeta1": "Mercurio", "planeta2": "Marte", "aspecto": "Oposicao", "orbe": f"{round(5.0 + idx * 0.4, 1)}°"},
            {"planeta1": "Venus", "planeta2": "Marte", "aspecto": "Trigono", "orbe": f"{round(3.8 + idx * 0.3, 1)}°"},
            {"planeta1": "Jupiter", "planeta2": "Saturno", "aspecto": "Quadratura", "orbe": f"{round(1.0 + idx * 0.2, 1)}°"},
        ],
        "resumo": f"Mapa {tipo} de {nome}. Sol em {SIGNOS[sol_idx]}, Lua em {SIGNOS[lua_idx]}, Ascendente em {SIGNOS[asc_idx]}. Elemento dominante: {ELEMENTOS[elem_idx]}. Personalidade marcada pela energia de {SIGNOS[sol_idx]} com profundidade emocional de {SIGNOS[lua_idx]}.",
    }
    return json.dumps(base, ensure_ascii=False)


def main():
    print("=== Reset e Criação de Mapas Demo ===\n")

    # 1. Deletar todos os mapas existentes
    print("[1/2] Deletando todos os mapas...")
    url = f"{SUPABASE_URL}/rest/v1/mapas_astrais?id=neq.00000000-0000-0000-0000-000000000000"
    h = dict(HEADERS)
    h["Prefer"] = "return=minimal"
    r = requests.delete(url, headers=h)
    print(f"  DELETE: {r.status_code}")

    # 2. Inserir 2 mapas por paciente
    print("\n[2/2] Criando 2 mapas por paciente...")
    sucesso = 0
    for idx, pac in enumerate(PACIENTES):
        for tipo in ["Mapa Natal", "Mapa Alquimico"]:
            data = {
                "terapeuta_id": TERAPEUTA_ID,
                "numero_telefone": pac["tel"],
                "nome": pac["nome"],
                "data_nascimento": pac["nasc"],
                "hora_nascimento": pac["hora"],
                "cidade_nascimento": pac["cidade"],
                "tipo_mapa": tipo,
                "mapa_json": gerar_mapa_json(pac["nome"], tipo, idx),
                "imagem_url": None,
            }
            r = requests.post(f"{SUPABASE_URL}/rest/v1/mapas_astrais", headers=HEADERS, json=data)
            if r.status_code in (200, 201):
                sucesso += 1
                print(f"  OK {pac['nome']} — {tipo}")
            else:
                print(f"  ERRO {pac['nome']} — {tipo}: {r.status_code} {r.text[:150]}")

    print(f"\n=== {sucesso}/20 mapas criados ===")
    print("Agora rode: python scripts/gerar_mapas_demo.py")


if __name__ == "__main__":
    main()
