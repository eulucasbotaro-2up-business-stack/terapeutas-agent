"""
Módulo de cálculo astrológico via Swiss Ephemeris (Kerykeion v5).

Fornece cálculo preciso do mapa natal para injetar no prompt do agente,
eliminando alucinações sobre Ascendente e posições planetárias.
"""

import logging
import re
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache de coordenadas — cidades brasileiras mais comuns.
# Evita chamada ao Nominatim (que pode pendurar indefinidamente).
# Fonte: coordenadas geográficas oficiais das capitais e grandes cidades.
# ---------------------------------------------------------------------------
_COORDS_BR: dict[str, tuple[float, float, str]] = {
    # (lat, lon, timezone)
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
    "são bernardo do campo": (-23.6939, -46.5650, "America/Sao_Paulo"),
    "santo andre":        (-23.6639, -46.5383, "America/Sao_Paulo"),
    "santos":             (-23.9608, -46.3336, "America/Sao_Paulo"),
    "são josé dos campos": (-23.1794, -45.8869, "America/Sao_Paulo"),
    "ribeirao preto":     (-21.1775, -47.8103, "America/Sao_Paulo"),
    "ribeirão preto":     (-21.1775, -47.8103, "America/Sao_Paulo"),
    "uberlandia":         (-18.9186, -48.2772, "America/Sao_Paulo"),
    "uberlândia":         (-18.9186, -48.2772, "America/Sao_Paulo"),
    "contagem":           (-19.9317, -44.0536, "America/Sao_Paulo"),
    "londrina":           (-23.3045, -51.1696, "America/Sao_Paulo"),
    "joinville":          (-26.3044, -48.8487, "America/Sao_Paulo"),
    "são gonçalo":        (-22.8268, -43.0546, "America/Sao_Paulo"),
    "duque de caxias":    (-22.7856, -43.3117, "America/Sao_Paulo"),
    "nova iguaçu":        (-22.7592, -43.4511, "America/Sao_Paulo"),
    "brasília":           (-15.7797, -47.9297, "America/Sao_Paulo"),
    "brasilia":           (-15.7797, -47.9297, "America/Sao_Paulo"),
    "df":                 (-15.7797, -47.9297, "America/Sao_Paulo"),
    "distrito federal":   (-15.7797, -47.9297, "America/Sao_Paulo"),
}


def _limpar_cidade(cidade: str) -> str:
    """Remove sufixos desnecessários e normaliza o nome da cidade."""
    cidade = cidade.lower().strip()
    # Remove sufixos como "capital", "sp", "mg", "rj" após vírgula ou espaço
    cidade = re.sub(r"\s*,\s*brasil\s*$", "", cidade)
    cidade = re.sub(r"\s*,\s*[a-z]{2}\s*$", "", cidade)    # ", SP"
    cidade = re.sub(r"\s+capital\s*$", "", cidade)          # "São Paulo capital"
    cidade = re.sub(r"\s*-\s*[a-z]{2}\s*$", "", cidade)    # "São Paulo - SP"
    cidade = re.sub(r"\s+[a-z]{2}\s*$", "", cidade)         # "São Paulo SP"
    return cidade.strip()


