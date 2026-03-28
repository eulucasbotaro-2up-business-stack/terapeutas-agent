"""
Gerador de imagens de mapa natal alquímico.

Gera uma imagem PNG do mapa natal para envio via WhatsApp.
Design: tema escuro moderno, muito mais bonito que o Vega Plus.
Usa matplotlib com tema polar escuro + Pillow para composição final.
"""

import io
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de design
# ---------------------------------------------------------------------------

COR_FUNDO = "#0d1117"          # fundo principal — preto azulado profundo
COR_FUNDO_PAINEL = "#161b22"   # painel lateral
COR_GRADE = "#21262d"          # linhas de grade / divisores
COR_BORDA = "#30363d"          # bordas sutis

COR_TEXTO_PRIMARIO = "#e6edf3"
COR_TEXTO_SECUNDARIO = "#8b949e"
COR_OURO = "#d4a853"           # destaque dourado
COR_OURO_CLARO = "#f0c060"

# Cores por elemento
COR_FOGO = "#e05252"    # Áries, Leão, Sagitário
COR_TERRA = "#52b052"   # Touro, Virgem, Capricórnio
COR_AR = "#d4c44a"      # Gêmeos, Libra, Aquário
COR_AGUA = "#4a8fd4"    # Câncer, Escorpião, Peixes

# Mapeamento signo → elemento → cor
ELEMENTO_COR: dict[str, str] = {
    "Ari": COR_FOGO, "Leo": COR_FOGO, "Sag": COR_FOGO,
    "Tau": COR_TERRA, "Vir": COR_TERRA, "Cap": COR_TERRA,
    "Gem": COR_AR, "Lib": COR_AR, "Aqu": COR_AR,
    "Can": COR_AGUA, "Sco": COR_AGUA, "Pis": COR_AGUA,
}

# Símbolos unicode dos signos do zodíaco (ordem: Áries=0° ... Peixes=330°)
SIGNOS_UNICODE = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
SIGNOS_ABREV = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
SIGNOS_NOME_PT = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]

# Cores por tipo de aspecto
COR_ASPECTO: dict[str, str] = {
    "conjunction":  "#d4a853",   # dourado
    "trine":        "#4a8fd4",   # azul — harmonioso
    "sextile":      "#52b0a0",   # verde-água — harmonioso leve
    "square":       "#e05252",   # vermelho — tenso
    "opposition":   "#c060d0",   # roxo — tenso forte
}

# Símbolo unicode dos planetas
PLANETA_GLIFO: dict[str, str] = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
    "Ascendant": "Asc",
    "Medium_Coeli": "MC",
}

PLANETA_NOME_PT: dict[str, str] = {
    "Sun": "Sol",
    "Moon": "Lua",
    "Mercury": "Mercúrio",
    "Venus": "Vênus",
    "Mars": "Marte",
    "Jupiter": "Júpiter",
    "Saturn": "Saturno",
    "Uranus": "Urano",
    "Neptune": "Netuno",
    "Pluto": "Plutão",
    "Ascendant": "Ascendente",
    "Medium_Coeli": "Meio do Céu",
}

COR_PLANETA: dict[str, str] = {
    "Sun": "#f0c060",
    "Moon": "#c0d4f0",
    "Mercury": "#a0c080",
    "Venus": "#e88080",
    "Mars": "#e05252",
    "Jupiter": "#d4a853",
    "Saturn": "#8b9e60",
    "Uranus": "#60b8d4",
    "Neptune": "#7060d4",
    "Pluto": "#c06090",
    "Ascendant": "#e6edf3",
    "Medium_Coeli": "#e6edf3",
}

# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------


