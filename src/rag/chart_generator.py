"""
Gerador do Mapa Alquímico — estilo Joel Aleixo.

Design:
- Fundo branco, alto contraste (legível no celular)
- Roda zodiacal colorida por elemento
- FIGURA HUMANA alquímica no centro (como o Joel ensina)
- Planetas marcados com abreviações de texto (sem Unicode que trava no Docker)
- Painel direito com posições e distribuição de elementos
"""

import os
import threading

# MPLCONFIGDIR antes de qualquer import matplotlib — necessário em Docker onde /root pode
# não ser gravável. /tmp é sempre gravável em containers.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib_cache")

import matplotlib
matplotlib.use("Agg")  # backend sem GUI — obrigatório ANTES de qualquer import pyplot

import io
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lock para thread safety — matplotlib não é thread-safe por padrão.
# asyncio.to_thread usa thread pool; requests concorrentes poderiam colidir.
_MPL_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------
BG           = "#FFFFFF"
BG_PAINEL    = "#F5F5F5"
BORDA        = "#999999"
TEXTO_ESCURO = "#111111"
TEXTO_CINZA  = "#555555"
LINHA_GRADE  = "#DDDDDD"
OURO         = "#B8860B"
FIGURA_COR   = "#2C2C2C"  # silhueta humana

COR_FOGO  = "#D32F2F"
COR_TERRA = "#388E3C"
COR_AR    = "#C6A800"
COR_AGUA  = "#1565C0"

ELEMENTO_COR: dict[str, str] = {
    "Ari": COR_FOGO,  "Leo": COR_FOGO,  "Sag": COR_FOGO,
    "Tau": COR_TERRA, "Vir": COR_TERRA, "Cap": COR_TERRA,
    "Gem": COR_AR,    "Lib": COR_AR,    "Aqu": COR_AR,
    "Can": COR_AGUA,  "Sco": COR_AGUA,  "Pis": COR_AGUA,
}

# ---------------------------------------------------------------------------
# Signos — abreviações SEM Unicode (evita crash no Docker slim)
# ---------------------------------------------------------------------------
SIGNOS_ABREV = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir",
                "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

SIGNO_LABEL: dict[str, str] = {
    "Ari": "AR", "Tau": "TA", "Gem": "GE", "Can": "CA",
    "Leo": "LE", "Vir": "VI", "Lib": "LI", "Sco": "ES",
    "Sag": "SA", "Cap": "CP", "Aqu": "AQ", "Pis": "PI",
}

SIGNO_NOME_PT: dict[str, str] = {
    "Ari": "Aries",  "Tau": "Touro",    "Gem": "Gemeos",  "Can": "Cancer",
    "Leo": "Leao",   "Vir": "Virgem",   "Lib": "Libra",   "Sco": "Escorp.",
    "Sag": "Sagit.", "Cap": "Capric.",  "Aqu": "Aquario", "Pis": "Peixes",
}

# ---------------------------------------------------------------------------
# Planetas — abreviações SEM Unicode
# ---------------------------------------------------------------------------
ORDEM_PLANETAS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Ascendant", "Medium_Coeli",
]

PLANETA_ABREV: dict[str, str] = {
    "Sun":          "Sol",
    "Moon":         "Lua",
    "Mercury":      "Mer",
    "Venus":        "Ven",
    "Mars":         "Mar",
    "Jupiter":      "Jup",
    "Saturn":       "Sat",
    "Uranus":       "Ura",
    "Neptune":      "Net",
    "Pluto":        "Plu",
    "Ascendant":    "Asc",
    "Medium_Coeli": "MC",
}

PLANETA_NOME_PT: dict[str, str] = {
    "Sun":          "Sol",
    "Moon":         "Lua",
    "Mercury":      "Mercurio",
    "Venus":        "Venus",
    "Mars":         "Marte",
    "Jupiter":      "Jupiter",
    "Saturn":       "Saturno",
    "Uranus":       "Urano",
    "Neptune":      "Netuno",
    "Pluto":        "Plutao",
    "Ascendant":    "Ascendente",
    "Medium_Coeli": "MC",
}

COR_PLANETA: dict[str, str] = {
    "Sun":          "#E65100",
    "Moon":         "#1565C0",
    "Mercury":      "#2E7D32",
    "Venus":        "#AD1457",
    "Mars":         "#C62828",
    "Jupiter":      "#4527A0",
    "Saturn":       "#37474F",
    "Uranus":       "#006064",
    "Neptune":      "#1A237E",
    "Pluto":        "#4A0E4E",
    "Ascendant":    "#000000",
    "Medium_Coeli": "#000000",
}