def _geocodificar_cidade(cidade_nascimento: str) -> tuple[float, float, str]:
    """
    Retorna (lat, lon, timezone) para a cidade informada.
    Tenta cache local primeiro; só chama Nominatim se necessário.
    """
    chave = _limpar_cidade(cidade_nascimento)
    if chave in _COORDS_BR:
        lat, lon, tz = _COORDS_BR[chave]
        logger.info(f"Coordenadas do cache local para '{cidade_nascimento}': ({lat}, {lon}) tz={tz}")
        return lat, lon, tz

    # Fallback: Nominatim (pode ser lento em produção)
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    geolocator = Nominatim(user_agent="alquimista-interior-bot/1.0", timeout=10)
    tentativas = [
        cidade_nascimento,
        cidade_nascimento + ", Brasil",
    ]
    location = None
    for tentativa in tentativas:
        try:
            time.sleep(1)
            location = geolocator.geocode(tentativa, language="pt")
            if location:
                break
        except Exception as geo_err:
            logger.warning(f"Erro de geocodificação para '{tentativa}': {geo_err}")

    if not location:
        raise ValueError(
            f"Cidade não encontrada: '{cidade_nascimento}'. "
            "Tente incluir o estado e o país (ex: 'Belo Horizonte, MG, Brasil')."
        )

    lat = location.latitude
    lon = location.longitude
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon) or "America/Sao_Paulo"
    logger.info(f"Coordenadas do Nominatim para '{cidade_nascimento}': ({lat}, {lon}) tz={tz_str}")
    return lat, lon, tz_str

# Mapeamentos de tradução
SIGNOS_PT = {
    "Ari": "Áries",
    "Tau": "Touro",
    "Gem": "Gêmeos",
    "Can": "Câncer",
    "Leo": "Leão",
    "Vir": "Virgem",
    "Lib": "Libra",
    "Sco": "Escorpião",
    "Sag": "Sagitário",
    "Cap": "Capricórnio",
    "Aqu": "Aquário",
    "Pis": "Peixes",
}

ELEMENTOS = {
    "Ari": "Fogo", "Leo": "Fogo", "Sag": "Fogo",
    "Tau": "Terra", "Vir": "Terra", "Cap": "Terra",
    "Gem": "Ar",   "Lib": "Ar",   "Aqu": "Ar",
    "Can": "Água",  "Sco": "Água",  "Pis": "Água",
}

ASPECTOS_PT = {
    "conjunction": "Conjunção (0°)",
    "opposition": "Oposição (180°)",
    "square": "Quadratura (90°)",
    "trine": "Trígono (120°)",
    "sextile": "Sextil (60°)",
}

PLANETAS_PT = {
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
}


def _signo_pt(signo_abrev: str) -> str:
    """Converte abreviação do signo em nome português."""
    return SIGNOS_PT.get(signo_abrev, signo_abrev)


def calcular_mapa_natal(
    nome: str,
    data_nascimento: str,
    hora_nascimento: str,
    cidade_nascimento: str,
) -> str:
    """
    Calcula o mapa natal alquímico do paciente via Swiss Ephemeris (Kerykeion v5).

    Args:
        nome: Nome do paciente
        data_nascimento: Data no formato DD/MM/AAAA
        hora_nascimento: Hora no formato HH:MM
        cidade_nascimento: Cidade de nascimento (ex: "São Paulo, SP, Brasil")

    Returns:
        Texto formatado em português com dados do mapa para injetar no prompt

    Raises:
        ValueError: Se a cidade não for encontrada ou os dados forem inválidos
        ImportError: Se kerykeion não estiver instalado
    """
    try:
        from kerykeion import AstrologicalSubjectFactory
        from kerykeion.aspects.aspects_factory import AspectsFactory
    except ImportError as e:
        raise ImportError(
            "Kerykeion não está instalado. Execute: pip install kerykeion"
        ) from e

    # --- Parsing dos dados ---
    try:
        dia, mes, ano = [int(x) for x in data_nascimento.strip().split("/")]
    except ValueError as e:
        raise ValueError(
            f"Formato de data inválido: '{data_nascimento}'. Use DD/MM/AAAA."
        ) from e

    try:
        hora, minuto = [int(x) for x in hora_nascimento.strip().split(":")]
    except ValueError as e:
        raise ValueError(
            f"Formato de hora inválido: '{hora_nascimento}'. Use HH:MM."
        ) from e

    # --- Geocodificação (cache local primeiro, Nominatim como fallback) ---
    lat, lon, tz_str = _geocodificar_cidade(cidade_nascimento)

    # --- Cálculo astrológico (Kerykeion v5 — offline com coordenadas manuais) ---
    sujeito = AstrologicalSubjectFactory.from_birth_data(
        name=nome,
        year=ano,
        month=mes,
        day=dia,
        hour=hora,
        minute=minuto,
        lng=lon,
        lat=lat,
        tz_str=tz_str,
        online=False,
        zodiac_type="Tropical",
        houses_system_identifier="P",  # Placidus
        suppress_geonames_warning=True,
    )

    return _formatar_texto_mapa(
        sujeito=sujeito,
        nome=nome,
        dia=dia,
        mes=mes,
        ano=ano,
        hora=hora,
        minuto=minuto,
        cidade_nascimento=cidade_nascimento,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
    )


