"""
Webhook do Asaas — recebe eventos de pagamento e gerencia assinaturas.

Eventos tratados:
- PAYMENT_RECEIVED: pagamento confirmado → renovar assinatura
- PAYMENT_OVERDUE: pagamento atrasado → suspender acesso
- PAYMENT_DELETED: pagamento cancelado → suspender acesso
- SUBSCRIPTION_DELETED: assinatura cancelada → cancelar acesso definitivamente

Segurança: validar o token de acesso no header antes de processar.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional

from src.core.config import get_settings
from src.core.assinatura import (
    renovar_assinatura,
    suspender_por_falha_pagamento,
    cancelar_assinatura,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook Asaas"])


@router.post("/asaas", summary="Recebe eventos de pagamento do Asaas")
async def webhook_asaas(
    request: Request,
    asaas_access_token: Optional[str] = Header(None, alias="asaas-access-token"),
):
    """
    Endpoint que recebe webhooks do Asaas.

    Configure no painel Asaas → Integrações → Webhooks:
    URL: https://modest-respect-production.up.railway.app/webhook/asaas

    Eventos suportados:
    - PAYMENT_RECEIVED → renova assinatura
    - PAYMENT_OVERDUE → suspende por atraso
    - PAYMENT_DELETED → suspende por cancelamento de pagamento
    - SUBSCRIPTION_DELETED → cancela assinatura definitivamente
    """
    settings = get_settings()

    # Validar token do Asaas (configurar ASAAS_WEBHOOK_TOKEN no Railway)
    expected_token = getattr(settings, "ASAAS_WEBHOOK_TOKEN", "")
    if expected_token and asaas_access_token != expected_token:
        logger.warning(f"Webhook Asaas: token inválido recebido")
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event = body.get("event", "")
    payment = body.get("payment", {})
    subscription = body.get("subscription", {})

    subscription_id = (
        payment.get("subscription")
        or subscription.get("id")
        or body.get("id", "")
    )

    logger.info(f"Asaas webhook: event={event} | subscription_id={subscription_id}")

    if event == "PAYMENT_RECEIVED":
        # Pagamento confirmado → renovar mais 1 mês
        renovar_assinatura(
            asaas_subscription_id=subscription_id,
            meses_adicionais=1,
        )

    elif event in ("PAYMENT_OVERDUE",):
        # Pagamento atrasado → suspender (aviso)
        suspender_por_falha_pagamento(
            asaas_subscription_id=subscription_id,
            payment_status=event,
        )

    elif event in ("PAYMENT_DELETED", "PAYMENT_REFUNDED"):
        # Pagamento cancelado/estornado → suspender
        suspender_por_falha_pagamento(
            asaas_subscription_id=subscription_id,
            payment_status=event,
        )

    elif event == "SUBSCRIPTION_DELETED":
        # Assinatura cancelada definitivamente
        cancelar_assinatura(asaas_subscription_id=subscription_id)

    else:
        logger.debug(f"Asaas webhook evento ignorado: {event}")

    # Asaas espera 200 OK
    return {"status": "ok", "event": event}
