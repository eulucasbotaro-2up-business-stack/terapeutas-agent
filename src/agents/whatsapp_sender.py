"""
Envio proativo de mensagens WhatsApp — usado pelos agentes de automação.

Suporta Evolution API e Meta Cloud API, com fallback automático.
Usado por: renovacao.py, reengajamento.py, cs.py, boas_vindas
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_EVO_URL     = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
_EVO_KEY     = os.getenv("EVOLUTION_API_KEY", "")
_EVO_INST    = os.getenv("EVOLUTION_INSTANCE", "terapeutas")

_META_TOKEN  = os.getenv("META_WHATSAPP_TOKEN", "")
_META_PHONE  = os.getenv("META_PHONE_NUMBER_ID", "")

# Timeout para chamadas de envio de mensagem
_TIMEOUT = 15.0


def _normalizar_numero(numero: str) -> str:
    """
    Normaliza número para formato internacional sem + e sem espaços.
    Ex: '+55 11 91234-5678' → '5511912345678'
    """
    return "".join(c for c in numero if c.isdigit())


async def enviar_mensagem(
    numero: str,
    texto: str,
    instancia: Optional[str] = None,
) -> bool:
    """
    Envia mensagem de texto via Evolution API.
    Tenta Evolution API primeiro; se falhar, tenta Meta.

    Args:
        numero: Número do destinatário (qualquer formato — será normalizado).
        texto: Texto da mensagem.
        instancia: Nome da instância Evolution (opcional, usa default).

    Returns:
        True se enviado com sucesso por qualquer provedor.
    """
    numero_limpo = _normalizar_numero(numero)
    inst = instancia or _EVO_INST

    # Tentar Evolution API primeiro
    if _EVO_URL and _EVO_KEY:
        ok = await _enviar_evolution(numero_limpo, texto, inst)
        if ok:
            return True
        logger.warning(f"Evolution falhou para {numero_limpo}, tentando Meta...")

    # Fallback para Meta Cloud API
    if _META_TOKEN and _META_PHONE:
        ok = await _enviar_meta(numero_limpo, texto)
        if ok:
            return True

    logger.error(f"Todos os provedores falharam ao enviar para {numero_limpo}")
    return False


async def _enviar_evolution(numero: str, texto: str, instancia: str) -> bool:
    """Envia via Evolution API."""
    url = f"{_EVO_URL}/message/sendText/{instancia}"
    payload = {
        "number": numero,
        "textMessage": {"text": texto},
    }
    headers = {"apikey": _EVO_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code in (200, 201):
            logger.info(f"Evolution: mensagem enviada para {numero}")
            return True
        else:
            logger.warning(
                f"Evolution retornou {resp.status_code} para {numero}: {resp.text[:200]}"
            )
            return False

    except Exception as e:
        logger.warning(f"Evolution erro para {numero}: {e}")
        return False


async def _enviar_meta(numero: str, texto: str) -> bool:
    """Envia via Meta Cloud API."""
    url = f"https://graph.facebook.com/v21.0/{_META_PHONE}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {"preview_url": False, "body": texto},
    }
    headers = {
        "Authorization": f"Bearer {_META_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code == 200:
            logger.info(f"Meta: mensagem enviada para {numero}")
            return True
        else:
            logger.warning(
                f"Meta retornou {resp.status_code} para {numero}: {resp.text[:200]}"
            )
            return False

    except Exception as e:
        logger.warning(f"Meta erro para {numero}: {e}")
        return False


def _registrar_log(
    tipo_campanha: str,
    numero: str,
    etapa: str,
    mensagem: str,
    status: str,
    campanha_id: Optional[str] = None,
    erro: Optional[str] = None,
) -> None:
    """Registra envio no log_mensagens_automaticas (síncrono via Supabase)."""
    try:
        from src.core.supabase_client import get_supabase
        get_supabase().table("log_mensagens_automaticas").insert({
            "tipo_campanha":  tipo_campanha,
            "campanha_id":    campanha_id,
            "numero_telefone": numero,
            "etapa":          etapa,
            "mensagem":       mensagem[:1000],  # truncar para não explodir o DB
            "status_envio":   status,
            "erro":           erro,
        }).execute()
    except Exception as e:
        logger.warning(f"Falha ao registrar log de mensagem automática: {e}")