def _formatar_texto_mapa(
    sujeito: object,
    nome: str,
    dia: int,
    mes: int,
    ano: int,
    hora: int,
    minuto: int,
    cidade_nascimento: str,
    lat: float,
    lon: float,
    tz_str: str,
) -> str:
    """
    Converte um AstrologicalSubjectModel já calculado em texto formatado.

    Usado internamente por calcular_mapa_natal e gerar_mapa_completo para evitar
    geocodificação duplicada.
    """
    from kerykeion.aspects.aspects_factory import AspectsFactory

    # Kerykeion v5: house é str "First_House" ... "Twelfth_House", não int
    _HOUSE_STR_TO_INT = {
        "First_House": 1, "Second_House": 2, "Third_House": 3,
        "Fourth_House": 4, "Fifth_House": 5, "Sixth_House": 6,
        "Seventh_House": 7, "Eighth_House": 8, "Ninth_House": 9,
        "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
    }

    def fmt_ponto(ponto_model, nome_pt: str) -> str:
        if ponto_model is None:
            return f"  {nome_pt}: — (não calculado)"
        signo = _signo_pt(ponto_model.sign)
        grau = ponto_model.position
        casa_raw = getattr(ponto_model, "house", None)
        # v5 retorna str ("First_House"), v4 retornava int — normalizar para int
        if isinstance(casa_raw, str):
            casa_num = _HOUSE_STR_TO_INT.get(casa_raw)
        elif isinstance(casa_raw, int):
            casa_num = casa_raw
        else:
            casa_num = None
        casa_txt = f" | Casa {casa_num}" if casa_num else ""
        return f"  {nome_pt}: {signo} {grau:.1f}°{casa_txt}"

    linhas = []
    linhas.append(f"╔══ MAPA NATAL — {nome.upper()} ══╗")
    linhas.append(
        f"Data: {dia:02d}/{mes:02d}/{ano}  |  Hora: {hora:02d}:{minuto:02d}  |  Local: {cidade_nascimento}"
    )
    linhas.append(f"Coordenadas: {lat:.4f}N, {lon:.4f}E  |  Fuso: {tz_str}")
    linhas.append("")

    linhas.append("▸ LUMINARES E ÂNGULOS")
    linhas.append(fmt_ponto(sujeito.sun, "Sol ☉"))
    linhas.append(fmt_ponto(sujeito.moon, "Lua ☽"))
    linhas.append(fmt_ponto(sujeito.ascendant, "Ascendente ↑"))
    linhas.append(fmt_ponto(sujeito.medium_coeli, "Meio do Céu (MC)"))
    linhas.append("")

    linhas.append("▸ PLANETAS")
    planetas_ordem = [
        ("mercury", "Mercúrio ☿"),
        ("venus", "Vênus ♀"),
        ("mars", "Marte ♂"),
        ("jupiter", "Júpiter ♃"),
        ("saturn", "Saturno ♄"),
        ("uranus", "Urano ♅"),
        ("neptune", "Netuno ♆"),
        ("pluto", "Plutão ♇"),
    ]
    for attr, nome_pt in planetas_ordem:
        ponto = getattr(sujeito, attr, None)
        linhas.append(fmt_ponto(ponto, nome_pt))
    linhas.append("")

    linhas.append("▸ DISTRIBUIÇÃO DOS ELEMENTOS")
    contagem_elem: dict[str, int] = {"Fogo": 0, "Terra": 0, "Ar": 0, "Água": 0}
    pontos_para_elementos = [
        sujeito.sun, sujeito.moon, sujeito.mercury, sujeito.venus,
        sujeito.mars, sujeito.jupiter, sujeito.saturn,
        sujeito.uranus, sujeito.neptune, sujeito.pluto,
    ]
    for ponto in pontos_para_elementos:
        if ponto is not None:
            elem = ELEMENTOS.get(ponto.sign)
            if elem:
                contagem_elem[elem] += 1

    for elem, qtd in contagem_elem.items():
        barra = "█" * qtd
        linhas.append(f"  {elem}: {qtd} {barra}")
    linhas.append("")

    linhas.append("▸ ASPECTOS PRINCIPAIS")
    try:
        aspectos_model = AspectsFactory.single_chart_aspects(sujeito)
        aspectos_lista = aspectos_model.aspects
        planetas_pessoais = {
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Ascendant", "Medium_Coeli",
        }
        aspectos_major = {"conjunction", "opposition", "square", "trine", "sextile"}
        aspectos_filtrados = [
            a for a in aspectos_lista
            if a.aspect in aspectos_major
            and a.p1_name in planetas_pessoais
            and a.p2_name in planetas_pessoais
        ]
        if aspectos_filtrados:
            for asp in aspectos_filtrados:
                p1_pt = PLANETAS_PT.get(asp.p1_name, asp.p1_name)
                p2_pt = PLANETAS_PT.get(asp.p2_name, asp.p2_name)
                tipo = ASPECTOS_PT.get(asp.aspect, asp.aspect)
                orbe = asp.orbit
                linhas.append(f"  {p1_pt} — {p2_pt}: {tipo} (orbe {orbe:.1f}°)")
        else:
            linhas.append("  (Nenhum aspecto maior encontrado entre planetas pessoais)")
    except Exception as asp_err:
        logger.warning(f"Não foi possível calcular aspectos: {asp_err}")
        linhas.append("  (Cálculo de aspectos indisponível)")

    linhas.append("")
    linhas.append("╚══ FIM DO MAPA NATAL ══╝")
    return "\n".join(linhas)


