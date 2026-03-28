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

    try:
        from geopy.geocoders import Nominatim
        from timezonefinder import TimezoneFinder
    except ImportError as e:
        raise ImportError(
            "geopy/timezonefinder não instalados. Execute: pip install geopy timezonefinder"
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

    # --- Geocodificação ---
    geolocator = Nominatim(user_agent="alquimista-interior-bot/1.0", timeout=10)

    location = None
    tentativas = [
        cidade_nascimento,
        cidade_nascimento + ", Brasil",  # fallback para cidades BR sem sufixo
    ]
    for tentativa in tentativas:
        try:
            time.sleep(1)  # respeitar rate limit do Nominatim
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

    # --- Timezone ---
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon)
    if not tz_str:
        logger.warning(
            f"Timezone não encontrada para ({lat}, {lon}). Usando America/Sao_Paulo."
        )
        tz_str = "America/Sao_Paulo"

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
    # Padrões: "paciente: Nome", "nome: Nome", "nome do paciente: Nome"
    nome_match = re.search(
        r"(?:paciente|nome do paciente|nome)\s*[:\-]\s*([A-ZÀ-Úa-zà-ú][a-zA-ZÀ-ú\s]{2,40}?)(?:\s*[\|\,\n]|$)",
        texto,
        re.IGNORECASE,
    )
    if nome_match:
        resultado["nome"] = nome_match.group(1).strip()

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
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

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

    # --- Geocodificação ---
    geolocator = Nominatim(user_agent="alquimista-interior-bot/1.0", timeout=10)
    location = None
    tentativas = [cidade_nascimento, cidade_nascimento + ", Brasil"]
    for tentativa in tentativas:
        try:
            time.sleep(1)
            location = geolocator.geocode(tentativa, language="pt")
            if location:
                break
        except Exception as geo_err:
            logger.warning(f"Geocodificação falhou para '{tentativa}': {geo_err}")

    if not location:
        raise ValueError(f"Cidade não encontrada: '{cidade_nascimento}'.")

    lat = location.latitude
    lon = location.longitude

    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon) or "America/Sao_Paulo"

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
        from src.rag.chart_generator import dados_mapa_de_sujeito, gerar_imagem_mapa_natal
        dados = dados_mapa_de_sujeito(
            sujeito=sujeito,
            nome_paciente=nome,
            data_nascimento=data_nascimento,
            hora_nascimento=hora_nascimento,
            cidade_nascimento=cidade_nascimento,
        )
        imagem_png = gerar_imagem_mapa_natal(dados)
        logger.info(f"Imagem do mapa natal gerada para '{nome}' ({len(imagem_png) // 1024} KB)")
    except Exception as img_err:
        logger.warning(f"Geração de imagem do mapa natal falhou — continuando apenas com texto: {img_err}")

    return texto, imagem_png
