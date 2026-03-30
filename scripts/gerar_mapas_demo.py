"""
Script STANDALONE para gerar imagens reais dos mapas astrais demo.

Busca registros em mapas_astrais que ainda usam placeholder (placehold.co),
calcula o mapa via Kerykeion (com fallback se indisponivel),
renderiza PNG via matplotlib (logica copiada inline — zero imports de src/),
faz upload ao Supabase Storage e atualiza imagem_url.

Uso:
    python scripts/gerar_mapas_demo.py

Requisitos:
    - matplotlib instalado (pip install matplotlib)
    - requests instalado (pip install requests)
    - Opcional: kerykeion (pip install kerykeion) — se falhar, usa posicoes estimadas
    - Bucket "mapas" criado no Supabase Storage (publico)

Compativel com Python 3.12+ incluindo 3.14 (sem dependencia de pyswisseph C ext).
"""

import io
import math
import os
import re
import uuid
from typing import Any, Optional

import requests

# Configurar matplotlib antes de qualquer import
os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.environ.get("TEMP", "/tmp"), "matplotlib_cache"))

import matplotlib
matplotlib.use("Agg")

# ---------------------------------------------------------------------------
# Configuracao Supabase (mesmos valores do seed)
# ---------------------------------------------------------------------------
SUPABASE_URL = "https://vtcjuaiuyjizkuyqfhtj.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ0Y2p1YWl1eWppemt1eXFmaHRqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE4Mzk4OCwiZXhwIjoyMDg5NzU5OTg4fQ."
    "Ie1RAfW4TBFX1GKB2_5vTUKCpVV6SWWW1qa5bJoYetQ"
)
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

STORAGE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "image/png",
}

# ---------------------------------------------------------------------------
# Cache de coordenadas — cidades brasileiras mais comuns
# ---------------------------------------------------------------------------
_COORDS_BR: dict[str, tuple[float, float, str]] = {
    "são paulo":          (-23.5505, -46.6333, "America/Sao_Paulo"),
    "sao paulo":          (-23.5505, -46.6333, "America/Sao_Paulo"),
    "sp":                 (-23.5505, -46.6333, "America/Sao_Paulo"),
    "rio de janeiro":     (-22.9068, -43.1729, "America/Sao_Paulo"),
    "rio":                (-22.9068, -43.1729, "America/Sao_Paulo"),
    "belo horizonte":     (-19.9167, -43.9345, "America/Sao_Paulo"),
    "bh":                 (-19.9167, -43.9345, "America/Sao_Paulo"),
    "salvador":           (-12.9714, -38.5014, "America/Bahia"),
    "fortaleza":          (-3.7172,  -38.5433, "America/Fortaleza"),
    "curitiba":           (-25.4290, -49.2671, "America/Sao_Paulo"),
    "manaus":             (-3.1019,  -60.0250, "America/Manaus"),
    "recife":             (-8.0476,  -34.8770, "America/Recife"),
    "porto alegre":       (-30.0346, -51.2177, "America/Sao_Paulo"),
    "belém":              (-1.4558,  -48.4902, "America/Belem"),
    "belem":              (-1.4558,  -48.4902, "America/Belem"),
    "goiânia":            (-16.6869, -49.2648, "America/Sao_Paulo"),
    "goiania":            (-16.6869, -49.2648, "America/Sao_Paulo"),
    "florianópolis":      (-27.5954, -48.5480, "America/Sao_Paulo"),
    "florianopolis":      (-27.5954, -48.5480, "America/Sao_Paulo"),
    "maceió":             (-9.6658,  -35.7350, "America/Maceio"),
    "maceio":             (-9.6658,  -35.7350, "America/Maceio"),
    "natal":              (-5.7945,  -35.2110, "America/Fortaleza"),
    "campo grande":       (-20.4697, -54.6201, "America/Campo_Grande"),
    "teresina":           (-5.0920,  -42.8038, "America/Fortaleza"),
    "são luís":           (-2.5297,  -44.3028, "America/Fortaleza"),
    "sao luis":           (-2.5297,  -44.3028, "America/Fortaleza"),
    "joão pessoa":        (-7.1195,  -34.8450, "America/Fortaleza"),
    "joao pessoa":        (-7.1195,  -34.8450, "America/Fortaleza"),
    "aracaju":            (-10.9472, -37.0731, "America/Maceio"),
    "porto velho":        (-8.7612,  -63.9004, "America/Porto_Velho"),
    "macapá":             (0.0356,   -51.0705, "America/Belem"),
    "macapa":             (0.0356,   -51.0705, "America/Belem"),
    "rio branco":         (-9.9754,  -67.8249, "America/Rio_Branco"),
    "boa vista":          (2.8235,   -60.6758, "America/Boa_Vista"),
    "palmas":             (-10.2491, -48.3243, "America/Araguaia"),
    "vitória":            (-20.3155, -40.3128, "America/Sao_Paulo"),
    "vitoria":            (-20.3155, -40.3128, "America/Sao_Paulo"),
    "cuiabá":             (-15.6014, -56.0979, "America/Cuiaba"),
    "cuiaba":             (-15.6014, -56.0979, "America/Cuiaba"),
    "campinas":           (-22.9099, -47.0626, "America/Sao_Paulo"),
    "guarulhos":          (-23.4543, -46.5333, "America/Sao_Paulo"),
    "brasília":           (-15.7797, -47.9297, "America/Sao_Paulo"),
    "brasilia":           (-15.7797, -47.9297, "America/Sao_Paulo"),
    "df":                 (-15.7797, -47.9297, "America/Sao_Paulo"),
    "distrito federal":   (-15.7797, -47.9297, "America/Sao_Paulo"),
    "santos":             (-23.9608, -46.3336, "America/Sao_Paulo"),
    "ribeirao preto":     (-21.1775, -47.8103, "America/Sao_Paulo"),
    "ribeirão preto":     (-21.1775, -47.8103, "America/Sao_Paulo"),
    "uberlandia":         (-18.9186, -48.2772, "America/Sao_Paulo"),
    "uberlândia":         (-18.9186, -48.2772, "America/Sao_Paulo"),
    "londrina":           (-23.3045, -51.1696, "America/Sao_Paulo"),
    "joinville":          (-26.3044, -48.8487, "America/Sao_Paulo"),
}