def extrair_dados_nascimento(texto: str) -> Optional[dict]:
    """
    Extrai dados de nascimento de uma mensagem de texto em linguagem natural.

    Reconhece padrões como:
    - "nascida em 15/03/1985 às 14h30 em São Paulo"
    - "nasceu em 18/10/1979 14:00 Belo Horizonte"
    - "data: 01/05/1990, hora: 09:15, local: Curitiba, PR"
    - "paciente: Ana Silva | 22/07/1988 | 08:45 | Rio de Janeiro, RJ"

    Args:
        texto: Texto contendo os dados de nascimento

    Returns:
        Dict com chaves 'nome', 'data', 'hora', 'cidade' ou None se incompleto
    """
    if not texto:
        return None

    resultado: dict = {}

    # Mapeamento de nomes de meses em português para número
    _MESES_PT = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10,
        "novembro": 11, "dezembro": 12,
    }

    # --- Extração da data ---
    # Tenta formato numérico primeiro: DD/MM/AAAA, DD-MM-AAAA, DD.MM.AAAA
    data_match = re.search(
        r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b",
        texto,
    )
    if data_match:
        dia, mes, ano = data_match.groups()
        resultado["data"] = f"{int(dia):02d}/{int(mes):02d}/{ano}"
    else:
        # Tenta formato por extenso: "18 de novembro de 1985" ou "18 de novembro"
        # (ano é opcional — pode vir sem ano quando o usuário o omitiu)
        data_extenso = re.search(
            r"\b(\d{1,2})\s+de\s+("
            + "|".join(_MESES_PT.keys())
            + r")(?:\s+de\s+(\d{4}))?\b",
            texto,
            re.IGNORECASE,
        )
        if data_extenso:
            dia_str = data_extenso.group(1)
            mes_str = data_extenso.group(2).lower()
            ano_str = data_extenso.group(3)  # pode ser None
            mes_num = _MESES_PT.get(mes_str)
            if mes_num:
                if ano_str:
                    resultado["data"] = f"{int(dia_str):02d}/{mes_num:02d}/{ano_str}"
                else:
                    # Sem ano: guardar data parcial (dia/mês) e sinalizar que falta o ano
                    resultado["data_parcial"] = f"{int(dia_str):02d}/{mes_num:02d}"

    # --- Extração da hora ---
    # Formatos: 14:30, 14h30, 14h00, 14:30:00
    # Também: "14 horas" ou "14h" (sem minutos → assume :00)
    hora_match = re.search(
        r"\b(\d{1,2})h(\d{2})\b"        # 14h30
        r"|\b(\d{1,2}):(\d{2})(?::\d{2})?\b",  # 14:30 ou 14:30:00
        texto,
    )
    if hora_match:
        grupos = hora_match.groups()
        if grupos[0] is not None:
            # formato XhYY
            hora, minuto = grupos[0], grupos[1]
        else:
            # formato X:YY
            hora, minuto = grupos[2], grupos[3]
        resultado["hora"] = f"{int(hora):02d}:{int(minuto):02d}"
    else:
        # Tenta "14 horas" (sem minutos)
        hora_extenso = re.search(r"\b(\d{1,2})\s+hora(?:s)?\b", texto, re.IGNORECASE)
        if hora_extenso:
            resultado["hora"] = f"{int(hora_extenso.group(1)):02d}:00"

    # --- Extração do nome ---
    # Padrão 1: campo explícito "paciente: Nome", "nome: Nome", "nome do paciente: Nome"
    nome_match = re.search(
        r"(?:paciente|nome do paciente|nome)\s*[:\-]\s*([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s]{2,40}?)(?:\s*[\|\,\n]|$)",
        texto,
        re.IGNORECASE,
    )
    if nome_match:
        resultado["nome"] = nome_match.group(1).strip()
    else:
        # Padrão 2: nome livre antes da data — "Lucas Botaro 27/01/1995 ..."
        # Captura até 3 palavras capitalizadas imediatamente antes de DD/MM/AAAA
        nome_antes_data = re.search(
            r"([A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝ][a-zA-ZÀ-ÿ]+"
            r"(?:\s+[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝ][a-zA-ZÀ-ÿ]+){0,3})"
            r"\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}",
            texto,
        )
        if nome_antes_data:
            candidato = nome_antes_data.group(1).strip()
            # Rejeitar palavras reservadas que não são nomes
            _nao_nomes = {"faça", "faz", "fazer", "calcule", "calcular", "gere", "gerar",
                          "quero", "preciso", "pode", "mapa", "natal", "astral", "ué"}
            if candidato.lower() not in _nao_nomes:
                resultado["nome"] = candidato

    # --- Extração da cidade ---
    # Tentativa 1: campo explícito "local: Cidade"
    cidade_encontrada = None
    m = re.search(
        r"local\s*[:\-]\s*([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s\,\-]{3,60}?)(?:\s*[\|\n,]|$)",
        texto,
        re.IGNORECASE,
    )
    if m:
        cidade_encontrada = m.group(1).strip().rstrip(",")

    # Tentativa 2: "em <Cidade>" após hora — captura a última ocorrência de "em <texto>"
    # após uma data ou hora já identificada. Cobre:
    # "nascida em 15/03/1985 às 14h30 em São Paulo"
    # "Tony, nascido em 18/10/1979 às 14h00 em Belo Horizonte MG"
    if not cidade_encontrada:
        m = re.search(
            r"(?:\d{1,2}h\d{2}|\d{1,2}:\d{2}(?::\d{2})?)"  # após hora
            r"[\s\w,]*?\bem\s+"  # eventual "em" depois da hora (com/sem "às")
            r"([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s\,\-]{2,60}?)(?:\s*[\|\n]|$)",
            texto,
            re.IGNORECASE,
        )
        if m:
            cidade_encontrada = m.group(1).strip().rstrip(",")

    # Tentativa 3: hora seguida diretamente de cidade sem "em" —
    # ex: "nascimento: 22/07/1988 as 08h45 Fortaleza Ceara"
    #     "ele nasceu em 18/10/1979 14:00 em Belo Horizonte MG" (já coberta pela T2)
    # Cobre formatos XX:YY <Cidade> e XXhYY <Cidade>
    if not cidade_encontrada:
        m = re.search(
            r"(?:\d{1,2}h\d{2}|\d{1,2}:\d{2}(?::\d{2})?)\s+"
            r"([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s\,\-]{2,60}?)(?:\s*[\|\n]|$)",
            texto,
        )
        if m:
            candidata = m.group(1).strip().rstrip(",")
            # Rejeitar se começa com preposição solta (em, no, na, de, do, da)
            # que indicaria que não é a cidade em si
            if not re.match(r"^(?:em|no|na|de|do|da)\s", candidata, re.IGNORECASE):
                cidade_encontrada = candidata

    # Tentativa 4: "nascida/nascido/nasceu em <Cidade>" ou
    # "...nasceu... no/na <Cidade>" quando cidade vem logo após o verbo/preposição.
    # Remove a preposição capturada por engano (no, na, em).
    if not cidade_encontrada:
        m = re.search(
            r"nascid[oa]\s+em\s+(?!\d)([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s\,\-]{3,60}?)(?:\s*[\|\n,]|$)",
            texto,
            re.IGNORECASE,
        )
        if m:
            cidade_encontrada = m.group(1).strip().rstrip(",")

    # Tentativa 4b: "nasceu... no/na/em <Cidade>" — caso "no Rio de Janeiro" etc.
    if not cidade_encontrada:
        m = re.search(
            r"nasceu\b.*?\b(?:no|na|em)\s+(?!\d)([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s\,\-]{3,60}?)(?:\s*[\|\n,]|$)",
            texto,
            re.IGNORECASE,
        )
        if m:
            cidade_encontrada = m.group(1).strip().rstrip(",")

    # Tentativa 5: campo pipe separado (ex: "Tony | 18/10/1979 | 14:00 | Belo Horizonte, MG")
    if not cidade_encontrada:
        pipe_parts = [p.strip() for p in texto.split("|")]
        for part in pipe_parts:
            if (
                re.search(r"[A-ZÀ-Úa-zà-ú]{4,}", part)
                and not re.search(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}", part)
                and not re.search(r"\d{1,2}h\d{2}|\d{1,2}:\d{2}", part)
                and not re.search(r"^(?:paciente|nome|data|hora|local)\s*:", part, re.I)
                and len(part) > 5
                and part not in resultado.values()
            ):
                cidade_encontrada = part.rstrip(",").strip()
                break

    if cidade_encontrada:
        resultado["cidade"] = cidade_encontrada

    # --- Verificar se temos dados suficientes ---
    campos_obrigatorios = ["data", "hora", "cidade"]
    if all(c in resultado for c in campos_obrigatorios):
        # Nome é opcional — se não encontrado, usar placeholder
        if "nome" not in resultado:
            resultado["nome"] = "Paciente"
        return resultado

    # Caso especial: temos hora e cidade mas a data está incompleta (falta o ano).
    # Retornar dict parcial com flag "falta_ano" para que o webhook possa perguntar o ano.
    if "data_parcial" in resultado and "hora" in resultado and "cidade" in resultado:
        if "nome" not in resultado:
            resultado["nome"] = "Paciente"
        resultado["falta_ano"] = True
        return resultado

    return None


