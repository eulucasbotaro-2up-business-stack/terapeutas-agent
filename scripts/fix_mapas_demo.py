"""
Script para corrigir os mapas_astrais dos pacientes demo.
Regras:
- Cada paciente demo deve ter EXATAMENTE 2 mapas
- Mapa 1: "Mapa Alquimico" (com imagem do boneco/figura humana)
- Mapa 2: "Mapa Natal" (com imagem das linhas de aspecto)
- Deletar entradas extras
- mapa_json deve ser JSONB (objeto), não string
"""

import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://vtcjuaiuyjizkuyqfhtj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ0Y2p1YWl1eWppemt1eXFmaHRqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE4Mzk4OCwiZXhwIjoyMDg5NzU5OTg4fQ.Ie1RAfW4TBFX1GKB2_5vTUKCpVV6SWWW1qa5bJoYetQ"
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

# Telefones dos pacientes demo
DEMO_PHONES = [f"551190000000{i}" for i in range(1, 10)] + ["5511900000010"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Dados astrológicos base para cada paciente demo (signo solar, lunar, ascendente)
ASTRO_DATA = {
    "5511900000001": {
        "sol": {"signo": "Áries", "casa": 11, "grau": 20.5},
        "lua": {"signo": "Câncer", "casa": 1, "grau": 8.2},
        "ascendente": {"signo": "Leão", "grau": 22.6},
        "elemento_dominante": "Água",
        "modalidade_dominante": "Fixo",
        "nome": "Ana Carolina Ribeiro",
        "data_nascimento": "15/04/1990",
        "hora_nascimento": "08:30",
        "cidade_nascimento": "São Paulo",
    },
    "5511900000002": {
        "sol": {"signo": "Escorpião", "casa": 3, "grau": 0.4},
        "lua": {"signo": "Capricórnio", "casa": 9, "grau": 13.3},
        "ascendente": {"signo": "Virgem", "grau": 5.8},
        "elemento_dominante": "Terra",
        "modalidade_dominante": "Cardinal",
        "nome": "Pedro Henrique Santos",
        "data_nascimento": "22/10/1985",
        "hora_nascimento": "09:00",
        "cidade_nascimento": "Rio de Janeiro",
    },
    "5511900000003": {
        "sol": {"signo": "Touro", "casa": 5, "grau": 5.0},
        "lua": {"signo": "Aquário", "casa": 11, "grau": 28.0},
        "ascendente": {"signo": "Sagitário", "grau": 14.2},
        "elemento_dominante": "Ar",
        "modalidade_dominante": "Fixo",
        "nome": "Juliana Ferreira Costa",
        "data_nascimento": "02/05/1992",
        "hora_nascimento": "10:15",
        "cidade_nascimento": "Belo Horizonte",
    },
    "5511900000004": {
        "sol": {"signo": "Capricórnio", "casa": 7, "grau": 15.3},
        "lua": {"signo": "Libra", "casa": 4, "grau": 22.1},
        "ascendente": {"signo": "Câncer", "grau": 10.5},
        "elemento_dominante": "Água",
        "modalidade_dominante": "Cardinal",
        "nome": "Marcos Oliveira Lima",
        "data_nascimento": "10/01/1988",
        "hora_nascimento": "07:45",
        "cidade_nascimento": "Curitiba",
    },
    "5511900000005": {
        "sol": {"signo": "Gêmeos", "casa": 5, "grau": 23.0},
        "lua": {"signo": "Peixes", "casa": 1, "grau": 12.0},
        "ascendente": {"signo": "Aquário", "grau": 7.9},
        "elemento_dominante": "Ar",
        "modalidade_dominante": "Mutável",
        "nome": "Beatriz Almeida Souza",
        "data_nascimento": "18/06/1995",
        "hora_nascimento": "14:00",
        "cidade_nascimento": "Salvador",
    },
    "5511900000006": {
        "sol": {"signo": "Câncer", "casa": 2, "grau": 13.3},
        "lua": {"signo": "Sagitário", "casa": 8, "grau": 4.5},
        "ascendente": {"signo": "Touro", "grau": 18.7},
        "elemento_dominante": "Terra",
        "modalidade_dominante": "Fixo",
        "nome": "Rafael Duarte Mendes",
        "data_nascimento": "05/07/1991",
        "hora_nascimento": "16:45",
        "cidade_nascimento": "Porto Alegre",
    },
    "5511900000007": {
        "sol": {"signo": "Sagitário", "casa": 12, "grau": 2.0},
        "lua": {"signo": "Gêmeos", "casa": 6, "grau": 17.5},
        "ascendente": {"signo": "Capricórnio", "grau": 25.3},
        "elemento_dominante": "Fogo",
        "modalidade_dominante": "Mutável",
        "nome": "Camila Rodrigues Neves",
        "data_nascimento": "25/11/1993",
        "hora_nascimento": "11:45",
        "cidade_nascimento": "Recife",
    },
    "5511900000008": {
        "sol": {"signo": "Leão", "casa": 4, "grau": 20.3},
        "lua": {"signo": "Touro", "casa": 7, "grau": 9.8},
        "ascendente": {"signo": "Áries", "grau": 3.1},
        "elemento_dominante": "Fogo",
        "modalidade_dominante": "Fixo",
        "nome": "Lucas Gabriel Pinto",
        "data_nascimento": "12/08/1987",
        "hora_nascimento": "06:20",
        "cidade_nascimento": "Fortaleza",
    },
    "5511900000009": {
        "sol": {"signo": "Virgem", "casa": 2, "grau": 9.3},
        "lua": {"signo": "Leão", "casa": 2, "grau": 15.0},
        "ascendente": {"signo": "Leão", "grau": 28.4},
        "elemento_dominante": "Terra",
        "modalidade_dominante": "Mutável",
        "nome": "Fernanda Vieira Torres",
        "data_nascimento": "08/09/1994",
        "hora_nascimento": "12:30",
        "cidade_nascimento": "Brasília",
    },
    "5511900000010": {
        "sol": {"signo": "Peixes", "casa": 10, "grau": 18.7},
        "lua": {"signo": "Escorpião", "casa": 6, "grau": 3.2},
        "ascendente": {"signo": "Gêmeos", "grau": 12.0},
        "elemento_dominante": "Água",
        "modalidade_dominante": "Mutável",
        "nome": "Thiago Barbosa Cardoso",
        "data_nascimento": "14/03/1989",
        "hora_nascimento": "20:00",
        "cidade_nascimento": "Manaus",
    },
}

# Dados alquímicos para cada paciente
ALQUIMICO_DATA = {
    "5511900000001": {
        "elemento_dominante": "Fogo",
        "elemento_carente": "Água",
        "dna_comprometido": "Linhagem paterna — padrões de raiva reprimida e dificuldade de expressão emocional",
        "serpentes_ativas": [
            "Serpente da Impaciência — ativação crônica no plexo solar",
            "Serpente do Controle — tensão constante nos ombros e nuca",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Calcinatio — processo de purificação pelo fogo interior",
    },
    "5511900000002": {
        "elemento_dominante": "Terra",
        "elemento_carente": "Ar",
        "dna_comprometido": "Linhagem materna — padrões de escassez e medo de abandono",
        "serpentes_ativas": [
            "Serpente da Rigidez — cristalização nas articulações",
            "Serpente da Desconfiança — tensão no peito e dificuldade de abertura",
        ],
        "setenio": "6º Setênio (35-42 anos) — fase de maturidade e contribuição",
        "fase_alquimica": "Coagulatio — processo de materialização e ancoragem",
    },
    "5511900000003": {
        "elemento_dominante": "Água",
        "elemento_carente": "Terra",
        "dna_comprometido": "Linhagem materna — padrões de codependência e absorção emocional",
        "serpentes_ativas": [
            "Serpente da Absorção — hipersensibilidade energética",
            "Serpente do Sacrifício — dor crônica nos joelhos e quadril",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Solutio — dissolução de padrões emocionais cristalizados",
    },
    "5511900000004": {
        "elemento_dominante": "Água",
        "elemento_carente": "Fogo",
        "dna_comprometido": "Linhagem paterna — padrões de autoritarismo e frieza emocional",
        "serpentes_ativas": [
            "Serpente do Dever — tensão nos ombros e peso nas costas",
            "Serpente da Culpa — aperto no estômago e dificuldade digestiva",
        ],
        "setenio": "6º Setênio (35-42 anos) — fase de maturidade e contribuição",
        "fase_alquimica": "Mortificatio — morte simbólica do ego rígido",
    },
    "5511900000005": {
        "elemento_dominante": "Ar",
        "elemento_carente": "Fogo",
        "dna_comprometido": "Linhagem paterna — padrões de dispersão mental e fuga de compromissos",
        "serpentes_ativas": [
            "Serpente da Dispersão — dificuldade de foco e presença",
            "Serpente da Superficialidade — evitação de conexões profundas",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Sublimatio — elevação da consciência além do mental",
    },
    "5511900000006": {
        "elemento_dominante": "Terra",
        "elemento_carente": "Ar",
        "dna_comprometido": "Linhagem materna — padrões de apego material e medo de mudança",
        "serpentes_ativas": [
            "Serpente da Estagnação — resistência ao fluxo natural",
            "Serpente do Apego — tensão no baixo ventre e quadril",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Separatio — processo de discernimento e separação do essencial",
    },
    "5511900000007": {
        "elemento_dominante": "Fogo",
        "elemento_carente": "Água",
        "dna_comprometido": "Linhagem paterna — padrões de inquietude e fuga de responsabilidades",
        "serpentes_ativas": [
            "Serpente da Fuga — tensão nas pernas e pés",
            "Serpente da Arrogância — rigidez na coluna cervical",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Calcinatio — purificação pelo fogo da experiência",
    },
    "5511900000008": {
        "elemento_dominante": "Fogo",
        "elemento_carente": "Terra",
        "dna_comprometido": "Linhagem paterna — padrões de orgulho e necessidade de reconhecimento",
        "serpentes_ativas": [
            "Serpente do Orgulho — tensão no coração e peito",
            "Serpente da Vaidade — necessidade constante de validação externa",
        ],
        "setenio": "6º Setênio (35-42 anos) — fase de maturidade e contribuição",
        "fase_alquimica": "Calcinatio — queima do ego inflado",
    },
    "5511900000009": {
        "elemento_dominante": "Água",
        "elemento_carente": "Fogo",
        "dna_comprometido": "Linhagem materna — padrões de perfeccionismo e autocrítica destrutiva",
        "serpentes_ativas": [
            "Serpente da Autocrítica — tensão na garganta e mandíbula",
            "Serpente do Perfeccionismo — dor crônica nas mãos e punhos",
        ],
        "setenio": "5º Setênio (28-35 anos) — fase de individuação e propósito",
        "fase_alquimica": "Separatio — processo de discernimento entre o real e o idealizado",
    },
    "5511900000010": {
        "elemento_dominante": "Água",
        "elemento_carente": "Terra",
        "dna_comprometido": "Linhagem materna — padrões de vitimismo e fuga da realidade",
        "serpentes_ativas": [
            "Serpente da Ilusão — dificuldade de ancoramento na realidade",
            "Serpente da Evasão — tendência a escapismos e vícios sutis",
        ],
        "setenio": "6º Setênio (35-42 anos) — fase de maturidade e contribuição",
        "fase_alquimica": "Solutio — dissolução de fantasias e ilusões",
    },
}

# Aspectos astrológicos para o Mapa Natal
ASPECTOS_BASE = [
    {"aspecto": "Conjunção", "planeta1": "Sol", "planeta2": "Mercúrio", "orbe": 3.2},
    {"aspecto": "Trígono", "planeta1": "Lua", "planeta2": "Vênus", "orbe": 4.1},
    {"aspecto": "Quadratura", "planeta1": "Marte", "planeta2": "Saturno", "orbe": 2.8},
    {"aspecto": "Oposição", "planeta1": "Júpiter", "planeta2": "Plutão", "orbe": 5.0},
    {"aspecto": "Sextil", "planeta1": "Vênus", "planeta2": "Netuno", "orbe": 1.5},
]

# URLs das imagens existentes no Supabase Storage
STORAGE_BASE = f"{SUPABASE_URL}/storage/v1/object/public/mapas-astrais"
IMAGE_ALQUIMICO = {
    "5511900000001": f"{STORAGE_BASE}/demo/ana_carolina_alquimico.png",
    "5511900000002": f"{STORAGE_BASE}/demo/pedro_henrique_alquimico.png",
    "5511900000003": f"{STORAGE_BASE}/demo/juliana_ferreira_alquimico.png",
    "5511900000004": f"{STORAGE_BASE}/demo/marcos_oliveira_alquimico.png",
    "5511900000005": f"{STORAGE_BASE}/demo/beatriz_almeida_alquimico.png",
    "5511900000006": f"{STORAGE_BASE}/demo/rafael_duarte_alquimico.png",
    "5511900000007": f"{STORAGE_BASE}/demo/camila_rodrigues_alquimico.png",
    "5511900000008": f"{STORAGE_BASE}/demo/lucas_gabriel_alquimico.png",
    "5511900000009": f"{STORAGE_BASE}/demo/fernanda_vieira_alquimico.png",
    "5511900000010": f"{STORAGE_BASE}/demo/thiago_barbosa_alquimico.png",
}
IMAGE_NATAL = {
    "5511900000001": f"{STORAGE_BASE}/demo/ana_carolina_natal.png",
    "5511900000002": f"{STORAGE_BASE}/demo/pedro_henrique_natal.png",
    "5511900000003": f"{STORAGE_BASE}/demo/juliana_ferreira_natal.png",
    "5511900000004": f"{STORAGE_BASE}/demo/marcos_oliveira_natal.png",
    "5511900000005": f"{STORAGE_BASE}/demo/beatriz_almeida_natal.png",
    "5511900000006": f"{STORAGE_BASE}/demo/rafael_duarte_natal.png",
    "5511900000007": f"{STORAGE_BASE}/demo/camila_rodrigues_natal.png",
    "5511900000008": f"{STORAGE_BASE}/demo/lucas_gabriel_natal.png",
    "5511900000009": f"{STORAGE_BASE}/demo/fernanda_vieira_natal.png",
    "5511900000010": f"{STORAGE_BASE}/demo/thiago_barbosa_natal.png",
}


def get_all_mapas():
    """Busca todos os mapas_astrais do terapeuta demo."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/mapas_astrais"
        f"?terapeuta_id=eq.{TERAPEUTA_ID}&order=numero_telefone,id",
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()


def delete_mapa(mapa_id):
    """Deleta um mapa pelo ID."""
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/mapas_astrais?id=eq.{mapa_id}",
        headers=HEADERS,
    )
    r.raise_for_status()
    print(f"  [DELETE] {mapa_id} — status {r.status_code}")


def update_mapa(mapa_id, data):
    """Atualiza um mapa pelo ID. mapa_json é enviado como JSON string (coluna text)."""
    # Se mapa_json é dict, converter para JSON string para coluna text
    if "mapa_json" in data and isinstance(data["mapa_json"], dict):
        data["mapa_json"] = json.dumps(data["mapa_json"], ensure_ascii=False)
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/mapas_astrais?id=eq.{mapa_id}",
        headers=HEADERS,
        json=data,
    )
    r.raise_for_status()
    print(f"  [UPDATE] {mapa_id} — status {r.status_code}")


def create_mapa(data):
    """Cria um novo mapa. mapa_json é enviado como JSON string (coluna text)."""
    if "mapa_json" in data and isinstance(data["mapa_json"], dict):
        data["mapa_json"] = json.dumps(data["mapa_json"], ensure_ascii=False)
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/mapas_astrais",
        headers=HEADERS,
        json=data,
    )
    r.raise_for_status()
    created = r.json()
    new_id = created[0]["id"] if isinstance(created, list) else created.get("id", "?")
    print(f"  [CREATE] {new_id} — status {r.status_code}")


def build_alquimico_json(phone):
    """Constrói o mapa_json para Mapa Alquimico."""
    astro = ASTRO_DATA[phone]
    alq = ALQUIMICO_DATA[phone]
    return {
        "tipo": "Mapa Alquimico",
        "sol": astro["sol"],
        "lua": astro["lua"],
        "ascendente": astro["ascendente"],
        "elemento_dominante": alq["elemento_dominante"],
        "elemento_carente": alq["elemento_carente"],
        "modalidade_dominante": astro["modalidade_dominante"],
        "dna_comprometido": alq["dna_comprometido"],
        "serpentes_ativas": alq["serpentes_ativas"],
        "setenio": alq["setenio"],
        "fase_alquimica": alq["fase_alquimica"],
    }


def build_natal_json(phone):
    """Constrói o mapa_json para Mapa Natal."""
    astro = ASTRO_DATA[phone]
    return {
        "tipo": "Mapa Natal",
        "sol": astro["sol"],
        "lua": astro["lua"],
        "ascendente": astro["ascendente"],
        "elemento_dominante": astro["elemento_dominante"],
        "modalidade_dominante": astro["modalidade_dominante"],
        "aspectos": ASPECTOS_BASE,
    }


def main():
    print("=" * 60)
    print("Corrigindo mapas_astrais dos pacientes demo")
    print("=" * 60)

    all_mapas = get_all_mapas()
    print(f"\nTotal de mapas encontrados: {len(all_mapas)}")

    # Agrupar por numero_telefone
    by_phone = {}
    for m in all_mapas:
        phone = m["numero_telefone"]
        if phone not in by_phone:
            by_phone[phone] = []
        by_phone[phone].append(m)

    print(f"Telefones únicos: {len(by_phone)}")
    for phone, entries in by_phone.items():
        is_demo = phone in DEMO_PHONES
        print(f"  {phone}: {len(entries)} entrada(s) {'[DEMO]' if is_demo else '[REAL - não tocar]'}")

    # Processar apenas pacientes demo
    for phone in DEMO_PHONES:
        entries = by_phone.get(phone, [])
        astro = ASTRO_DATA[phone]
        print(f"\n--- {astro['nome']} ({phone}) ---")
        print(f"  Entradas existentes: {len(entries)}")

        # Nota: existe unique constraint em (terapeuta_id, numero_telefone, hora_nascimento)
        # Por isso NÃO alteramos hora_nascimento de registros existentes para evitar conflitos.
        # Para novos registros, usamos hora_nascimento original + ":01" como sufixo diferenciador.

        if len(entries) == 0:
            # Criar ambos os mapas com horas levemente diferentes
            hora_base = astro["hora_nascimento"]
            # Adicionar 1 minuto para o segundo mapa evitar conflito
            h, m = hora_base.split(":")
            hora_natal = f"{h}:{int(m)+1:02d}"
            print(f"  Criando Mapa Alquímico (hora={hora_base})...")
            create_mapa({
                "terapeuta_id": TERAPEUTA_ID,
                "numero_telefone": phone,
                "nome": astro["nome"],
                "data_nascimento": astro["data_nascimento"],
                "hora_nascimento": hora_base,
                "cidade_nascimento": astro["cidade_nascimento"],
                "mapa_json": build_alquimico_json(phone),
                "imagem_url": IMAGE_ALQUIMICO[phone],
            })
            print(f"  Criando Mapa Natal (hora={hora_natal})...")
            create_mapa({
                "terapeuta_id": TERAPEUTA_ID,
                "numero_telefone": phone,
                "nome": astro["nome"],
                "data_nascimento": astro["data_nascimento"],
                "hora_nascimento": hora_natal,
                "cidade_nascimento": astro["cidade_nascimento"],
                "mapa_json": build_natal_json(phone),
                "imagem_url": IMAGE_NATAL[phone],
            })

        elif len(entries) == 1:
            # Atualizar o existente como Alquímico (manter hora original), criar Natal
            entry = entries[0]
            existing_hora = entry["hora_nascimento"]
            print(f"  Atualizando {entry['id']} para Mapa Alquímico (hora={existing_hora})...")
            update_data = {
                "nome": astro["nome"],
                "mapa_json": build_alquimico_json(phone),
            }
            if entry.get("imagem_url"):
                update_data["imagem_url"] = entry["imagem_url"]
            else:
                update_data["imagem_url"] = IMAGE_ALQUIMICO[phone]
            update_mapa(entry["id"], update_data)

            # Criar Mapa Natal com hora +1 minuto
            h, m = existing_hora.split(":")
            hora_natal = f"{h}:{int(m)+1:02d}"
            print(f"  Criando Mapa Natal (hora={hora_natal})...")
            create_mapa({
                "terapeuta_id": TERAPEUTA_ID,
                "numero_telefone": phone,
                "nome": astro["nome"],
                "data_nascimento": entry.get("data_nascimento", astro["data_nascimento"]),
                "hora_nascimento": hora_natal,
                "cidade_nascimento": entry.get("cidade_nascimento", astro["cidade_nascimento"]),
                "mapa_json": build_natal_json(phone),
                "imagem_url": IMAGE_NATAL[phone],
            })

        else:
            # 2+ entradas: manter a primeira como Alquímico, segunda como Natal, deletar o resto
            sorted_entries = sorted(entries, key=lambda x: x.get("criado_em", ""))

            first = sorted_entries[0]
            second = sorted_entries[1]
            extras = sorted_entries[2:]

            # Deletar extras PRIMEIRO para evitar conflitos de unique constraint
            for extra in extras:
                print(f"  Deletando extra {extra['id']} (hora={extra['hora_nascimento']})")
                delete_mapa(extra["id"])

            # Atualizar primeira como Mapa Alquimico (manter hora original)
            print(f"  Atualizando {first['id']} (hora={first['hora_nascimento']}) -> Mapa Alquímico")
            update_data_1 = {
                "nome": astro["nome"],
                "mapa_json": build_alquimico_json(phone),
            }
            if first.get("imagem_url"):
                update_data_1["imagem_url"] = first["imagem_url"]
            else:
                update_data_1["imagem_url"] = IMAGE_ALQUIMICO[phone]
            update_mapa(first["id"], update_data_1)

            # Atualizar segunda como Mapa Natal (manter hora original)
            print(f"  Atualizando {second['id']} (hora={second['hora_nascimento']}) -> Mapa Natal")
            update_data_2 = {
                "nome": astro["nome"],
                "mapa_json": build_natal_json(phone),
            }
            if second.get("imagem_url"):
                update_data_2["imagem_url"] = second["imagem_url"]
            else:
                update_data_2["imagem_url"] = IMAGE_NATAL[phone]
            update_mapa(second["id"], update_data_2)

    # Verificação final
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO FINAL")
    print("=" * 60)
    all_mapas = get_all_mapas()
    by_phone = {}
    for m in all_mapas:
        phone = m["numero_telefone"]
        if phone not in by_phone:
            by_phone[phone] = []
        by_phone[phone].append(m)

    ok_count = 0
    error_count = 0
    for phone in DEMO_PHONES:
        entries = by_phone.get(phone, [])
        nome = ASTRO_DATA[phone]["nome"]
        if len(entries) == 2:
            tipos = []
            for e in entries:
                mj = e["mapa_json"]
                if isinstance(mj, dict):
                    tipos.append(mj.get("tipo", "???"))
                elif isinstance(mj, str):
                    try:
                        parsed = json.loads(mj)
                        tipos.append(parsed.get("tipo", "??? (string)"))
                    except:
                        tipos.append("ERRO: string não-JSON")
                else:
                    tipos.append(f"ERRO: tipo {type(mj)}")
            has_alq = "Mapa Alquimico" in tipos
            has_nat = "Mapa Natal" in tipos
            if has_alq and has_nat:
                print(f"  OK  {nome} ({phone}): {tipos}")
                ok_count += 1
            else:
                print(f"  ERR {nome} ({phone}): {tipos}")
                error_count += 1
        else:
            print(f"  ERR {nome} ({phone}): {len(entries)} entradas (esperado 2)")
            error_count += 1

    print(f"\nResultado: {ok_count} OK, {error_count} erros")
    if error_count == 0:
        print("Todos os pacientes demo estão corretos!")
    else:
        print("ATENÇÃO: Alguns pacientes ainda têm problemas!")


if __name__ == "__main__":
    main()