ELEM_MAPA: dict[str, str] = {
    "Ari": "Fogo", "Leo": "Fogo", "Sag": "Fogo",
    "Tau": "Terra", "Vir": "Terra", "Cap": "Terra",
    "Gem": "Ar",    "Lib": "Ar",   "Aqu": "Ar",
    "Can": "Agua",  "Sco": "Agua", "Pis": "Agua",
}

# ---------------------------------------------------------------------------
# Correspondência signo ↔ parte do corpo (tradição alquímica)
# ---------------------------------------------------------------------------
SIGNO_CORPO: dict[str, str] = {
    "Ari": "Cabeca",    "Tau": "Pescoco",
    "Gem": "Ombros",    "Can": "Peito",
    "Leo": "Coracao",   "Vir": "Abdomen",
    "Lib": "Rins",      "Sco": "Pelve",
    "Sag": "Coxas",     "Cap": "Joelhos",
    "Aqu": "Pernas",    "Pis": "Pes",
}

# ---------------------------------------------------------------------------
# Estrutura de dados (compatível com astrologia.py)
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
        self.nome_paciente    = nome_paciente
        self.data_nascimento  = data_nascimento
        self.hora_nascimento  = hora_nascimento
        self.cidade_nascimento = cidade_nascimento
        self.planetas  = planetas
        self.signos    = signos
        self.casas     = casas
        self.aspectos  = aspectos
        self.ascendente_grau = ascendente_grau


# ---------------------------------------------------------------------------
# Converte sujeito Kerykeion → DadosMapa
# ---------------------------------------------------------------------------


def dados_mapa_de_sujeito(
    sujeito: Any,
    nome_paciente: str,
    data_nascimento: str,
    hora_nascimento: str,
    cidade_nascimento: str,
) -> "DadosMapa":
    atributos_planetas = [
        ("sun", "Sun"), ("moon", "Moon"), ("mercury", "Mercury"),
        ("venus", "Venus"), ("mars", "Mars"), ("jupiter", "Jupiter"),
        ("saturn", "Saturn"), ("uranus", "Uranus"), ("neptune", "Neptune"),
        ("pluto", "Pluto"), ("ascendant", "Ascendant"), ("medium_coeli", "Medium_Coeli"),
    ]
    _HOUSE_STR_TO_INT = {
        "First_House": 1, "Second_House": 2, "Third_House": 3,
        "Fourth_House": 4, "Fifth_House": 5, "Sixth_House": 6,
        "Seventh_House": 7, "Eighth_House": 8, "Ninth_House": 9,
        "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
    }

    planetas: dict[str, float] = {}
    signos:   dict[str, str]   = {}
    casas:    dict[str, Optional[int]] = {}

    for attr, nome in atributos_planetas:
        ponto = getattr(sujeito, attr, None)
        if ponto is not None:
            sign_idx = SIGNOS_ABREV.index(ponto.sign) if ponto.sign in SIGNOS_ABREV else 0
            grau_abs = sign_idx * 30.0 + float(ponto.position)
            planetas[nome] = grau_abs % 360.0
            signos[nome]   = ponto.sign
            casa_raw = getattr(ponto, "house", None)
            if isinstance(casa_raw, str):
                casas[nome] = _HOUSE_STR_TO_INT.get(casa_raw)
            elif isinstance(casa_raw, int):
                casas[nome] = casa_raw
            else:
                casas[nome] = None

    asc_grau = planetas.get("Ascendant", 0.0)

    aspectos: list[dict[str, Any]] = []
    try:
        from kerykeion.aspects.aspects_factory import AspectsFactory
        aspectos_model = AspectsFactory.single_chart_aspects(sujeito)
        planetas_pessoais = {"Sun", "Moon", "Mercury", "Venus", "Mars",
                             "Jupiter", "Saturn", "Ascendant", "Medium_Coeli"}
        tipos_major = {"conjunction", "opposition", "square", "trine", "sextile"}
        for asp in aspectos_model.aspects:
            if (asp.aspect in tipos_major
                    and asp.p1_name in planetas_pessoais
                    and asp.p2_name in planetas_pessoais):
                aspectos.append({
                    "p1":   asp.p1_name,
                    "p2":   asp.p2_name,
                    "tipo": asp.aspect,
                    "orbe": float(asp.orbit),
                })
    except Exception as e:
        logger.warning(f"Aspectos indisponiveis para o grafico: {e}")

    return DadosMapa(
        nome_paciente=nome_paciente,
        data_nascimento=data_nascimento,
        hora_nascimento=hora_nascimento,
        cidade_nascimento=cidade_nascimento,
        planetas=planetas,
        signos=signos,
        casas=casas,
        aspectos=aspectos,
        ascendente_grau=asc_grau,
    )


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------