# ---------------------------------------------------------------------------
# Extração de dados de nascimento via LLM (agente robusto)
# ---------------------------------------------------------------------------

_PROMPT_NASC_LLM = """\
Analise o texto abaixo e extraia dados de nascimento de uma pessoa específica, SE existirem.

Texto:
\"\"\"{texto}\"\"\"

Retorne APENAS JSON válido (sem markdown, sem explicação, sem texto extra):
{{"nome": "Nome Completo", "data": "DD/MM/AAAA", "hora": "HH:MM", "cidade": "Cidade"}}

Regras obrigatórias:
- Só extraia se o texto contiver data + hora + cidade de nascimento de alguém
- Normalize cidade: "SP" → "São Paulo", "São Paulo capital" → "São Paulo",
  "Rio" → "Rio de Janeiro", "BH" → "Belo Horizonte", "BSB" → "Brasília",
  "Sampa" → "São Paulo", use o nome completo da cidade sempre
- Data obrigatoriamente em DD/MM/AAAA
- Hora em HH:MM (24h); "meio-dia"/"12h" = "12:00", "meia-noite" = "00:00"
- Nome: extraia se presente no texto; caso contrário use null
- Se NÃO há dados de nascimento completos (data + hora + cidade), retorne exatamente:
  {{"nome": null, "data": null, "hora": null, "cidade": null}}
- Não invente dados que não estão no texto"""