class DadosMapa:
    """
    Contém todas as posições e aspectos do mapa natal em formato limpo.
    Pode ser criado a partir de um AstrologicalSubject ou de dados básicos.
    """

    def __init__(
        self,
        nome_paciente: str,
        data_nascimento: str,
        hora_nascimento: str,
        cidade_nascimento: str,
        planetas: dict[str, float],    # {"Sun": 45.5, "Moon": 132.0, ...} — graus eclípticos (0–360)
        signos: dict[str, str],        # {"Sun": "Tau", "Moon": "Can", ...}
        casas: dict[str, Optional[int]],  # {"Sun": 2, ...}
        aspectos: list[dict[str, Any]],   # [{"p1": "Sun", "p2": "Moon", "tipo": "trine", "orbe": 1.5}]
        ascendente_grau: float = 0.0,
    ) -> None:
        self.nome_paciente = nome_paciente
        self.data_nascimento = data_nascimento
        self.hora_nascimento = hora_nascimento
        self.cidade_nascimento = cidade_nascimento
        self.planetas = planetas
        self.signos = signos
        self.casas = casas
        self.aspectos = aspectos
        self.ascendente_grau = ascendente_grau


def dados_mapa_de_sujeito(
    sujeito: Any,
    nome_paciente: str,
    data_nascimento: str,
    hora_nascimento: str,
    cidade_nascimento: str,
) -> "DadosMapa":
    """
    Converte um AstrologicalSubject do Kerykeion em DadosMapa.

    Args:
        sujeito: AstrologicalSubject do Kerykeion
        nome_paciente: Nome do paciente
        data_nascimento: Data no formato DD/MM/AAAA
        hora_nascimento: Hora no formato HH:MM
        cidade_nascimento: Cidade de nascimento

    Returns:
        DadosMapa com todos os dados extraídos
    """
    # Mapeamento de atributos do Kerykeion → nome interno
    atributos_planetas = [
        ("sun", "Sun"), ("moon", "Moon"), ("mercury", "Mercury"),
        ("venus", "Venus"), ("mars", "Mars"), ("jupiter", "Jupiter"),
        ("saturn", "Saturn"), ("uranus", "Uranus"), ("neptune", "Neptune"),
        ("pluto", "Pluto"), ("ascendant", "Ascendant"), ("medium_coeli", "Medium_Coeli"),
    ]

    # Kerykeion v5: house é str "First_House" ... "Twelfth_House", não int
    _HOUSE_STR_TO_INT = {
        "First_House": 1, "Second_House": 2, "Third_House": 3,
        "Fourth_House": 4, "Fifth_House": 5, "Sixth_House": 6,
        "Seventh_House": 7, "Eighth_House": 8, "Ninth_House": 9,
        "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
    }

    planetas: dict[str, float] = {}
    signos: dict[str, str] = {}
    casas: dict[str, Optional[int]] = {}

    for attr, nome in atributos_planetas:
        ponto = getattr(sujeito, attr, None)
        if ponto is not None:
            # Grau absoluto na eclíptica (0–360)
            sign_idx = SIGNOS_ABREV.index(ponto.sign) if ponto.sign in SIGNOS_ABREV else 0
            grau_abs = sign_idx * 30.0 + float(ponto.position)
            planetas[nome] = grau_abs % 360.0
            signos[nome] = ponto.sign
            casa_raw = getattr(ponto, "house", None)
            # Normalizar: v5 retorna str, v4 retornava int
            if isinstance(casa_raw, str):
                casas[nome] = _HOUSE_STR_TO_INT.get(casa_raw)
            elif isinstance(casa_raw, int):
                casas[nome] = casa_raw
            else:
                casas[nome] = None

    asc_grau = planetas.get("Ascendant", 0.0)

    # Extrair aspectos se disponível
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
                    "p1": asp.p1_name,
                    "p2": asp.p2_name,
                    "tipo": asp.aspect,
                    "orbe": float(asp.orbit),
                })
    except Exception as e:
        logger.warning(f"Não foi possível extrair aspectos para o gráfico: {e}")

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
# Funções de geometria
# ---------------------------------------------------------------------------

def _grau_para_angulo_rad(grau_ecl: float, asc_grau: float) -> float:
    """
    Converte graus eclípticos em ângulo polar para o gráfico.

    Na roda natal, o Ascendente fica à esquerda (ângulo π = 180°).
    Crescimento anti-horário = sentido astrológico.

    Returns:
        Ângulo em radianos para uso em matplotlib (0=direita, cresce anti-horário).
    """
    # Posição relativa ao Ascendente
    delta = (grau_ecl - asc_grau) % 360.0
    # Na roda natal, 0° relativo = ponta esquerda (π), crescendo no sentido anti-horário
    angulo_graus = 180.0 - delta  # anti-horário a partir da esquerda
    return math.radians(angulo_graus)