def _grau_para_rad(grau_ecl: float, asc_grau: float) -> float:
    """Converte grau eclíptico → ângulo cartesiano. Ascendente fica à esquerda (180°)."""
    delta = (grau_ecl - asc_grau) % 360.0
    angulo_graus = 180.0 - delta
    return math.radians(angulo_graus)


def _xy(raio: float, ang_rad: float) -> tuple[float, float]:
    return raio * math.cos(ang_rad), raio * math.sin(ang_rad)


# ---------------------------------------------------------------------------
# Figura humana alquímica (homem inscrito na roda — estilo Joel Aleixo)
# ---------------------------------------------------------------------------


def _desenhar_homem_alquimico(ax: Any, dados: "DadosMapa") -> None:
    """
    Desenha a silhueta humana alquímica no centro da roda.
    Os signos ativos (onde o nativo tem planetas) são destacados
    na parte do corpo correspondente.
    """
    import matplotlib.patches as patches

    cor  = FIGURA_COR
    lw   = 1.8

    # ── Cabeça ────────────────────────────────────────────────────────────
    head = patches.Circle((0, 0.395), 0.090, color=BG, ec=cor, lw=lw, zorder=22)
    ax.add_patch(head)

    # ── Pescoço ──────────────────────────────────────────────────────────
    ax.plot([0, 0], [0.305, 0.262], color=cor, lw=lw, zorder=22)

    # ── Ombros ───────────────────────────────────────────────────────────
    ax.plot([-0.215, 0.215], [0.262, 0.262], color=cor, lw=lw, zorder=22)

    # ── Braços (estendidos — figura Vitruviana) ───────────────────────────
    ax.plot([-0.215, -0.510], [0.262, 0.160], color=cor, lw=lw, zorder=22)
    ax.plot([ 0.215,  0.510], [0.262, 0.160], color=cor, lw=lw, zorder=22)

    # ── Torso ─────────────────────────────────────────────────────────────
    ax.plot([0, 0], [0.262, -0.100], color=cor, lw=lw, zorder=22)

    # ── Quadris ──────────────────────────────────────────────────────────
    ax.plot([-0.175, 0.175], [-0.100, -0.100], color=cor, lw=lw, zorder=22)

    # ── Pernas ───────────────────────────────────────────────────────────
    ax.plot([-0.175, -0.120], [-0.100, -0.500], color=cor, lw=lw, zorder=22)
    ax.plot([ 0.175,  0.120], [-0.100, -0.500], color=cor, lw=lw, zorder=22)

    # ── Pontos articulares (joelhos) ──────────────────────────────────────
    for xk, yk in [(-0.147, -0.300), (0.147, -0.300)]:
        ax.plot(xk, yk, "o", color=cor, markersize=3, zorder=22)

    # ── Marcação de planetas no corpo ────────────────────────────────────
    # Mapeia onde cada planeta do nativo está no corpo via signo
    _CORPO_XY: dict[str, tuple[float, float]] = {
        "Cabeca":   (0,     0.395),
        "Pescoco":  (0,     0.270),
        "Ombros":   (0,     0.262),
        "Peito":    (0,     0.185),
        "Coracao":  (0,     0.130),
        "Abdomen":  (0,     0.050),
        "Rins":     (0,    -0.030),
        "Pelve":    (0,    -0.100),
        "Coxas":    (0,    -0.185),
        "Joelhos":  (0,    -0.300),
        "Pernas":   (0,    -0.390),
        "Pes":      (0,    -0.490),
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
        cor_p  = COR_PLANETA.get(nome_p, OURO)
        abrev  = PLANETA_ABREV.get(nome_p, nome_p[:3])
        ax.plot(cx + 0.05, cy, "o", color=cor_p, markersize=4.5, zorder=23)
        ax.text(cx + 0.14, cy, abrev,
                ha="left", va="center", fontsize=5.5,
                color=cor_p, fontweight="bold", zorder=23)

    # ── Rótulos dos 4 elementos nos cantos interiores da roda ─────────────
    elem_dados = [
        ( 0.000,  0.570, "FOGO",  COR_FOGO),
        ( 0.570,  0.000, "AR",    COR_AR),
        ( 0.000, -0.570, "TERRA", COR_TERRA),
        (-0.570,  0.000, "AGUA",  COR_AGUA),
    ]
    for ex, ey, elabel, ecor in elem_dados:
        ax.text(ex, ey, elabel, ha="center", va="center",
                fontsize=6.5, color=ecor, fontweight="bold",
                alpha=0.65, zorder=21)


# ---------------------------------------------------------------------------
# Ajuste de sobreposição de planetas
# ---------------------------------------------------------------------------


def _ajustar_posicoes(
    posicoes: dict[str, float],
    asc: float,
    limiar_graus: float = 7.0,
) -> dict[str, float]:
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
# Renderização principal
# ---------------------------------------------------------------------------


def gerar_imagem_mapa_natal(dados: "DadosMapa") -> bytes:
    """
    Gera PNG do Mapa Alquimico — roda zodiacal com homem no centro.
    Retorna bytes PNG. Levanta RuntimeError se falhar.
    """
    if not _MPL_LOCK.acquire(timeout=60.0):
        raise RuntimeError("Timeout aguardando lock matplotlib (60s) — servidor sobrecarregado")
    try:
        return _gerar_imagem_locked(dados)
    finally:
        _MPL_LOCK.release()


def _gerar_imagem_locked(dados: "DadosMapa") -> bytes:
    """Executa a geração da imagem com o lock _MPL_LOCK já adquirido."""
    try:
        # Usar Figure() diretamente — evita estado global do pyplot (thread-unsafe).
        # matplotlib docs recomendam este padrão para ambientes multi-thread / servidor.
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.patches as patches
        import numpy as np

        # ── Figura ──────────────────────────────────────────────────────────
        fig = Figure(figsize=(12, 9), facecolor=BG, dpi=110)
        FigureCanvasAgg(fig)  # canvas Agg sem estado global

        # Roda (esquerda 63%) + painel (direita 35%)
        ax  = fig.add_axes([0.01, 0.05, 0.60, 0.90])
        axp = fig.add_axes([0.63, 0.04, 0.35, 0.92])

        ax.set_aspect("equal")
        ax.set_facecolor(BG)
        ax.set_xlim(-1.32, 1.32)
        ax.set_ylim(-1.32, 1.32)
        ax.axis("off")

        asc = dados.ascendente_grau

        # Raios
        R_EXT  = 1.18   # borda externa zodíaco
        R_ZOD  = 0.94   # borda interna zodíaco / externa planetas
        R_PLN  = 0.81   # anel dos planetas
        R_CSA  = 0.68   # divisões de casas
        R_INT  = 0.63   # círculo interno (figura humana)
        R_ASP  = 0.59   # linhas de aspectos

        # ── Anel zodiacal ────────────────────────────────────────────────────
        # Cada signo ocupa exatamente 30° no sentido horário (sentido da progressão zodiacal).
        # ang0 sempre diminui 30° para ang1 — sem linspace entre pontos que cruzam ±π.
        SEG_RAD = math.pi / 6  # 30° em radianos
        for i, abrev in enumerate(SIGNOS_ABREV):
            ang0 = _grau_para_rad(i * 30.0, asc)
            ang1 = ang0 - SEG_RAD  # sempre exatos 30° horários — sem wrap-around
            cor  = ELEMENTO_COR.get(abrev, "#CCCCCC")
            t    = np.linspace(ang0, ang1, 40)

            # Fundo colorido translúcido
            xs = list(R_EXT * np.cos(t)) + list(R_ZOD * np.cos(t[::-1]))
            ys = list(R_EXT * np.sin(t)) + list(R_ZOD * np.sin(t[::-1]))
            ax.fill(xs, ys, color=cor, alpha=0.18, zorder=2)

            # Bordas do segmento
            ang_div = ang0
            x0, y0 = _xy(R_ZOD, ang_div)
            x1, y1 = _xy(R_EXT, ang_div)
            ax.plot([x0, x1], [y0, y1], color=cor, lw=0.8, alpha=0.55, zorder=3)

            # Rótulo do signo (abreviação 2 letras) — posicionado no meio do segmento
            ang_m = ang0 - SEG_RAD / 2
            sx, sy = _xy((R_ZOD + R_EXT) / 2, ang_m)
            label = SIGNO_LABEL.get(abrev, abrev[:2])
            ax.text(sx, sy, label,
                    ha="center", va="center", fontsize=9,
                    color=cor, fontweight="bold", zorder=4)

        # Círculos do anel
        for r, lw_c in [(R_EXT, 1.2), (R_ZOD, 0.9), (R_CSA, 0.7), (R_INT, 1.0)]:
            ax.add_patch(patches.Circle((0, 0), r, color=BORDA, fill=False, lw=lw_c, zorder=5))

        # ── Divisões de casas ────────────────────────────────────────────────
        for i in range(12):
            ang   = _grau_para_rad(i * 30.0, asc)
            eixo  = i in (0, 3, 6, 9)
            x0, y0 = _xy(R_CSA, ang)
            x1, y1 = _xy(R_ZOD, ang)
            ax.plot([x0, x1], [y0, y1],
                    color=OURO if eixo else LINHA_GRADE,
                    lw=1.4 if eixo else 0.6, zorder=6)
            # Número da casa — posicionado 15° depois da borda (metade do segmento)
            ang_n = ang - SEG_RAD / 2
            nx, ny = _xy((R_CSA + R_ZOD) / 2 - 0.01, ang_n)
            ax.text(nx, ny, str(i + 1),
                    ha="center", va="center", fontsize=7,
                    color=TEXTO_CINZA, zorder=7)

        # ── Linhas de aspectos ───────────────────────────────────────────────
        COR_ASP = {
            "conjunction": "#8B4513",
            "trine":       "#1565C0",
            "sextile":     "#2E7D32",
            "square":      "#C62828",
            "opposition":  "#7B1FA2",
        }
        for asp in dados.aspectos:
            p1, p2, tipo = asp["p1"], asp["p2"], asp["tipo"]
            if p1 not in dados.planetas or p2 not in dados.planetas:
                continue
            cor_a  = COR_ASP.get(tipo, "#888888")
            alpha_a = 0.40 if tipo in ("trine", "sextile") else 0.55
            lw_a   = 0.8  if tipo in ("trine", "sextile") else 1.1
            a1 = _grau_para_rad(dados.planetas[p1], asc)
            a2 = _grau_para_rad(dados.planetas[p2], asc)
            x1_a, y1_a = _xy(R_ASP, a1)
            x2_a, y2_a = _xy(R_ASP, a2)
            ax.plot([x1_a, x2_a], [y1_a, y2_a],
                    color=cor_a, lw=lw_a, alpha=alpha_a, zorder=8)

        # Círculo branco cobre as interseções de aspectos
        ax.add_patch(patches.Circle((0, 0), R_ASP - 0.01, color=BG, fill=True, zorder=9))
        ax.add_patch(patches.Circle((0, 0), R_INT, color=BG, fill=True, zorder=10))
        ax.add_patch(patches.Circle((0, 0), R_INT, color=BORDA, fill=False, lw=1.0, zorder=11))

        # ── Figura humana alquímica ──────────────────────────────────────────
        _desenhar_homem_alquimico(ax, dados)

        # ── Planetas no anel ─────────────────────────────────────────────────
        posicoes_ajust = _ajustar_posicoes(
            {k: v for k, v in dados.planetas.items() if k in ORDEM_PLANETAS}, asc
        )

        for nome, grau_ajust in posicoes_ajust.items():
            if nome not in dados.planetas:
                continue
            grau_real = dados.planetas[nome]
            ang_real  = _grau_para_rad(grau_real, asc)
            ang_ajust = _grau_para_rad(grau_ajust, asc)
            cor_p     = COR_PLANETA.get(nome, TEXTO_ESCURO)
            abrev     = PLANETA_ABREV.get(nome, nome[:3])

            # Ponto exato (menor)
            px, py = _xy(R_PLN - 0.06, ang_real)
            ax.plot(px, py, "o", color=cor_p, markersize=3.5, zorder=14)

            # Rótulo com abreviação (posição ajustada)
            lx, ly = _xy(R_PLN + 0.06, ang_ajust)
            if abs(ang_real - ang_ajust) > 0.05:
                ax.plot([px, lx], [py, ly], color=cor_p, lw=0.5, alpha=0.35, zorder=13)

            fs_p = 7 if nome in ("Ascendant", "Medium_Coeli") else 8.5
            ax.text(lx, ly, abrev,
                    ha="center", va="center", fontsize=fs_p,
                    color=cor_p, fontweight="bold", zorder=15)

            # Grau dentro do signo
            grau_sig = grau_real % 30.0
            dx, dy = _xy(R_PLN + 0.06, ang_ajust)
            ax.text(dx, dy - 0.095, f"{grau_sig:.0f}",
                    ha="center", va="center", fontsize=5.5,
                    color=cor_p, alpha=0.75, zorder=15)

        # Rodapé com dados
        ax.text(0, -1.30,
                f"Swiss Ephemeris  |  {dados.data_nascimento}  {dados.hora_nascimento}  |  {dados.cidade_nascimento}",
                ha="center", va="center", fontsize=6.5,
                color=TEXTO_CINZA, zorder=16)

        # ── PAINEL DIREITO ───────────────────────────────────────────────────
        axp.set_facecolor(BG_PAINEL)
        axp.axis("off")
        axp.set_xlim(0, 1)
        axp.set_ylim(0, 1)
        axp.add_patch(patches.FancyBboxPatch(
            (0.02, 0.01), 0.96, 0.97,
            boxstyle="round,pad=0.01",
            linewidth=1.0, edgecolor=BORDA,
            facecolor=BG_PAINEL,
        ))

        def txt(t: str, x: float, y: float,
                color: str = TEXTO_ESCURO,
                fs: float = 8.5,
                bold: bool = False) -> None:
            axp.text(x, y, t, ha="left", va="top", fontsize=fs,
                     color=color, fontweight="bold" if bold else "normal")

        y = 0.97

        # Nome em destaque
        txt(dados.nome_paciente[:22].upper(), 0.06, y, color=OURO, fs=10, bold=True)
        y -= 0.048

        # Data / cidade
        txt(f"{dados.data_nascimento}  {dados.hora_nascimento}", 0.06, y, color=TEXTO_CINZA, fs=7.5)
        y -= 0.033
        txt(dados.cidade_nascimento[:28], 0.06, y, color=TEXTO_CINZA, fs=7.5)
        y -= 0.040

        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.030

        # Posições planetárias
        txt("POSICOES", 0.06, y, color=OURO, fs=7.5, bold=True)
        y -= 0.030

        for nome_p in ORDEM_PLANETAS:
            if nome_p not in dados.planetas or y < 0.41:
                continue
            grau_abs = dados.planetas[nome_p]
            sig_abrev = dados.signos.get(nome_p, "")
            sig_nome  = SIGNO_NOME_PT.get(sig_abrev, sig_abrev)
            grau_sig  = grau_abs % 30.0
            casa      = dados.casas.get(nome_p)
            casa_txt  = f" C{casa}" if casa else ""
            cor_p     = COR_PLANETA.get(nome_p, TEXTO_ESCURO)
            abrev_p   = PLANETA_ABREV.get(nome_p, nome_p[:3])
            axp.text(0.06, y, abrev_p,
                     ha="left", va="top", fontsize=7.5,
                     color=cor_p, fontweight="bold")
            axp.text(0.32, y, f"{grau_sig:.1f}  {sig_nome}{casa_txt}",
                     ha="left", va="top", fontsize=7.5,
                     color=TEXTO_ESCURO)
            y -= 0.034

        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.025

        # Distribuição de elementos
        txt("ELEMENTOS", 0.06, y, color=OURO, fs=7.5, bold=True)
        y -= 0.028

        contagem: dict[str, int] = {"Fogo": 0, "Terra": 0, "Ar": 0, "Agua": 0}
        COR_EL = {"Fogo": COR_FOGO, "Terra": COR_TERRA, "Ar": COR_AR, "Agua": COR_AGUA}
        for p in ORDEM_PLANETAS[:10]:
            sg = dados.signos.get(p, "")
            el = ELEM_MAPA.get(sg)
            if el:
                contagem[el] += 1

        total_el = sum(contagem.values()) or 1
        for el, qtd in contagem.items():
            cor_el = COR_EL[el]
            barra  = 0.65 * (qtd / total_el)
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

        # ── Salva ────────────────────────────────────────────────────────────
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110,
                    facecolor=BG, bbox_inches="tight")
        buf.seek(0)
        png_bytes = buf.read()
        logger.info(f"Mapa Alquimico gerado: {len(png_bytes) // 1024} KB")
        return png_bytes

    except Exception as e:
        logger.error(f"Falha ao gerar imagem do mapa natal: {e}", exc_info=True)
        raise RuntimeError(f"Falha na geracao da imagem: {e}") from e