async def extrair_dados_nascimento_llm(texto: str) -> Optional[dict]:
    """
    Agente LLM (Claude Haiku) para extrair dados de nascimento de qualquer formato.

    Muito mais robusto que regex: interpreta linguagem natural, áudio transcrito,
    abreviações de cidades ("SP", "BH", "Rio"), datas por extenso, variações de hora.

    Fallback automático para regex se a chamada LLM falhar.

    Args:
        texto: Texto a ser analisado (pode ser mensagem, histórico concatenado, transcrição de áudio)

    Returns:
        Dict com 'nome', 'data' (DD/MM/AAAA), 'hora' (HH:MM), 'cidade' ou None se incompleto.
    """
    import asyncio
    import json as _json

    if not texto or len(texto.strip()) < 5:
        return None

    # Pré-filtro rápido: sem dígito → sem data/hora → não há nascimento
    if not re.search(r"\d", texto):
        return None

    try:
        import anthropic
        from src.core.config import get_settings

        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        resposta = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": _PROMPT_NASC_LLM.format(texto=texto[:600]),
                }],
            ),
            timeout=12.0,
        )

        texto_resp = resposta.content[0].text.strip()
        # Remove blocos markdown se o modelo insistir em adicioná-los
        texto_resp = re.sub(r"^```(?:json)?\s*", "", texto_resp)
        texto_resp = re.sub(r"\s*```$", "", texto_resp).strip()

        dados = _json.loads(texto_resp)

        # Normalizar: converter string "null" para None real
        nome  = dados.get("nome")  if dados.get("nome")  not in (None, "null", "") else None
        data  = dados.get("data")  if dados.get("data")  not in (None, "null", "") else None
        hora  = dados.get("hora")  if dados.get("hora")  not in (None, "null", "") else None
        cidade = dados.get("cidade") if dados.get("cidade") not in (None, "null", "") else None

        if data and hora and cidade:
            resultado = {"data": data, "hora": hora, "cidade": cidade}
            resultado["nome"] = nome if nome else "Paciente"
            print(f"[NASC-LLM] Extraído: {resultado}", flush=True)
            logger.info(f"LLM extraiu dados de nascimento: {resultado}")
            return resultado

        # Sem dados completos → None (não ativa cálculo de mapa)
        return None

    except Exception as llm_err:
        print(f"[NASC-LLM] Falhou ({type(llm_err).__name__}: {llm_err}) — fallback regex", flush=True)
        logger.warning(f"Extração LLM de nascimento falhou — usando regex: {llm_err}")
        # Fallback robusto para o extrator regex
        return extrair_dados_nascimento(texto)


