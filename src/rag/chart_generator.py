"""
Gerador de imagens de mapa natal — estilo clássico, fundo branco, legível no celular.

Design inspirado no estilo Astro.com:
- Fundo branco com alto contraste
- Anel zodiacal colorido por elemento
- Planetas com glifos e graus visíveis
- Linhas de aspectos coloridas (azul=harmônico, vermelho=tenso)
- Painel de posições à direita
- 1100×900px, otimizado para tela de celular
"""

import matplotlib
matplotlib.use("Agg")  # backend sem GUI — obrigatório em servidor antes de qualquer import pyplot

import io
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cores — fundo claro, alto contraste
# ---------------------------------------------------------------------------

BG           = "#FFFFFF"
BG_PAINEL    = "#F7F7F7"
BORDA        = "#AAAAAA"
TEXTO_ESCURO = "#111111"
TEXTO_CINZA  = "#555555"
LINHA_GRADE  = "#CCCCCC"
OURO         = "#B8860B"

# Elementos — cores saturadas para boa leitura em celular
COR_FOGO  = "#E53935"   # Áries, Leão, Sagitário
COR_TERRA = "#388E3C"   # Touro, Virgem, Capricórnio
COR_AR    = "#C6A800"   # Gêmeos, Libra, Aquário
COR_AGUA  = "#1565C0"   # Câncer, Escorpião, Peixes

ELEMENTO_COR: dict[str, str] = {
    "Ari": COR_FOGO,  "Leo": COR_FOGO,  "Sag": COR_FOGO,
    "Tau": COR_TERRA, "Vir": COR_TERRA, "Cap": COR_TERRA,
    "Gem": COR_AR,    "Lib": COR_AR,    "Aqu": COR_AR,
    "Can": COR_AGUA,  "Sco": COR_AGUA,  "Pis": COR_AGUA,
}

SIGNOS_UNICODE = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
SIGNOS_ABREV   = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir",
                  "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
SIGNOS_NOME_PT = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]

# Aspectos
COR_ASPECTO: dict[str, str] = {
    "conjunction": "#8B4513",   # marrom
    "trine":       "#1565C0",   # azul — harmônico forte
    "sextile":     "#2E7D32",   # verde — harmônico leve
    "square":      "#C62828",   # vermelho — tensão
    "opposition":  "#7B1FA2",   # roxo — oposição
}
SIGLA_ASPECTO: dict[str, str] = {
    "conjunction": "☌",
    "opposition":  "☍",
    "square":      "□",
    "trine":       "△",
    "sextile":     "✶",
}

# Planetas
PLANETA_GLIFO: dict[str, str] = {
    "Sun":          "☉",
    "Moon":         "☽",
    "Mercury":      "☿",
    "Venus":        "♀",
    "Mars":         "♂",
    "Jupiter":      "♃",
    "Saturn":       "♄",
    "Uranus":       "♅",
    "Neptune":      "♆",
    "Pluto":        "♇",
    "Ascendant":    "Asc",
    "Medium_Coeli": "MC",
}

PLANETA_NOME_PT: dict[str, str] = {
    "Sun":          "Sol",
    "Moon":         "Lua",
    "Mercury":      "Mercúrio",
    "Venus":        "Vênus",
    "Mars":         "Marte",
    "Jupiter":      "Júpiter",
    "Saturn":       "Saturno",
    "Uranus":       "Urano",
    "Neptune":      "Netuno",
    "Pluto":        "Plutão",
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
    "Saturn":       "#1B5E20",
    "Uranus":       "#006064",
    "Neptune":      "#1A237E",
    "Pluto":        "#4A0E4E",
    "Ascendant":    "#000000",
    "Medium_Coeli": "#000000",
}

ORDEM_PLANETAS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Ascendant", "Medium_Coeli",
]

ELEM_MAPA: dict[str, str] = {
    "Ari": "Fogo", "Leo": "Fogo", "Sag": "Fogo",
    "Tau": "Terra", "Vir": "Terra", "Cap": "Terra",
    "Gem": "Ar", "Lib": "Ar", "Aqu": "Ar",
    "Can": "Água", "Sco": "Água", "Pis": "Água",
}

# ---------------------------------------------------------------------------
# Estruturas de dados (inalteradas — compatibilidade com astrologia.py)
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
        logger.warning(f"Aspectos indisponíveis para o gráfico: {e}")

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
    """
    Converte grau eclíptico → ângulo cartesiano para o gráfico.
    Ascendente fica à esquerda (180°). Sentido anti-horário.
    """
    delta = (grau_ecl - asc_grau) % 360.0
    angulo_graus = 180.0 - delta
    return math.radians(angulo_graus)