def _pol_to_xy(raio: float, angulo_rad: float) -> tuple[float, float]:
    """Converte polar → cartesiano."""
    return raio * math.cos(angulo_rad), raio * math.sin(angulo_rad)


# ---------------------------------------------------------------------------
# Renderização principal
# ---------------------------------------------------------------------------

def gerar_imagem_mapa_natal(
    dados: "DadosMapa",
) -> bytes:
    """
    Gera PNG do mapa natal com tema escuro moderno.

    Args:
        dados: DadosMapa com posições e aspectos calculados

    Returns:
        bytes: PNG image data pronto para envio via WhatsApp

    Raises:
        RuntimeError: Se a geração da imagem falhar
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # sem GUI — para uso em servidor
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.patches import Arc, FancyArrowPatch
        import numpy as np

        # --- Configuração da figura ---
        fig = plt.figure(figsize=(14, 10), facecolor=COR_FUNDO, dpi=100)

        # Layout: coluna esquerda = roda natal, coluna direita = painel de dados
        # Proporção 65% / 35%
        ax_roda = fig.add_axes([0.01, 0.05, 0.60, 0.90])   # roda principal
        ax_painel = fig.add_axes([0.63, 0.05, 0.36, 0.90])  # painel de dados

        # ----------------------------------------------------------------
        # RODA NATAL
        # ----------------------------------------------------------------
        ax_roda.set_aspect("equal")
        ax_roda.set_facecolor(COR_FUNDO)
        ax_roda.set_xlim(-1.35, 1.35)
        ax_roda.set_ylim(-1.35, 1.35)
        ax_roda.axis("off")

        asc = dados.ascendente_grau

        # Raios dos anéis
        R_EXTERNO = 1.20       # borda externa do anel zodiacal
        R_ZODIAC_INT = 0.92    # borda interna do anel zodiacal
        R_CASAS_EXT = 0.88     # borda externa do anel das casas
        R_CASAS_INT = 0.65     # borda interna do anel das casas (círculo das casas)
        R_PLANETA_ANEL = 0.78  # onde ficam os planetas
        R_ASPECTOS = 0.60      # raio interno para linhas de aspectos

        # --- Anel zodiacal externo ---
        anel_zodiac = plt.Circle((0, 0), R_EXTERNO, color=COR_GRADE, fill=True, zorder=1)
        anel_zodiac_int = plt.Circle((0, 0), R_ZODIAC_INT, color=COR_FUNDO, fill=True, zorder=2)
        ax_roda.add_patch(anel_zodiac)
        ax_roda.add_patch(anel_zodiac_int)

        # Divisões e cores dos 12 signos
        for i, abrev in enumerate(SIGNOS_ABREV):
            angulo_inicio = _grau_para_angulo_rad(i * 30.0, asc)
            angulo_fim = _grau_para_angulo_rad((i + 1) * 30.0, asc)

            # Fatia colorida do anel zodiacal
            cor_signo = ELEMENTO_COR.get(abrev, "#444444")
            theta1_deg = math.degrees(angulo_inicio)
            theta2_deg = math.degrees(angulo_fim)

            # Arco colorido (fundo do segmento)
            theta_arr = np.linspace(angulo_inicio, angulo_fim, 40)
            xs_ext = [R_EXTERNO * math.cos(t) for t in theta_arr]
            ys_ext = [R_EXTERNO * math.sin(t) for t in theta_arr]
            xs_int = [R_ZODIAC_INT * math.cos(t) for t in reversed(theta_arr)]
            ys_int = [R_ZODIAC_INT * math.sin(t) for t in reversed(theta_arr)]
            ax_roda.fill(xs_ext + xs_int, ys_ext + ys_int,
                         color=cor_signo, alpha=0.18, zorder=3)

            # Linha divisória do signo
            x0, y0 = _pol_to_xy(R_ZODIAC_INT, angulo_inicio)
            x1, y1 = _pol_to_xy(R_EXTERNO, angulo_inicio)
            ax_roda.plot([x0, x1], [y0, y1], color=COR_GRADE, lw=0.8, zorder=4)

            # Símbolo unicode do signo (centro do segmento)
            ang_meio = (angulo_inicio + angulo_fim) / 2
            r_simbolo = (R_ZODIAC_INT + R_EXTERNO) / 2
            sx, sy = _pol_to_xy(r_simbolo, ang_meio)
            ax_roda.text(sx, sy, SIGNOS_UNICODE[i],
                         ha="center", va="center", fontsize=11,
                         color=cor_signo, alpha=0.95, zorder=5,
                         fontfamily="DejaVu Sans")

        # --- Círculo das casas ---
        circulo_casas = plt.Circle((0, 0), R_CASAS_INT, color=COR_GRADE, fill=False,
                                   lw=0.8, zorder=6)
        ax_roda.add_patch(circulo_casas)

        # Linhas das casas (12 casas iguais por simplicidade — roda Whole Sign visual)
        for i in range(12):
            ang = _grau_para_angulo_rad(i * 30.0, asc)
            x0, y0 = _pol_to_xy(R_CASAS_INT, ang)
            x1, y1 = _pol_to_xy(R_ZODIAC_INT, ang)
            lw = 1.2 if i in (0, 3, 6, 9) else 0.5
            cor = COR_OURO if i in (0, 3, 6, 9) else COR_BORDA
            ax_roda.plot([x0, x1], [y0, y1], color=cor, lw=lw, zorder=7)

            # Número da casa (pequeno, dentro do anel das casas)
            ang_meio = _grau_para_angulo_rad((i + 0.5) * 30.0, asc)
            r_num = (R_CASAS_INT + R_CASAS_EXT) / 2
            nx, ny = _pol_to_xy(r_num, ang_meio)
            ax_roda.text(nx, ny, str(i + 1),
                         ha="center", va="center", fontsize=6.5,
                         color=COR_TEXTO_SECUNDARIO, alpha=0.7, zorder=8)

        # --- Linhas de aspectos ---
        ordem_planetas = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                          "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
                          "Ascendant", "Medium_Coeli"]
        for asp in dados.aspectos:
            p1_nome = asp["p1"]
            p2_nome = asp["p2"]
            tipo = asp["tipo"]
            if p1_nome not in dados.planetas or p2_nome not in dados.planetas:
                continue
            cor_asp = COR_ASPECTO.get(tipo, "#555555")
            alpha_asp = 0.55 if tipo in ("trine", "sextile") else 0.70

            ang1 = _grau_para_angulo_rad(dados.planetas[p1_nome], asc)
            ang2 = _grau_para_angulo_rad(dados.planetas[p2_nome], asc)
            x1, y1 = _pol_to_xy(R_ASPECTOS, ang1)
            x2, y2 = _pol_to_xy(R_ASPECTOS, ang2)

            lw_asp = 1.0 if tipo in ("trine", "sextile") else 1.4
            ax_roda.plot([x1, x2], [y1, y2], color=cor_asp,
                         lw=lw_asp, alpha=alpha_asp, zorder=9)

        # --- Ponto central ---
        circulo_centro = plt.Circle((0, 0), R_ASPECTOS - 0.02, color=COR_FUNDO,
                                    fill=True, zorder=10)
        ax_roda.add_patch(circulo_centro)
        circulo_centro_borda = plt.Circle((0, 0), R_ASPECTOS - 0.02, color=COR_GRADE,
                                          fill=False, lw=0.6, zorder=11)
        ax_roda.add_patch(circulo_centro_borda)

        # Anel interno dourado pequeno
        circulo_ouro = plt.Circle((0, 0), 0.08, color=COR_OURO, fill=True,
                                  alpha=0.30, zorder=12)
        ax_roda.add_patch(circulo_ouro)

        # --- Planetas na roda ---
        # Detectar sobreposições e ajustar posições
        posicoes_ajustadas: dict[str, float] = _ajustar_posicoes(
            {k: v for k, v in dados.planetas.items() if k in ordem_planetas}, asc
        )

        for nome_planeta, grau in posicoes_ajustadas.items():
            if nome_planeta not in dados.planetas:
                continue
            grau_original = dados.planetas[nome_planeta]
            ang_orig = _grau_para_angulo_rad(grau_original, asc)
            ang_ajust = _grau_para_angulo_rad(grau, asc)

            # Pequena linha do ponto original até o glifo
            x_orig, y_orig = _pol_to_xy(R_PLANETA_ANEL - 0.06, ang_orig)
            x_glifo, y_glifo = _pol_to_xy(R_PLANETA_ANEL + 0.04, ang_ajust)

            # Ponto marcador na posição original
            ax_roda.plot(x_orig, y_orig, "o",
                         color=COR_PLANETA.get(nome_planeta, "#ffffff"),
                         markersize=3, zorder=13)

            # Linha de conexão (só se houver ajuste significativo)
            delta_ang = abs(ang_orig - ang_ajust)
            if delta_ang > 0.05:
                ax_roda.plot([x_orig, x_glifo], [y_orig, y_glifo],
                             color=COR_PLANETA.get(nome_planeta, "#ffffff"),
                             lw=0.4, alpha=0.5, zorder=13)

            # Glifo do planeta
            glifo = PLANETA_GLIFO.get(nome_planeta, "?")
            fontsize_glifo = 7 if nome_planeta in ("Ascendant", "Medium_Coeli") else 9
            ax_roda.text(x_glifo, y_glifo, glifo,
                         ha="center", va="center",
                         fontsize=fontsize_glifo,
                         color=COR_PLANETA.get(nome_planeta, "#ffffff"),
                         fontweight="bold", zorder=14,
                         fontfamily="DejaVu Sans")

        # --- Título da roda ---
        ax_roda.text(0, -1.32, "MAPA NATAL ALQUÍMICO",
                     ha="center", va="center", fontsize=8,
                     color=COR_OURO, alpha=0.70, zorder=15,
                     fontfamily="DejaVu Sans")

        # ----------------------------------------------------------------
        # PAINEL DE DADOS (direita)
        # ----------------------------------------------------------------
        ax_painel.set_facecolor(COR_FUNDO_PAINEL)
        ax_painel.axis("off")
        ax_painel.set_xlim(0, 1)
        ax_painel.set_ylim(0, 1)

        # Borda do painel
        rect_painel = patches.FancyBboxPatch(
            (0.02, 0.01), 0.96, 0.97,
            boxstyle="round,pad=0.01",
            linewidth=1.0, edgecolor=COR_BORDA,
            facecolor=COR_FUNDO_PAINEL, zorder=1
        )
        ax_painel.add_patch(rect_painel)

        y = 0.97  # posição vertical inicial (de cima para baixo)
        dy_titulo = 0.04
        dy_linha = 0.033

        def painel_texto(texto: str, x: float, y_pos: float,
                         color: str = COR_TEXTO_PRIMARIO,
                         fontsize: float = 8.5,
                         bold: bool = False,
                         alpha: float = 1.0) -> None:
            ax_painel.text(x, y_pos, texto,
                           ha="left", va="top",
                           fontsize=fontsize, color=color,
                           fontweight="bold" if bold else "normal",
                           alpha=alpha, zorder=2,
                           fontfamily="DejaVu Sans")

        # Nome e dados principais
        nome_display = dados.nome_paciente[:22] if len(dados.nome_paciente) > 22 else dados.nome_paciente
        painel_texto(nome_display.upper(), 0.06, y - 0.01,
                     color=COR_OURO, fontsize=11, bold=True)
        y -= dy_titulo

        painel_texto(f"{dados.data_nascimento}  {dados.hora_nascimento}", 0.06, y,
                     color=COR_TEXTO_SECUNDARIO, fontsize=8)
        y -= dy_linha * 0.85

        cidade_display = dados.cidade_nascimento[:28] if len(dados.cidade_nascimento) > 28 else dados.cidade_nascimento
        painel_texto(cidade_display, 0.06, y, color=COR_TEXTO_SECUNDARIO, fontsize=7.5)
        y -= dy_linha * 1.2

        # Linha separadora
        ax_painel.axhline(y=y, xmin=0.04, xmax=0.96, color=COR_BORDA, lw=0.8, alpha=0.7)
        y -= dy_linha * 0.6

        # Cabeçalho posições planetárias
        painel_texto("POSIÇÕES PLANETÁRIAS", 0.06, y,
                     color=COR_OURO, fontsize=7.5, bold=True, alpha=0.85)
        y -= dy_linha

        # Lista de planetas
        ordem_painel = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
            "Ascendant", "Medium_Coeli",
        ]
        SIGNOS_NOMES = {
            "Ari": "Áries", "Tau": "Touro", "Gem": "Gêmeos", "Can": "Câncer",
            "Leo": "Leão", "Vir": "Virgem", "Lib": "Libra", "Sco": "Escorpião",
            "Sag": "Sagitário", "Cap": "Capricórnio", "Aqu": "Aquário", "Pis": "Peixes",
        }

        for nome_p in ordem_painel:
            if nome_p not in dados.planetas:
                continue
            grau_abs = dados.planetas[nome_p]
            signo_abrev = dados.signos.get(nome_p, "")
            signo_nome = SIGNOS_NOMES.get(signo_abrev, signo_abrev)
            grau_no_signo = grau_abs % 30.0
            casa = dados.casas.get(nome_p)
            casa_txt = f" C{casa}" if casa else ""

            glifo = PLANETA_GLIFO.get(nome_p, "")
            cor_p = COR_PLANETA.get(nome_p, COR_TEXTO_PRIMARIO)
            cor_elem = ELEMENTO_COR.get(signo_abrev, COR_TEXTO_SECUNDARIO)

            # Glifo
            painel_texto(glifo, 0.06, y, color=cor_p, fontsize=8.5, bold=True)
            # Nome planeta
            nome_curto = PLANETA_NOME_PT.get(nome_p, nome_p)[:8]
            painel_texto(f" {nome_curto}", 0.14, y, color=COR_TEXTO_PRIMARIO, fontsize=7.5)
            # Posição
            painel_texto(f"{grau_no_signo:.1f}° {signo_nome[:3]}{casa_txt}",
                         0.56, y, color=cor_elem, fontsize=7.5)
            y -= dy_linha

        y -= dy_linha * 0.2
        ax_painel.axhline(y=y, xmin=0.04, xmax=0.96, color=COR_BORDA, lw=0.8, alpha=0.7)
        y -= dy_linha * 0.6

        # --- Distribuição dos elementos ---
        painel_texto("ELEMENTOS", 0.06, y, color=COR_OURO, fontsize=7.5, bold=True, alpha=0.85)
        y -= dy_linha

        contagem_elem: dict[str, int] = {"Fogo": 0, "Terra": 0, "Ar": 0, "Água": 0}
        ELEM_MAPA = {
            "Ari": "Fogo", "Leo": "Fogo", "Sag": "Fogo",
            "Tau": "Terra", "Vir": "Terra", "Cap": "Terra",
            "Gem": "Ar", "Lib": "Ar", "Aqu": "Ar",
            "Can": "Água", "Sco": "Água", "Pis": "Água",
        }
        PLANETAS_PARA_ELEM = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                              "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        for p in PLANETAS_PARA_ELEM:
            sg = dados.signos.get(p, "")
            elem = ELEM_MAPA.get(sg)
            if elem:
                contagem_elem[elem] += 1

        COR_ELEM_DISPLAY = {
            "Fogo": COR_FOGO, "Terra": COR_TERRA,
            "Ar": COR_AR, "Água": COR_AGUA,
        }
        total_planetas = sum(contagem_elem.values()) or 1
        for elem_nome, qtd in contagem_elem.items():
            cor_e = COR_ELEM_DISPLAY[elem_nome]
            barra_w = 0.70 * (qtd / total_planetas)
            rect_e = patches.Rectangle((0.22, y - 0.012), barra_w, 0.014,
                                       color=cor_e, alpha=0.55, zorder=3)
            ax_painel.add_patch(rect_e)
            painel_texto(f"{elem_nome[:4]}:", 0.06, y, color=cor_e, fontsize=7.5)
            painel_texto(str(qtd), 0.95, y, color=cor_e, fontsize=7.5)
            y -= dy_linha * 0.85

        # --- Aspectos principais ---
        y -= dy_linha * 0.4
        ax_painel.axhline(y=y, xmin=0.04, xmax=0.96, color=COR_BORDA, lw=0.8, alpha=0.7)
        y -= dy_linha * 0.6

        if dados.aspectos and y > 0.08:
            painel_texto("ASPECTOS", 0.06, y, color=COR_OURO, fontsize=7.5, bold=True, alpha=0.85)
            y -= dy_linha

            TIPO_SIGLA = {
                "conjunction": "☌",
                "opposition": "☍",
                "square": "□",
                "trine": "△",
                "sextile": "60°",  # ⚹ não está em DejaVu Sans
            }
            for asp in dados.aspectos[:8]:  # máx 8 aspectos no painel
                if y < 0.06:
                    break
                p1 = PLANETA_GLIFO.get(asp["p1"], asp["p1"][:3])
                p2 = PLANETA_GLIFO.get(asp["p2"], asp["p2"][:3])
                tipo = asp["tipo"]
                sigla = TIPO_SIGLA.get(tipo, tipo[:3])
                cor_asp = COR_ASPECTO.get(tipo, COR_TEXTO_SECUNDARIO)
                orbe = asp.get("orbe", 0)
                painel_texto(f"{p1} {sigla} {p2}  {orbe:.1f}°",
                             0.06, y, color=cor_asp, fontsize=7.5)
                y -= dy_linha * 0.90

        # --- Rodapé ---
        ax_painel.text(0.50, 0.025,
                       "Calculado via Swiss Ephemeris  ·  Alquimista Interior",
                       ha="center", va="bottom", fontsize=6.0,
                       color=COR_TEXTO_SECUNDARIO, alpha=0.55, zorder=2,
                       fontfamily="DejaVu Sans")

        # ----------------------------------------------------------------
        # Título global acima do chart
        # ----------------------------------------------------------------
        fig.text(0.32, 0.98,
                 f"Mapa Natal — {dados.nome_paciente}",
                 ha="center", va="top", fontsize=14,
                 color=COR_OURO_CLARO, fontweight="bold",
                 fontfamily="DejaVu Sans")

        # ----------------------------------------------------------------
        # Exportar PNG para bytes
        # ----------------------------------------------------------------
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100,
                    facecolor=COR_FUNDO, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        png_bytes = buf.read()
        logger.info(f"Imagem do mapa natal gerada: {len(png_bytes) // 1024} KB")
        return png_bytes

    except Exception as e:
        logger.error(f"Falha ao gerar imagem do mapa natal: {e}", exc_info=True)
        raise RuntimeError(f"Falha na geração da imagem do mapa natal: {e}") from e


def _ajustar_posicoes(
    posicoes: dict[str, float],
    asc: float,
    limiar_graus: float = 6.0,
) -> dict[str, float]:
    """
    Afasta planetas próximos no anel para evitar sobreposição de glifos.

    Args:
        posicoes: {nome_planeta: grau_ecliptico}
        asc: grau do Ascendente
        limiar_graus: distância mínima entre planetas (em graus)

    Returns:
        Novo dict com posições ajustadas (apenas o ângulo do glifo, não o ponto original)
    """
    if not posicoes:
        return {}

    ordem = list(posicoes.keys())
    ajustadas = {k: v for k, v in posicoes.items()}

    # Ordenar por grau eclíptico
    ordem.sort(key=lambda k: posicoes[k])

    # Iteração simples: se dois planetas estão muito próximos, afastar
    for _ in range(5):  # max 5 passes
        modificado = False
        for i in range(len(ordem)):
            for j in range(i + 1, len(ordem)):
                p1, p2 = ordem[i], ordem[j]
                d = (ajustadas[p2] - ajustadas[p1]) % 360.0
                if d < limiar_graus:
                    # Afastar em direções opostas
                    delta = (limiar_graus - d) / 2.0 + 0.5
                    ajustadas[p1] = (ajustadas[p1] - delta) % 360.0
                    ajustadas[p2] = (ajustadas[p2] + delta) % 360.0
                    modificado = True
        if not modificado:
            break

    return ajustadas
