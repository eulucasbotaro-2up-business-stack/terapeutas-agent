"""
Extracao automatica de dados diagnosticos a partir de respostas do agente.

Analisa respostas em modo CONSULTA usando pattern matching (regex) para
detectar sinais diagnosticos do metodo alquimico: elementos, substancias,
serpentes DNA, niveis de floral, setenios e fases alquimicas.

Se pelo menos 2 sinais distintos forem encontrados, cria um RASCUNHO
na tabela diagnosticos_alquimicos para o terapeuta revisar no portal.

IMPORTANTE:
- Nunca auto-finaliza — sempre status "rascunho"
- Usa regex puro, sem chamada LLM adicional
- Roda em background para nao atrasar resposta do WhatsApp
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# PADROES DE DETECCAO — regex para cada sinal diagnostico
# =============================================================================

# Elementos (terra, ar, fogo, agua)
_RE_ELEMENTO_DOMINANTE = re.compile(
    r"excesso\s+de\s+(terra|ar|fogo|[aá]gua)",
    re.IGNORECASE | re.UNICODE,
)
_RE_ELEMENTO_CARENTE = re.compile(
    r"falta\s+de\s+(terra|ar|fogo|[aá]gua)",
    re.IGNORECASE | re.UNICODE,
)
# Variantes adicionais: "elemento X em excesso/falta/desequilibrio", "desequilibrio no elemento X"
_RE_ELEMENTO_DESEQUILIBRIO = re.compile(
    r"(terra|ar|fogo|[aá]gua)\s+em\s+(?:desequil[ií]brio|excesso|falta)",
    re.IGNORECASE | re.UNICODE,
)
_RE_DESEQUILIBRIO_NO_ELEMENTO = re.compile(
    r"desequil[ií]brio\s+(?:no|do)\s+elemento\s+(terra|ar|fogo|[aá]gua)",
    re.IGNORECASE | re.UNICODE,
)
_RE_ELEMENTO_EM_ESTADO = re.compile(
    r"elemento\s+(terra|ar|fogo|[aá]gua)\s+em\s+(?:excesso|falta|desequil[ií]brio)",
    re.IGNORECASE | re.UNICODE,
)

# Substancias alquimicas (Enxofre/Sulfurico, Sal/Salino, Mercurio/Mercurial)
_RE_SULFURICO = re.compile(r"sulfúric|sulfuric|enxofre\s+(?:elevado|alto|em\s+excesso)", re.IGNORECASE | re.UNICODE)
_RE_SALINO = re.compile(r"salin[oa]|sal\s+(?:elevado|alto|em\s+excesso)", re.IGNORECASE | re.UNICODE)
_RE_MERCURIAL = re.compile(r"mercurial|merc[uú]rio\s+(?:elevado|alto|em\s+excesso)", re.IGNORECASE | re.UNICODE)

# Serpentes DNA
_RE_SERPENTE_PAI = re.compile(r"serpente\s+do\s+pai", re.IGNORECASE | re.UNICODE)
_RE_SERPENTE_MAE = re.compile(r"serpente\s+da\s+m[aã]e", re.IGNORECASE | re.UNICODE)

# Nivel de floral (1, 2, 3)
_RE_NIVEL_FLORAL = re.compile(r"n[íi]vel\s+(\d)", re.IGNORECASE | re.UNICODE)

# Setenio
_RE_SETENIO = re.compile(r"(\d+)[ºo]?\s*set[êe]nio", re.IGNORECASE | re.UNICODE)
# Variante: "primeiro setenio", "segundo setenio", etc.
_SETENIO_POR_EXTENSO = {
    "primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4,
    "quinto": 5, "sexto": 6, "setimo": 7, "sétimo": 7,
    "oitavo": 8, "nono": 9, "decimo": 10, "décimo": 10,
}
_RE_SETENIO_EXTENSO = re.compile(
    r"(primeiro|segundo|terceiro|quarto|quinto|sexto|s[eé]timo|oitavo|nono|d[eé]cimo)\s+set[êe]nio",
    re.IGNORECASE | re.UNICODE,
)

# Fases alquimicas
_RE_FASE = re.compile(r"\b(nigredo|albedo|rubedo|citrinitas)\b", re.IGNORECASE | re.UNICODE)

# Fluxo continuo
_RE_FLUXO_CONTINUO = re.compile(r"fluxo\s+cont[íi]nuo", re.IGNORECASE | re.UNICODE)


# =============================================================================
# FUNCAO PRINCIPAL
# =============================================================================

def extrair_diagnostico_automatico(
    resposta: str,
    terapeuta_id: str,
    paciente_id: str,
) -> Optional[dict]:
    """
    Analisa a resposta do agente e extrai dados diagnosticos automaticamente.
    Retorna dict com dados do diagnostico ou None se nao houver diagnostico.
    Salva como RASCUNHO — terapeuta deve revisar no portal.

    Requer pelo menos 2 sinais diagnosticos distintos para evitar falsos positivos.

    Args:
        resposta: Texto da resposta gerada pelo agente.
        terapeuta_id: UUID do terapeuta.
        paciente_id: UUID do paciente vinculado na conversa.

    Returns:
        Dict com os dados extraidos e salvos, ou None se insuficiente.
    """
    if not resposta or not paciente_id:
        return None

    # Contadores de sinais encontrados
    sinais_encontrados: list[str] = []
    dados: dict = {
        "elemento_dominante": None,
        "elemento_carente": None,
        "substancias": {},
        "serpentes_ativas": [],
        "nivel_floral": None,
        "setenio_atual": None,
        "fluxo_continuo": None,
    }

    # --- Elementos ---
    match_dom = _RE_ELEMENTO_DOMINANTE.search(resposta)
    if match_dom:
        elemento = _normalizar_elemento(match_dom.group(1))
        dados["elemento_dominante"] = elemento
        sinais_encontrados.append(f"elemento_dominante={elemento}")

    match_car = _RE_ELEMENTO_CARENTE.search(resposta)
    if match_car:
        elemento = _normalizar_elemento(match_car.group(1))
        dados["elemento_carente"] = elemento
        sinais_encontrados.append(f"elemento_carente={elemento}")

    match_deseq = (
        _RE_ELEMENTO_DESEQUILIBRIO.search(resposta)
        or _RE_DESEQUILIBRIO_NO_ELEMENTO.search(resposta)
        or _RE_ELEMENTO_EM_ESTADO.search(resposta)
    )
    if match_deseq and not match_dom:
        # Se nao encontrou excesso, desequilibrio serve como dominante
        elemento = _normalizar_elemento(match_deseq.group(1))
        dados["elemento_dominante"] = elemento
        sinais_encontrados.append(f"elemento_desequilibrio={elemento}")

    # --- Substancias ---
    if _RE_SULFURICO.search(resposta):
        dados["substancias"]["enxofre"] = "alto"
        sinais_encontrados.append("substancia=enxofre")

    if _RE_SALINO.search(resposta):
        dados["substancias"]["sal"] = "alto"
        sinais_encontrados.append("substancia=sal")

    if _RE_MERCURIAL.search(resposta):
        dados["substancias"]["mercurio"] = "alto"
        sinais_encontrados.append("substancia=mercurio")

    # --- Serpentes DNA ---
    if _RE_SERPENTE_PAI.search(resposta):
        dados["serpentes_ativas"].append("pai")
        sinais_encontrados.append("serpente=pai")

    if _RE_SERPENTE_MAE.search(resposta):
        dados["serpentes_ativas"].append("mae")
        sinais_encontrados.append("serpente=mae")

    # --- Nivel floral ---
    match_nivel = _RE_NIVEL_FLORAL.search(resposta)
    if match_nivel:
        nivel = int(match_nivel.group(1))
        if 1 <= nivel <= 3:
            dados["nivel_floral"] = nivel
            sinais_encontrados.append(f"nivel_floral={nivel}")

    # --- Setenio ---
    match_set = _RE_SETENIO.search(resposta)
    if match_set:
        setenio = int(match_set.group(1))
        if 1 <= setenio <= 15:
            dados["setenio_atual"] = setenio
            sinais_encontrados.append(f"setenio={setenio}")
    else:
        match_set_ext = _RE_SETENIO_EXTENSO.search(resposta)
        if match_set_ext:
            palavra = match_set_ext.group(1).lower().replace("é", "e")
            setenio = _SETENIO_POR_EXTENSO.get(palavra)
            if setenio:
                dados["setenio_atual"] = setenio
                sinais_encontrados.append(f"setenio={setenio}")

    # --- Fases alquimicas ---
    match_fase = _RE_FASE.search(resposta)
    if match_fase:
        fase = match_fase.group(1).lower()
        sinais_encontrados.append(f"fase={fase}")
        # Fase nao tem campo proprio no schema, mas entra no protocolo_texto

    # --- Fluxo continuo ---
    if _RE_FLUXO_CONTINUO.search(resposta):
        dados["fluxo_continuo"] = True
        sinais_encontrados.append("fluxo_continuo")

    # --- Verificar minimo de sinais ---
    if len(sinais_encontrados) < 2:
        logger.debug(
            f"[DIAGNOSTICO_AUTO] Sinais insuficientes ({len(sinais_encontrados)}): "
            f"{sinais_encontrados} | terapeuta={terapeuta_id}"
        )
        return None

    # --- Montar registro do diagnostico ---
    logger.info(
        f"[DIAGNOSTICO_AUTO] {len(sinais_encontrados)} sinais encontrados: "
        f"{sinais_encontrados} | terapeuta={terapeuta_id} | paciente={paciente_id}"
    )

    registro = {
        "id": str(uuid4()),
        "terapeuta_id": terapeuta_id,
        "paciente_id": paciente_id,
        "status": "rascunho",
        "sessao_data": datetime.now(timezone.utc).date().isoformat(),
        "protocolo_texto": resposta[:500],
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "origem": "auto_extracao_whatsapp",
    }

    # Preencher campos extraidos (somente os que tem valor)
    if dados["elemento_dominante"]:
        registro["elemento_dominante"] = dados["elemento_dominante"]
    if dados["elemento_carente"]:
        registro["elemento_carente"] = dados["elemento_carente"]
    if dados["substancias"]:
        registro["substancias"] = dados["substancias"]
    if dados["serpentes_ativas"]:
        registro["serpentes_ativas"] = dados["serpentes_ativas"]
    if dados["nivel_floral"] is not None:
        registro["nivel_floral"] = dados["nivel_floral"]
    if dados["setenio_atual"] is not None:
        registro["setenio_atual"] = dados["setenio_atual"]
    if dados["fluxo_continuo"] is not None:
        registro["fluxo_continuo"] = dados["fluxo_continuo"]

    return registro


def _normalizar_elemento(elemento_raw: str) -> str:
    """Normaliza nome do elemento para formato padrao do banco."""
    mapa = {
        "terra": "Terra",
        "ar": "Ar",
        "fogo": "Fogo",
        "agua": "Agua",
        "água": "Agua",
    }
    return mapa.get(elemento_raw.lower(), elemento_raw.capitalize())


# =============================================================================
# FUNCAO DE PERSISTENCIA — salvar no Supabase
# =============================================================================

def _salvar_diagnostico_sync(registro: dict) -> None:
    """
    Persiste o diagnostico rascunho na tabela diagnosticos_alquimicos.
    Versao sincrona — deve ser chamada via asyncio.to_thread().
    """
    supabase = get_supabase()
    supabase.table("diagnosticos_alquimicos").insert(registro).execute()
    logger.info(
        f"[DIAGNOSTICO_AUTO] Rascunho salvo — id={registro['id']} "
        f"terapeuta={registro['terapeuta_id']} paciente={registro['paciente_id']}"
    )


async def processar_diagnostico_auto(
    resposta: str,
    terapeuta_id: str,
    paciente_id: str,
) -> None:
    """
    Funcao async para rodar em background (asyncio.create_task).
    Extrai sinais diagnosticos e salva rascunho se houver dados suficientes.
    Nunca levanta excecao — erros sao apenas logados.
    """
    import asyncio

    try:
        registro = extrair_diagnostico_automatico(resposta, terapeuta_id, paciente_id)
        if registro:
            await asyncio.to_thread(_salvar_diagnostico_sync, registro)
    except Exception as e:
        logger.error(
            f"[DIAGNOSTICO_AUTO] Erro ao processar: {e} | "
            f"terapeuta={terapeuta_id} paciente={paciente_id}",
            exc_info=True,
        )