def gerar_mapa_completo(
    nome: str,
    data_nascimento: str,
    hora_nascimento: str,
    cidade_nascimento: str,
) -> Tuple[str, Optional[bytes]]:
    """
    Calcula o mapa natal e gera a imagem PNG.

    Combina calcular_mapa_natal() (texto formatado) com gerar_imagem_mapa_natal()
    (PNG em bytes) em uma única chamada conveniente.

    Args:
        nome: Nome do paciente
        data_nascimento: Data no formato DD/MM/AAAA
        hora_nascimento: Hora no formato HH:MM
        cidade_nascimento: Cidade de nascimento

    Returns:
        Tuple[str, Optional[bytes]]:
            - str: texto formatado do mapa natal (sempre presente)
            - Optional[bytes]: PNG do mapa natal, ou None se geração de imagem falhar
    """
    from kerykeion import AstrologicalSubjectFactory
    from kerykeion.aspects.aspects_factory import AspectsFactory

    # --- Parsing dos dados ---
    try:
        dia, mes, ano = [int(x) for x in data_nascimento.strip().split("/")]
    except ValueError as e:
        raise ValueError(
            f"Formato de data inválido: '{data_nascimento}'. Use DD/MM/AAAA."
        ) from e

    try:
        hora, minuto = [int(x) for x in hora_nascimento.strip().split(":")]
    except ValueError as e:
        raise ValueError(
            f"Formato de hora inválido: '{hora_nascimento}'. Use HH:MM."
        ) from e

    # --- Geocodificação (cache local primeiro, Nominatim como fallback) ---
    lat, lon, tz_str = _geocodificar_cidade(cidade_nascimento)

    # --- Cálculo astrológico ---
    sujeito = AstrologicalSubjectFactory.from_birth_data(
        name=nome,
        year=ano,
        month=mes,
        day=dia,
        hour=hora,
        minute=minuto,
        lng=lon,
        lat=lat,
        tz_str=tz_str,
        online=False,
        zodiac_type="Tropical",
        houses_system_identifier="P",
        suppress_geonames_warning=True,
    )

    # --- Texto formatado — usa _formatar_texto_mapa com o sujeito já calculado
    # (evita dupla geocodificação que calcular_mapa_natal faria internamente)
    texto = _formatar_texto_mapa(
        sujeito=sujeito,
        nome=nome,
        dia=dia,
        mes=mes,
        ano=ano,
        hora=hora,
        minuto=minuto,
        cidade_nascimento=cidade_nascimento,
        lat=lat,
        lon=lon,
        tz_str=tz_str,
    )

    # --- Imagem PNG ---
    imagem_png: Optional[bytes] = None
    try:
        print(f"[MAPA] Iniciando geração de imagem para '{nome}'", flush=True)
        from src.rag.chart_generator import dados_mapa_de_sujeito, gerar_imagem_mapa_natal
        dados = dados_mapa_de_sujeito(
            sujeito=sujeito,
            nome_paciente=nome,
            data_nascimento=data_nascimento,
            hora_nascimento=hora_nascimento,
            cidade_nascimento=cidade_nascimento,
        )
        imagem_png = gerar_imagem_mapa_natal(dados)
        print(f"[MAPA] Imagem gerada para '{nome}': {len(imagem_png) // 1024} KB", flush=True)
        logger.info(f"Imagem do mapa natal gerada para '{nome}' ({len(imagem_png) // 1024} KB)")
    except Exception as img_err:
        print(f"[MAPA] ERRO ao gerar imagem para '{nome}': {img_err}", flush=True)
        logger.warning(f"Geração de imagem do mapa natal falhou — continuando apenas com texto: {img_err}", exc_info=True)

    return texto, imagem_png