def _limpar_cidade(cidade: str) -> str:
    """Remove sufixos desnecessarios e normaliza o nome da cidade."""
    cidade = cidade.lower().strip()
    cidade = re.sub(r"\s*,\s*brasil\s*$", "", cidade)
    cidade = re.sub(r"\s*,\s*[a-z]{2}\s*$", "", cidade)
    cidade = re.sub(r"\s+capital\s*$", "", cidade)
    cidade = re.sub(r"\s*-\s*[a-z]{2}\s*$", "", cidade)
    cidade = re.sub(r"\s+[a-z]{2}\s*$", "", cidade)
    return cidade.strip()


def _geocodificar_cidade(cidade_nascimento: str) -> tuple[float, float, str]:
    """Retorna (lat, lon, timezone) para a cidade informada."""
    chave = _limpar_cidade(cidade_nascimento)
    if chave in _COORDS_BR:
        lat, lon, tz = _COORDS_BR[chave]
        return lat, lon, tz

    # Fallback: Nominatim via requests (sem dependencia de geopy)
    url = "https://nominatim.openstreetmap.org/search"
    for tentativa in [cidade_nascimento, f"{cidade_nascimento}, Brasil"]:
        try:
            r = requests.get(url, params={
                "q": tentativa, "format": "json", "limit": 1, "accept-language": "pt",
            }, headers={"User-Agent": "alquimista-interior-bot/1.0"}, timeout=10)
            if r.status_code == 200 and r.json():
                loc = r.json()[0]
                lat, lon = float(loc["lat"]), float(loc["lon"])
                # Timezone simples — assume Sao Paulo para Brasil
                return lat, lon, "America/Sao_Paulo"
        except Exception:
            pass

    # Fallback final — Sao Paulo
    print(f"  AVISO: cidade '{cidade_nascimento}' nao encontrada, usando Sao Paulo")
    return -23.5505, -46.6333, "America/Sao_Paulo"


# ---------------------------------------------------------------------------
# Constantes de renderizacao (copiadas de chart_generator.py)
# ---------------------------------------------------------------------------
SIGNOS_ABREV = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir",
                "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

SIGNO_LABEL_TEXTO = {
    "Ari": "AR", "Tau": "TA", "Gem": "GE", "Can": "CA",
    "Leo": "LE", "Vir": "VI", "Lib": "LI", "Sco": "ES",
    "Sag": "SA", "Cap": "CP", "Aqu": "AQ", "Pis": "PI",
}

SIGNO_NOME_PT = {
    "Ari": "Aries",  "Tau": "Touro",    "Gem": "Gemeos",  "Can": "Cancer",
    "Leo": "Leao",   "Vir": "Virgem",   "Lib": "Libra",   "Sco": "Escorp.",
    "Sag": "Sagit.", "Cap": "Capric.",  "Aqu": "Aquario", "Pis": "Peixes",
}

ORDEM_PLANETAS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Ascendant", "Medium_Coeli",
]

PLANETA_ABREV_TEXTO = {
    "Sun": "Sol", "Moon": "Lua", "Mercury": "Mer", "Venus": "Ven",
    "Mars": "Mar", "Jupiter": "Jup", "Saturn": "Sat", "Uranus": "Ura",
    "Neptune": "Net", "Pluto": "Plu", "Ascendant": "AC", "Medium_Coeli": "MC",
}

COR_PLANETA = {
    "Sun": "#E65100", "Moon": "#1565C0", "Mercury": "#2E7D32",
    "Venus": "#AD1457", "Mars": "#C62828", "Jupiter": "#4527A0",
    "Saturn": "#37474F", "Uranus": "#006064", "Neptune": "#1A237E",
    "Pluto": "#4A0E4E", "Ascendant": "#000000", "Medium_Coeli": "#000000",
}

ELEM_MAPA = {
    "Ari": "Fogo", "Leo": "Fogo", "Sag": "Fogo",
    "Tau": "Terra", "Vir": "Terra", "Cap": "Terra",
    "Gem": "Ar",    "Lib": "Ar",   "Aqu": "Ar",
    "Can": "Agua",  "Sco": "Agua", "Pis": "Agua",
}