def _xy(raio: float, ang_rad: float) -> tuple[float, float]:
    return raio * math.cos(ang_rad), raio * math.sin(ang_rad)


# ---------------------------------------------------------------------------
# Renderização principal — estilo clássico fundo branco
# ---------------------------------------------------------------------------

def gerar_imagem_mapa_natal(dados: "DadosMapa") -> bytes:
    """
    Gera PNG do mapa natal estilo clássico (fundo branco, legível em celular).
    Retorna bytes PNG.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        import numpy as np

        # ── Figura ──────────────────────────────────────────────────────────
        fig = plt.figure(figsize=(13, 9), facecolor=BG, dpi=110)

        # Dois eixos: roda (esquerda) + painel (direita)
        ax  = fig.add_axes([0.01, 0.04, 0.62, 0.92])   # roda
        axp = fig.add_axes([0.65, 0.04, 0.34, 0.92])   # painel

        # ── RODA NATAL ───────────────────────────────────────────────────────
        ax.set_aspect("equal")
        ax.set_facecolor(BG)
        ax.set_xlim(-1.35, 1.35)
        ax.set_ylim(-1.35, 1.35)
        ax.axis("off")

        asc = dados.ascendente_grau

        # Raios
        R_EXT    = 1.22   # borda externa zodíaco
        R_ZOD    = 0.97   # borda interna zodíaco / externa casas
        R_CASA   = 0.72   # borda interna anel casas
        R_PLAN   = 0.84   # anel dos planetas
        R_ASP    = 0.68   # raio das linhas de aspectos

        # ── Anel zodiacal (fundo cinza claro + colorido por elemento) ────────
        for i, abrev in enumerate(SIGNOS_ABREV):
            ang0 = _grau_para_rad(i * 30.0, asc)
            ang1 = _grau_para_rad((i + 1) * 30.0, asc)
            cor  = ELEMENTO_COR.get(abrev, "#CCCCCC")

            # Fatia colorida (fill)
            t = np.linspace(ang0, ang1, 40)
            xs = list(R_EXT * np.cos(t)) + list(R_ZOD * np.cos(t[::-1]))
            ys = list(R_EXT * np.sin(t)) + list(R_ZOD * np.sin(t[::-1]))
            ax.fill(xs, ys, color=cor, alpha=0.15, zorder=2)

            # Borda da fatia
            x0, y0 = _xy(R_ZOD, ang0)
            x1, y1 = _xy(R_EXT, ang0)
            ax.plot([x0, x1], [y0, y1], color=cor, lw=0.9, alpha=0.6, zorder=3)

            # Símbolo do signo (centro da fatia)
            ang_m = (ang0 + ang1) / 2
            r_sim = (R_ZOD + R_EXT) / 2
            sx, sy = _xy(r_sim, ang_m)
            ax.text(sx, sy, SIGNOS_UNICODE[i],
                    ha="center", va="center", fontsize=13,
                    color=cor, fontweight="bold", zorder=4)

        # Círculos externos
        ax.add_patch(plt.Circle((0, 0), R_EXT,  color=BORDA, fill=False, lw=1.2, zorder=5))
        ax.add_patch(plt.Circle((0, 0), R_ZOD,  color=BORDA, fill=False, lw=0.8, zorder=5))
        ax.add_patch(plt.Circle((0, 0), R_CASA, color=BORDA, fill=False, lw=0.8, zorder=5))

        # ── Linhas de casas ──────────────────────────────────────────────────
        for i in range(12):
            ang = _grau_para_rad(i * 30.0, asc)
            x0, y0 = _xy(R_CASA, ang)
            x1, y1 = _xy(R_ZOD,  ang)
            eixo = i in (0, 3, 6, 9)
            ax.plot([x0, x1], [y0, y1],
                    color=OURO if eixo else LINHA_GRADE,
                    lw=1.5 if eixo else 0.7, zorder=6)

            # Número da casa
            ang_n = _grau_para_rad((i + 0.5) * 30.0, asc)
            r_n   = (R_CASA + R_ZOD) / 2
            nx, ny = _xy(r_n, ang_n)
            ax.text(nx, ny, str(i + 1),
                    ha="center", va="center", fontsize=7.5,
                    color=TEXTO_CINZA, zorder=7)

        # ── Linhas de aspectos ───────────────────────────────────────────────
        for asp in dados.aspectos:
            p1, p2, tipo = asp["p1"], asp["p2"], asp["tipo"]
            if p1 not in dados.planetas or p2 not in dados.planetas:
                continue
            cor_a  = COR_ASPECTO.get(tipo, "#888888")
            alpha_a = 0.45 if tipo in ("trine", "sextile") else 0.60
            lw_a   = 0.9  if tipo in ("trine", "sextile") else 1.2

            a1 = _grau_para_rad(dados.planetas[p1], asc)
            a2 = _grau_para_rad(dados.planetas[p2], asc)
            x1, y1 = _xy(R_ASP, a1)
            x2, y2 = _xy(R_ASP, a2)
            ax.plot([x1, x2], [y1, y2], color=cor_a, lw=lw_a, alpha=alpha_a, zorder=8)

        # Círculo central (branco para cobrir cruzamentos de aspectos)
        ax.add_patch(plt.Circle((0, 0), R_ASP - 0.01, color=BG, fill=True, zorder=9))
        ax.add_patch(plt.Circle((0, 0), R_ASP - 0.01, color=LINHA_GRADE, fill=False, lw=0.6, zorder=10))

        # Ponto dourado no centro
        ax.add_patch(plt.Circle((0, 0), 0.04, color=OURO, fill=True, alpha=0.6, zorder=11))

        # ── Planetas no anel ─────────────────────────────────────────────────
        posicoes_ajustadas = _ajustar_posicoes(
            {k: v for k, v in dados.planetas.items() if k in ORDEM_PLANETAS}, asc
        )

        for nome, grau in posicoes_ajustadas.items():
            if nome not in dados.planetas:
                continue
            grau_orig = dados.planetas[nome]
            ang_orig  = _grau_para_rad(grau_orig, asc)
            ang_ajust = _grau_para_rad(grau, asc)

            cor_p  = COR_PLANETA.get(nome, "#000000")
            glifo  = PLANETA_GLIFO.get(nome, "?")
            signo  = dados.signos.get(nome, "")
            grau_s = grau_orig % 30.0

            # Ponto de posição exata
            px, py = _xy(R_PLAN - 0.05, ang_orig)
            ax.plot(px, py, "o", color=cor_p, markersize=3.5, zorder=12)

            # Linha de conexão se ajustado
            gx, gy = _xy(R_PLAN + 0.05, ang_ajust)
            if abs(ang_orig - ang_ajust) > 0.04:
                ax.plot([px, gx], [py, gy], color=cor_p, lw=0.5, alpha=0.4, zorder=12)

            # Glifo
            fs = 8 if nome in ("Ascendant", "Medium_Coeli") else 11
            ax.text(gx, gy, glifo,
                    ha="center", va="center", fontsize=fs,
                    color=cor_p, fontweight="bold", zorder=13)

            # Grau no signo abaixo do glifo (menor)
            deg_lbl = f"{grau_s:.0f}°"
            ax.text(gx, gy - 0.10, deg_lbl,
                    ha="center", va="center", fontsize=6,
                    color=cor_p, alpha=0.80, zorder=13)

        # Título abaixo da roda
        ax.text(0, -1.33,
                f"Swiss Ephemeris  ·  {dados.data_nascimento}  {dados.hora_nascimento}  ·  {dados.cidade_nascimento}",
                ha="center", va="center", fontsize=7,
                color=TEXTO_CINZA, zorder=14)

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
                bold: bool = False,
                alpha: float = 1.0) -> None:
            axp.text(x, y, t,
                     ha="left", va="top", fontsize=fs,
                     color=color,
                     fontweight="bold" if bold else "normal",
                     alpha=alpha)

        y = 0.97

        # Nome
        nome_d = dados.nome_paciente[:24]
        txt(nome_d.upper(), 0.06, y, color=OURO, fs=10, bold=True)
        y -= 0.045

        # Data / hora / cidade
        txt(f"{dados.data_nascimento}  {dados.hora_nascimento}", 0.06, y, color=TEXTO_CINZA, fs=7.5)
        y -= 0.030
        txt(dados.cidade_nascimento[:30], 0.06, y, color=TEXTO_CINZA, fs=7.5)
        y -= 0.038

        # Separador
        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.030

        # Posições planetárias
        txt("POSIÇÕES", 0.06, y, color=OURO, fs=7.5, bold=True)
        y -= 0.030

        dy = 0.032
        for nome_p in ORDEM_PLANETAS:
            if nome_p not in dados.planetas or y < 0.40:
                continue
            grau_abs = dados.planetas[nome_p]
            sig_abrev = dados.signos.get(nome_p, "")
            sig_nome  = SIGNOS_NOME_PT[SIGNOS_ABREV.index(sig_abrev)] if sig_abrev in SIGNOS_ABREV else sig_abrev
            grau_sig  = grau_abs % 30.0
            casa      = dados.casas.get(nome_p)
            casa_txt  = f" C{casa}" if casa else ""

            glifo = PLANETA_GLIFO.get(nome_p, "")
            cor_p = COR_PLANETA.get(nome_p, TEXTO_ESCURO)
            cor_e = ELEMENTO_COR.get(sig_abrev, TEXTO_CINZA)
            nome_curto = PLANETA_NOME_PT.get(nome_p, nome_p)[:9]

            txt(glifo,    0.06, y, color=cor_p, fs=9, bold=True)
            txt(nome_curto, 0.15, y, color=TEXTO_ESCURO, fs=7.5)
            txt(f"{grau_sig:.1f}° {sig_nome[:3]}{casa_txt}", 0.58, y, color=cor_e, fs=7.5)
            y -= dy

        # Separador
        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.025

        # Distribuição de elementos
        txt("ELEMENTOS", 0.06, y, color=OURO, fs=7.5, bold=True)
        y -= 0.028

        contagem: dict[str, int] = {"Fogo": 0, "Terra": 0, "Ar": 0, "Água": 0}
        COR_ELEM = {"Fogo": COR_FOGO, "Terra": COR_TERRA, "Ar": COR_AR, "Água": COR_AGUA}
        for p in ORDEM_PLANETAS[:10]:  # só os 10 planetas principais
            sg = dados.signos.get(p, "")
            el = ELEM_MAPA.get(sg)
            if el:
                contagem[el] += 1

        total = sum(contagem.values()) or 1
        for el, qtd in contagem.items():
            cor_el = COR_ELEM[el]
            barra  = 0.65 * (qtd / total)
            axp.add_patch(patches.Rectangle(
                (0.24, y - 0.010), barra, 0.013,
                color=cor_el, alpha=0.35,
            ))
            txt(f"{el[:4]}:", 0.06, y, color=cor_el, fs=7.5)
            txt(str(qtd), 0.94, y, color=cor_el, fs=7.5)
            y -= 0.026

        # Separador
        axp.axhline(y=y, xmin=0.04, xmax=0.96, color=BORDA, lw=0.8)
        y -= 0.025

        # Aspectos principais
        if dados.aspectos and y > 0.05:
            txt("ASPECTOS", 0.06, y, color=OURO, fs=7.5, bold=True)
            y -= 0.028
            for asp in dados.aspectos[:10]:
                if y < 0.04:
                    break
                p1   = PLANETA_GLIFO.get(asp["p1"], asp["p1"][:2])
                p2   = PLANETA_GLIFO.get(asp["p2"], asp["p2"][:2])
                tipo = asp["tipo"]
                sig  = SIGLA_ASPECTO.get(tipo, tipo[:2])
                cor_a = COR_ASPECTO.get(tipo, TEXTO_CINZA)
                orbe  = asp.get("orbe", 0)
                txt(f"{p1} {sig} {p2}   {orbe:.1f}°", 0.06, y, color=cor_a, fs=7.5)
                y -= 0.026

        # Rodapé
        axp.text(0.50, 0.015,
                 "Alquimista Interior · Swiss Ephemeris",
                 ha="center", va="bottom", fontsize=6,
                 color=TEXTO_CINZA, alpha=0.6)

        # ── Título global ────────────────────────────────────────────────────
        fig.text(0.33, 0.98,
                 f"Mapa Natal — {dados.nome_paciente}",
                 ha="center", va="top", fontsize=14,
                 color=OURO, fontweight="bold")

        # ── Exportar ─────────────────────────────────────────────────────────
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110,
                    facecolor=BG, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        png_bytes = buf.read()
        logger.info(f"Imagem do mapa natal gerada: {len(png_bytes) // 1024} KB")
        return png_bytes

    except Exception as e:
        logger.error(f"Falha ao gerar imagem do mapa natal: {e}", exc_info=True)
        raise RuntimeError(f"Falha na geração da imagem: {e}") from e


# ---------------------------------------------------------------------------
# Ajuste de sobreposição de planetas
# ---------------------------------------------------------------------------

def _ajustar_posicoes(
    posicoes: dict[str, float],
    asc: float,
    limiar_graus: float = 6.0,
) -> dict[str, float]:
    if not posicoes:
        return {}

    ordem = sorted(posicoes.keys(), key=lambda k: posicoes[k])
    ajustadas = dict(posicoes)

    for _ in range(6):
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