SIGNO_CORPO = {
    "Ari": "Cabeca",    "Tau": "Pescoco",
    "Gem": "Ombros",    "Can": "Peito",
    "Leo": "Coracao",   "Vir": "Abdomen",
    "Lib": "Rins",      "Sco": "Pelve",
    "Sag": "Coxas",     "Cap": "Joelhos",
    "Aqu": "Pernas",    "Pis": "Pes",
}

BG           = "#FFFFFF"
BG_PAINEL    = "#F5F5F5"
BORDA        = "#999999"
TEXTO_ESCURO = "#111111"
TEXTO_CINZA  = "#555555"
LINHA_GRADE  = "#DDDDDD"
OURO         = "#B8860B"
FIGURA_COR   = "#2C2C2C"

COR_FOGO  = "#D32F2F"
COR_TERRA = "#388E3C"
COR_AR    = "#C6A800"
COR_AGUA  = "#1565C0"

ELEMENTO_COR = {
    "Ari": COR_FOGO,  "Leo": COR_FOGO,  "Sag": COR_FOGO,
    "Tau": COR_TERRA, "Vir": COR_TERRA, "Cap": COR_TERRA,
    "Gem": COR_AR,    "Lib": COR_AR,    "Aqu": COR_AR,
    "Can": COR_AGUA,  "Sco": COR_AGUA,  "Pis": COR_AGUA,
}


# ---------------------------------------------------------------------------
# Estrutura de dados do mapa
# ---------------------------------------------------------------------------
class DadosMapa:
    def __init__(
        self,
        nome_paciente: str,
        data_nascimento: str,
        hora_nascimento: str,
        cidade_nascimento: str,
        planetas: dict[str, float],
        signos: dict[str, str],
        casas: dict[str, Optional[int]],
        aspectos: list[dict[str, Any]],
        ascendente_grau: float = 0.0,
    ) -> None:
        self.nome_paciente     = nome_paciente
        self.data_nascimento   = data_nascimento
        self.hora_nascimento   = hora_nascimento
        self.cidade_nascimento = cidade_nascimento
        self.planetas          = planetas
        self.signos            = signos
        self.casas             = casas
        self.aspectos          = aspectos
        self.ascendente_grau   = ascendente_grau


# ---------------------------------------------------------------------------
# Calculo astrologico via Kerykeion (com fallback)
# ---------------------------------------------------------------------------

# Tenta importar kerykeion uma vez
_KERYKEION_OK = False
try:
    from kerykeion import AstrologicalSubject
    _KERYKEION_OK = True
    print("[OK] Kerykeion importado com sucesso")
except Exception as e:
    print(f"[AVISO] Kerykeion indisponivel ({e}) — usando posicoes estimadas")


def _calcular_via_kerykeion(
    nome: str, ano: int, mes: int, dia: int,
    hora: int, minuto: int, lat: float, lon: float, tz_str: str,
) -> DadosMapa | None:
    """Calcula mapa via Kerykeion. Retorna None se falhar."""
    if not _KERYKEION_OK:
        return None
    try:
        sujeito = AstrologicalSubject(
            nome, ano, mes, dia, hora, minuto,
            lng=lon, lat=lat, tz_str=tz_str,
            online=False, zodiac_type="Tropical",
        )

        _HOUSE_STR_TO_INT = {
            "First_House": 1, "Second_House": 2, "Third_House": 3,
            "Fourth_House": 4, "Fifth_House": 5, "Sixth_House": 6,
            "Seventh_House": 7, "Eighth_House": 8, "Ninth_House": 9,
            "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
        }

        atributos = [
            ("sun", "Sun"), ("moon", "Moon"), ("mercury", "Mercury"),
            ("venus", "Venus"), ("mars", "Mars"), ("jupiter", "Jupiter"),
            ("saturn", "Saturn"), ("uranus", "Uranus"), ("neptune", "Neptune"),
            ("pluto", "Pluto"),
        ]

        planetas: dict[str, float] = {}
        signos: dict[str, str] = {}
        casas: dict[str, Optional[int]] = {}

        for attr, nome_p in atributos:
            ponto = getattr(sujeito, attr, None)
            if ponto is None:
                continue
            sign = ponto.sign if hasattr(ponto, "sign") else None
            if sign and sign in SIGNOS_ABREV:
                sign_idx = SIGNOS_ABREV.index(sign)
                pos = float(ponto.position) if hasattr(ponto, "position") else 0.0
                grau_abs = (sign_idx * 30.0 + pos) % 360.0
                planetas[nome_p] = grau_abs
                signos[nome_p] = sign
                casa_raw = getattr(ponto, "house", None)
                if isinstance(casa_raw, str):
                    casas[nome_p] = _HOUSE_STR_TO_INT.get(casa_raw)
                elif isinstance(casa_raw, int):
                    casas[nome_p] = casa_raw
                else:
                    casas[nome_p] = None

        # Ascendente e MC
        for attr, nome_p in [("ascendant", "Ascendant"), ("medium_coeli", "Medium_Coeli")]:
            ponto = getattr(sujeito, attr, None)
            if ponto is not None:
                sign = ponto.sign if hasattr(ponto, "sign") else None
                if sign and sign in SIGNOS_ABREV:
                    sign_idx = SIGNOS_ABREV.index(sign)
                    pos = float(ponto.position) if hasattr(ponto, "position") else 0.0
                    grau_abs = (sign_idx * 30.0 + pos) % 360.0
                    planetas[nome_p] = grau_abs
                    signos[nome_p] = sign
                    casas[nome_p] = None

        asc_grau = planetas.get("Ascendant", 0.0)

        # Aspectos
        aspectos: list[dict[str, Any]] = []
        try:
            from kerykeion.aspects.natal_aspects import NatalAspects
            natal_asp = NatalAspects(sujeito)
            planetas_pessoais = {"Sun", "Moon", "Mercury", "Venus", "Mars",
                                 "Jupiter", "Saturn", "Ascendant", "Medium_Coeli"}
            tipos_major = {"conjunction", "opposition", "square", "trine", "sextile"}
            for asp in natal_asp.relevant_aspects:
                p1 = asp.get("p1_name", asp.get("p1", ""))
                p2 = asp.get("p2_name", asp.get("p2", ""))
                tipo = asp.get("aspect", asp.get("aspect_type", ""))
                orbe = float(asp.get("orbit", asp.get("orb", 0)))
                if tipo in tipos_major and p1 in planetas_pessoais and p2 in planetas_pessoais:
                    aspectos.append({"p1": p1, "p2": p2, "tipo": tipo, "orbe": orbe})
        except Exception:
            # Aspectos sao opcionais — versoes diferentes de kerykeion tem APIs diferentes
            pass

        data_fmt = f"{dia:02d}/{mes:02d}/{ano}"
        hora_fmt = f"{hora:02d}:{minuto:02d}"
        return DadosMapa(
            nome_paciente=nome,
            data_nascimento=data_fmt,
            hora_nascimento=hora_fmt,
            cidade_nascimento="",
            planetas=planetas,
            signos=signos,
            casas=casas,
            aspectos=aspectos,
            ascendente_grau=asc_grau,
        )
    except Exception as e:
        print(f"  Kerykeion falhou: {e}")
        return None


def _calcular_fallback(
    nome: str, ano: int, mes: int, dia: int,
    hora: int, minuto: int,
) -> DadosMapa:
    """
    Gera posicoes planetarias ESTIMADAS usando formulas simplificadas.
    Nao e astronomicamente preciso, mas gera um mapa visualmente realista.
    Usa o dia juliano aproximado para estimar posicoes dos planetas.
    """
    import hashlib

    # Dia juliano simplificado (dias desde J2000.0 = 1 Jan 2000 12:00 TT)
    a = (14 - mes) // 12
    y = ano + 4800 - a
    m = mes + 12 * a - 3
    jdn = dia + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    jd = jdn + (hora - 12) / 24.0 + minuto / 1440.0
    d = jd - 2451545.0  # dias desde J2000.0

    # Posicoes medias simplificadas (graus eclipticos)
    # Baseado nas velocidades medias diarias dos planetas
    sol      = (280.460 + 0.9856474 * d) % 360.0
    lua      = (218.316 + 13.176396 * d) % 360.0
    mercurio = (252.251 + 4.0923344 * d) % 360.0
    venus    = (181.980 + 1.6021302 * d) % 360.0
    marte    = (355.433 + 0.5240208 * d) % 360.0
    jupiter  = (34.351  + 0.0831294 * d) % 360.0
    saturno  = (50.077  + 0.0334442 * d) % 360.0
    urano    = (314.055 + 0.0117300 * d) % 360.0
    netuno   = (304.349 + 0.0059880 * d) % 360.0
    plutao   = (238.929 + 0.0039780 * d) % 360.0

    # Ascendente estimado (baseado na hora + longitude de Sao Paulo aprox)
    lst = (280.46 + 360.9856474 * d + hora * 15 + minuto * 0.25) % 360.0
    ascendente = (lst + 180) % 360.0

    # MC = ~90 graus antes do ASC
    mc = (ascendente + 270) % 360.0

    def _grau_para_signo(grau: float) -> str:
        idx = int(grau / 30.0) % 12
        return SIGNOS_ABREV[idx]

    def _grau_para_casa(grau: float, asc: float) -> int:
        delta = (grau - asc) % 360.0
        return int(delta / 30.0) + 1

    posicoes = {
        "Sun": sol, "Moon": lua, "Mercury": mercurio, "Venus": venus,
        "Mars": marte, "Jupiter": jupiter, "Saturn": saturno,
        "Uranus": urano, "Neptune": netuno, "Pluto": plutao,
        "Ascendant": ascendente, "Medium_Coeli": mc,
    }

    signos = {k: _grau_para_signo(v) for k, v in posicoes.items()}
    casas = {k: _grau_para_casa(v, ascendente) for k, v in posicoes.items()}

    # Aspectos basicos
    aspectos = []
    nomes = list(posicoes.keys())
    tipo_asp = {0: "conjunction", 60: "sextile", 90: "square", 120: "trine", 180: "opposition"}
    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            diff = abs(posicoes[nomes[i]] - posicoes[nomes[j]])
            if diff > 180:
                diff = 360 - diff
            for ang, tipo in tipo_asp.items():
                orbe = abs(diff - ang)
                if orbe < 8:
                    aspectos.append({
                        "p1": nomes[i], "p2": nomes[j],
                        "tipo": tipo, "orbe": orbe,
                    })
                    break

    data_fmt = f"{dia:02d}/{mes:02d}/{ano}"
    hora_fmt = f"{hora:02d}:{minuto:02d}"
    return DadosMapa(
        nome_paciente=nome,
        data_nascimento=data_fmt,
        hora_nascimento=hora_fmt,
        cidade_nascimento="",
        planetas=posicoes,
        signos=signos,
        casas=casas,
        aspectos=aspectos,
        ascendente_grau=ascendente,
    )


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
def _grau_para_rad(grau_ecl: float, asc_grau: float) -> float:
    """Converte grau ecliptico para angulo cartesiano. Ascendente fica a esquerda."""
    delta = (grau_ecl - asc_grau) % 360.0
    angulo_graus = 180.0 - delta
    return math.radians(angulo_graus)


def _xy(raio: float, ang_rad: float) -> tuple[float, float]:
    return raio * math.cos(ang_rad), raio * math.sin(ang_rad)


def _ajustar_posicoes(
    posicoes: dict[str, float],
    asc: float,
    limiar_graus: float = 7.0,
) -> dict[str, float]:
    """Separa planetas muito proximos para evitar sobreposicao visual."""
    if not posicoes:
        return {}
    ordem = sorted(posicoes.keys(), key=lambda k: posicoes[k])
    ajustadas = dict(posicoes)
    for _ in range(8):
        modificado = False
        for i in range(len(ordem)):
            for j in range(i + 1, len(ordem)):
                p1, p2 = ordem[i], ordem[j]
                d = (ajustadas[p2] - ajustadas[p1]) % 360.0
                if d < limiar_graus:
                    delta = (limiar_graus - d) / 2.0 + 0.5
                    ajustadas[p1] = (ajustadas[p1] - delta) % 360.0
                    ajustadas[p2] = (ajustadas[p2] + delta) % 360.0
                    modificado = True
        if not modificado:
            break
    return ajustadas


# ---------------------------------------------------------------------------
# Figura humana alquimica
# ---------------------------------------------------------------------------
def _desenhar_homem_alquimico(ax: Any, dados: DadosMapa) -> None:
    """Desenha a silhueta humana alquimica no centro da roda."""
    import matplotlib.patches as patches

    cor = FIGURA_COR
    lw = 1.8

    # Cabeca
    head = patches.Circle((0, 0.395), 0.090, color=BG, ec=cor, lw=lw, zorder=22)
    ax.add_patch(head)

    # Pescoco
    ax.plot([0, 0], [0.305, 0.262], color=cor, lw=lw, zorder=22)
    # Ombros
    ax.plot([-0.215, 0.215], [0.262, 0.262], color=cor, lw=lw, zorder=22)
    # Bracos
    ax.plot([-0.215, -0.510], [0.262, 0.160], color=cor, lw=lw, zorder=22)
    ax.plot([0.215, 0.510], [0.262, 0.160], color=cor, lw=lw, zorder=22)
    # Torso
    ax.plot([0, 0], [0.262, -0.100], color=cor, lw=lw, zorder=22)
    # Quadris
    ax.plot([-0.175, 0.175], [-0.100, -0.100], color=cor, lw=lw, zorder=22)
    # Pernas
    ax.plot([-0.175, -0.120], [-0.100, -0.500], color=cor, lw=lw, zorder=22)
    ax.plot([0.175, 0.120], [-0.100, -0.500], color=cor, lw=lw, zorder=22)
    # Joelhos
    for xk, yk in [(-0.147, -0.300), (0.147, -0.300)]:
        ax.plot(xk, yk, "o", color=cor, markersize=3, zorder=22)

    # Marcacao de planetas no corpo
    _CORPO_XY = {
        "Cabeca":  (0, 0.395),  "Pescoco": (0, 0.270),
        "Ombros":  (0, 0.262),  "Peito":   (0, 0.185),
        "Coracao": (0, 0.130),  "Abdomen": (0, 0.050),
        "Rins":    (0, -0.030), "Pelve":   (0, -0.100),
        "Coxas":   (0, -0.185), "Joelhos": (0, -0.300),
        "Pernas":  (0, -0.390), "Pes":     (0, -0.490),
    }

    planetas_marcados: set[str] = set()
    for nome_p in ["Sun", "Moon", "Ascendant", "Mercury", "Venus", "Mars"]:
        if nome_p not in dados.signos:
            continue
        signo = dados.signos[nome_p]
        parte = SIGNO_CORPO.get(signo)
        if not parte or parte in planetas_marcados:
            continue
        planetas_marcados.add(parte)
        cx, cy = _CORPO_XY.get(parte, (0, 0))
        cor_p = COR_PLANETA.get(nome_p, OURO)
        abrev = PLANETA_ABREV_TEXTO.get(nome_p, nome_p[:3])
        ax.plot(cx + 0.05, cy, "o", color=cor_p, markersize=4.5, zorder=23)
        ax.text(cx + 0.14, cy, abrev,
                ha="left", va="center", fontsize=5.5,
                color=cor_p, fontweight="bold", zorder=23)

    # Rotulos dos 4 elementos
    elem_dados = [
        (0.000, 0.570, "FOGO", COR_FOGO),
        (0.570, 0.000, "AR", COR_AR),
        (0.000, -0.570, "TERRA", COR_TERRA),
        (-0.570, 0.000, "AGUA", COR_AGUA),
    ]
    for ex, ey, elabel, ecor in elem_dados:
        ax.text(ex, ey, elabel, ha="center", va="center",
                fontsize=6.5, color=ecor, fontweight="bold",
                alpha=0.65, zorder=21)


# ---------------------------------------------------------------------------
# Renderizacao PNG
# ---------------------------------------------------------------------------
def gerar_imagem_mapa(dados: DadosMapa) -> bytes:
    """Gera PNG do Mapa Alquimico — roda zodiacal com homem no centro."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import matplotlib.patches as patches
    import numpy as np

    fig = Figure(figsize=(12, 9), facecolor=BG, dpi=110)
    FigureCanvasAgg(fig)

    ax  = fig.add_axes([0.01, 0.05, 0.60, 0.90])
    axp = fig.add_axes([0.63, 0.04, 0.35, 0.92])

    ax.set_aspect("equal")
    ax.set_facecolor(BG)
    ax.set_xlim(-1.32, 1.32)
    ax.set_ylim(-1.32, 1.32)
    ax.axis("off")

    asc = dados.ascendente_grau

    R_EXT = 1.18
    R_ZOD = 0.94
    R_PLN = 0.81
    R_CSA = 0.68
    R_INT = 0.63
    R_ASP = 0.59
    SEG_RAD = math.pi / 6

    # Anel zodiacal
    for i, abrev in enumerate(SIGNOS_ABREV):
        ang0 = _grau_para_rad(i * 30.0, asc)
        ang1 = ang0 - SEG_RAD
        cor = ELEMENTO_COR.get(abrev, "#CCCCCC")
        t = np.linspace(ang0, ang1, 40)

        xs = list(R_EXT * np.cos(t)) + list(R_ZOD * np.cos(t[::-1]))
        ys = list(R_EXT * np.sin(t)) + list(R_ZOD * np.sin(t[::-1]))
        ax.fill(xs, ys, color=cor, alpha=0.18, zorder=2)

        x0, y0 = _xy(R_ZOD, ang0)
        x1, y1 = _xy(R_EXT, ang0)
        ax.plot([x0, x1], [y0, y1], color=cor, lw=0.8, alpha=0.55, zorder=3)

        ang_m = ang0 - SEG_RAD / 2
        sx, sy = _xy((R_ZOD + R_EXT) / 2, ang_m)
        label = SIGNO_LABEL_TEXTO.get(abrev, abrev[:2])
        ax.text(sx, sy, label, ha="center", va="center",
                fontsize=11, color=cor, fontweight="bold", zorder=4)

    # Circulos dos aneis
    for r, lw_c in [(R_EXT, 1.2), (R_ZOD, 0.9), (R_CSA, 0.7), (R_INT, 1.0)]:
        ax.add_patch(patches.Circle((0, 0), r, color=BORDA, fill=False, lw=lw_c, zorder=5))

    # Divisoes de casas
    for i in range(12):
        ang = _grau_para_rad(i * 30.0, asc)
        eixo = i in (0, 3, 6, 9)
        x0, y0 = _xy(R_CSA, ang)
        x1, y1 = _xy(R_ZOD, ang)
        ax.plot([x0, x1], [y0, y1],
                color=OURO if eixo else LINHA_GRADE,
                lw=1.4 if eixo else 0.6, zorder=6)
        ang_n = ang - SEG_RAD / 2
        nx, ny = _xy((R_CSA + R_ZOD) / 2 - 0.01, ang_n)
        ax.text(nx, ny, str(i + 1),
                ha="center", va="center", fontsize=7,
                color=TEXTO_CINZA, zorder=7)

    # Linhas de aspectos
    COR_ASP = {
        "conjunction": "#8B4513", "trine": "#1565C0",
        "sextile": "#2E7D32", "square": "#C62828", "opposition": "#7B1FA2",
    }
    for asp in dados.aspectos:
        p1, p2, tipo = asp["p1"], asp["p2"], asp["tipo"]
        if p1 not in dados.planetas or p2 not in dados.planetas:
            continue
        cor_a = COR_ASP.get(tipo, "#888888")
        alpha_a = 0.40 if tipo in ("trine", "sextile") else 0.55
        lw_a = 0.8 if tipo in ("trine", "sextile") else 1.1
        a1 = _grau_para_rad(dados.planetas[p1], asc)
        a2 = _grau_para_rad(dados.planetas[p2], asc)
        x1_a, y1_a = _xy(R_ASP, a1)
        x2_a, y2_a = _xy(R_ASP, a2)
        ax.plot([x1_a, x2_a], [y1_a, y2_a],
                color=cor_a, lw=lw_a, alpha=alpha_a, zorder=8)

    # Circulo branco cobre intersecoes
    ax.add_patch(patches.Circle((0, 0), R_ASP - 0.01, color=BG, fill=True, zorder=9))
    ax.add_patch(patches.Circle((0, 0), R_INT, color=BG, fill=True, zorder=10))
    ax.add_patch(patches.Circle((0, 0), R_INT, color=BORDA, fill=False, lw=1.0, zorder=11))

    # Figura humana alquimica
    _desenhar_homem_alquimico(ax, dados)

    # Planetas no anel
    posicoes_ajust = _ajustar_posicoes(
        {k: v for k, v in dados.planetas.items() if k in ORDEM_PLANETAS}, asc
    )

    for nome, grau_ajust in posicoes_ajust.items():
        if nome not in dados.planetas:
            continue
        grau_real = dados.planetas[nome]
        ang_real = _grau_para_rad(grau_real, asc)
        ang_ajust = _grau_para_rad(grau_ajust, asc)
        cor_p = COR_PLANETA.get(nome, TEXTO_ESCURO)
        abrev = PLANETA_ABREV_TEXTO.get(nome, nome[:3])

        px, py = _xy(R_PLN - 0.06, ang_real)
        ax.plot(px, py, "o", color=cor_p, markersize=3.5, zorder=14)

        lx, ly = _xy(R_PLN + 0.06, ang_ajust)
        if abs(ang_real - ang_ajust) > 0.05:
            ax.plot([px, lx], [py, ly], color=cor_p, lw=0.5, alpha=0.35, zorder=13)

        fs_p = 7.5 if nome in ("Ascendant", "Medium_Coeli") else 10
        ax.text(lx, ly, abrev, ha="center", va="center",
                fontsize=fs_p, color=cor_p, fontweight="bold", zorder=15)

        grau_sig = grau_real % 30.0
        ax.text(lx, ly - 0.095, f"{grau_sig:.0f}",
                ha="center", va="center", fontsize=5.5,
                color=cor_p, alpha=0.75, zorder=15)

    # Rodape
    ax.text(0, -1.30,
            f"Mapa Alquimico  |  {dados.data_nascimento}  {dados.hora_nascimento}  |  {dados.cidade_nascimento}",
            ha="center", va="center", fontsize=6.5,
            color=TEXTO_CINZA, zorder=16)

    # --- PAINEL DIREITO ---
    axp.set_facecolor(BG_PAINEL)
    axp.axis("off")
    axp.set_xlim(0, 1)
    axp.set_ylim(0, 1)
    axp.add_patch(patches.FancyBboxPatch(
        (0.02, 0.01), 0.96, 0.97,
        boxstyle="round,pad=0.01",
        linewidth=1.0, edgecolor=BORDA, facecolor=BG_PAINEL,
    ))

    def txt(t, x, y, color=TEXTO_ESCURO, fs=8.5, bold=False):
        axp.text(x, y, t, ha="left", va="top", fontsize=fs,
                 color=color, fontweight="bold" if bold else "normal")

    y = 0.97
    txt(dados.nome_paciente[:22].upper(), 0.06, y, color=OURO, fs=10, bold=True)
    y -= 0.048
    txt(f"{dados.data_nascimento}  {dados.hora_nascimento}", 0.06, y, color=TEXTO_CINZA, fs=7.5)
    y -= 0.033
    txt(dados.cidade_nascimento[:28], 0.06, y, color=TEXTO_CINZA, fs=7.5)
    y -= 0.040
    axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
    y -= 0.030

    txt("POSICOES", 0.06, y, color=OURO, fs=7.5, bold=True)
    y -= 0.030

    for nome_p in ORDEM_PLANETAS:
        if nome_p not in dados.planetas or y < 0.41:
            continue
        grau_abs = dados.planetas[nome_p]
        sig_abrev = dados.signos.get(nome_p, "")
        sig_nome = SIGNO_NOME_PT.get(sig_abrev, sig_abrev)
        grau_sig = grau_abs % 30.0
        casa = dados.casas.get(nome_p)
        casa_txt = f" C{casa}" if casa else ""
        cor_p = COR_PLANETA.get(nome_p, TEXTO_ESCURO)
        abrev_p = PLANETA_ABREV_TEXTO.get(nome_p, nome_p[:3])
        axp.text(0.06, y, abrev_p,
                 ha="left", va="top", fontsize=7.5,
                 color=cor_p, fontweight="bold")
        axp.text(0.32, y, f"{grau_sig:.1f}  {sig_nome}{casa_txt}",
                 ha="left", va="top", fontsize=7.5, color=TEXTO_ESCURO)
        y -= 0.034

    axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
    y -= 0.025

    # Distribuicao de elementos
    txt("ELEMENTOS", 0.06, y, color=OURO, fs=7.5, bold=True)
    y -= 0.028

    contagem = {"Fogo": 0, "Terra": 0, "Ar": 0, "Agua": 0}
    COR_EL = {"Fogo": COR_FOGO, "Terra": COR_TERRA, "Ar": COR_AR, "Agua": COR_AGUA}
    for p in ORDEM_PLANETAS[:10]:
        sg = dados.signos.get(p, "")
        el = ELEM_MAPA.get(sg)
        if el:
            contagem[el] += 1

    total_el = sum(contagem.values()) or 1
    for el, qtd in contagem.items():
        cor_el = COR_EL[el]
        barra = 0.65 * (qtd / total_el)
        axp.add_patch(patches.Rectangle(
            (0.06, y - 0.018), barra, 0.016,
            color=cor_el, alpha=0.75,
        ))
        axp.text(0.73, y - 0.004, f"{el[:2].upper()} {qtd}",
                 ha="left", va="top", fontsize=6.5, color=cor_el, fontweight="bold")
        y -= 0.028

    if y > 0.05:
        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.025
        txt("Mapa Alquimico", 0.06, y, color=TEXTO_CINZA, fs=6.5)
        y -= 0.022
        txt("Escola Joel Aleixo", 0.06, y, color=TEXTO_CINZA, fs=6.5)

    # Salvar
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=BG, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Supabase REST API helpers
# ---------------------------------------------------------------------------
def buscar_mapas_placeholder() -> list[dict]:
    """Busca mapas com imagem_url de placeholder (placehold.co)."""
    url = (
        f"{SUPABASE_URL}/rest/v1/mapas_astrais"
        f"?imagem_url=like.*placehold.co*"
        f"&select=id,terapeuta_id,nome,data_nascimento,hora_nascimento,cidade_nascimento,imagem_url"
    )
    r = requests.get(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    if r.status_code != 200:
        print(f"ERRO ao buscar mapas: {r.status_code} — {r.text}")
        return []
    return r.json()


def upload_imagem_storage(terapeuta_id: str, imagem_bytes: bytes) -> str | None:
    """Faz upload da imagem para Supabase Storage bucket 'mapas'."""
    mapa_id = str(uuid.uuid4())
    storage_path = f"{terapeuta_id}/{mapa_id}.png"
    url = f"{SUPABASE_URL}/storage/v1/object/mapas/{storage_path}"

    r = requests.post(url, headers=STORAGE_HEADERS, data=imagem_bytes)
    if r.status_code not in (200, 201):
        print(f"  ERRO upload Storage: {r.status_code} — {r.text}")
        return None

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/mapas/{storage_path}"
    return public_url


def atualizar_imagem_url(mapa_id: str, imagem_url: str) -> bool:
    """Atualiza o campo imagem_url no registro do mapa."""
    url = f"{SUPABASE_URL}/rest/v1/mapas_astrais?id=eq.{mapa_id}"
    r = requests.patch(url, headers=HEADERS, json={"imagem_url": imagem_url})
    if r.status_code not in (200, 204):
        print(f"  ERRO ao atualizar imagem_url: {r.status_code} — {r.text}")
        return False
    return True


def converter_data_para_ddmmaaaa(data_iso: str) -> str:
    """Converte YYYY-MM-DD para DD/MM/AAAA."""
    partes = data_iso.split("-")
    if len(partes) == 3:
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return data_iso


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=== Gerador de Mapas Demo — Imagens Reais (STANDALONE) ===\n")

    mapas = buscar_mapas_placeholder()
    if not mapas:
        print("Nenhum mapa com placeholder encontrado.")
        return

    print(f"Encontrados {len(mapas)} mapas com placeholder.\n")

    sucesso = 0
    falha = 0

    for mapa in mapas:
        nome = mapa["nome"] or "Paciente"
        data_iso = mapa["data_nascimento"]
        hora = mapa["hora_nascimento"]
        cidade = mapa["cidade_nascimento"]
        terapeuta_id = mapa["terapeuta_id"]
        mapa_id = mapa["id"]

        data_ddmm = converter_data_para_ddmmaaaa(data_iso)

        print(f"[{sucesso + falha + 1}/{len(mapas)}] {nome} — {data_ddmm} {hora} ({cidade})")

        try:
            # Parsing
            partes_data = data_iso.split("-")
            ano, mes_n, dia_n = int(partes_data[0]), int(partes_data[1]), int(partes_data[2])
            partes_hora = hora.split(":")
            hora_n, minuto_n = int(partes_hora[0]), int(partes_hora[1])

            # Geocodificacao
            lat, lon, tz_str = _geocodificar_cidade(cidade)

            # Tentar Kerykeion primeiro, fallback se falhar
            dados = _calcular_via_kerykeion(nome, ano, mes_n, dia_n, hora_n, minuto_n, lat, lon, tz_str)
            if dados is None:
                print("  Usando calculo estimado (fallback)")
                dados = _calcular_fallback(nome, ano, mes_n, dia_n, hora_n, minuto_n)

            # Preencher cidade (pode nao ter sido setada)
            dados.cidade_nascimento = cidade
            dados.data_nascimento = data_ddmm
            dados.hora_nascimento = hora

            # Gerar imagem
            imagem = gerar_imagem_mapa(dados)
            print(f"  Imagem gerada: {len(imagem) // 1024} KB")

        except Exception as e:
            print(f"  ERRO ao gerar imagem: {e}")
            falha += 1
            continue

        # Upload para Storage
        public_url = upload_imagem_storage(terapeuta_id, imagem)
        if not public_url:
            print(f"  SKIP: upload falhou")
            falha += 1
            continue

        print(f"  Upload OK: {public_url}")

        # Atualizar no banco
        if atualizar_imagem_url(mapa_id, public_url):
            print(f"  OK: imagem_url atualizada")
            sucesso += 1
        else:
            print(f"  ERRO: falha ao atualizar banco")
            falha += 1

    print(f"\n=== Resultado: {sucesso} OK / {falha} falhas / {len(mapas)} total ===")


if __name__ == "__main__":
    main()
