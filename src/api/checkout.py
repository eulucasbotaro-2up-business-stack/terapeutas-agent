"""
API de Checkout — cria cliente + assinatura no Asaas e gera código de acesso.

Fluxo:
  1. Frontend envia dados do formulário (nome, email, CPF, telefone, plano, payment data)
  2. Backend cria customer no Asaas
  3. Backend cria subscription no Asaas (com 7 dias de trial via nextDueDate)
  4. Backend gera código de liberação aleatório (6 chars, alfanumérico)
  5. Backend salva tudo no Supabase (codigos_liberacao)
  6. Backend dispara mensagem WhatsApp com o código
  7. Retorna sucesso para frontend redirecionar para /obrigado
"""

import asyncio
import logging
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.core.assinatura import criar_codigo_assinatura

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portal", tags=["Checkout"])

# Planos disponíveis
PLANOS = {
    "essencial": {
        "nome": "Essencial",
        "valor": 197.00,
        "descricao": "TerapeutasAgent — Plano Essencial",
        "ciclo": "MONTHLY",
    },
    "profissional": {
        "nome": "Profissional",
        "valor": 297.00,
        "descricao": "TerapeutasAgent — Plano Profissional",
        "ciclo": "MONTHLY",
    },
}

ASAAS_BASE_URL = "https://api.asaas.com/api/v3"


class CheckoutRequest(BaseModel):
    nome: str
    email: EmailStr
    cpf: str
    telefone: str  # WhatsApp number
    plano: str  # "essencial" or "profissional"
    # Método de pagamento
    metodo_pagamento: str  # "PIX", "CREDIT_CARD", "BOLETO"
    # Campos de cartão de crédito (opcional, só para CREDIT_CARD)
    card_holder_name: Optional[str] = None
    card_number: Optional[str] = None
    card_expiry_month: Optional[str] = None
    card_expiry_year: Optional[str] = None
    card_cvv: Optional[str] = None
    card_holder_cpf: Optional[str] = None
    card_holder_cep: Optional[str] = None
    card_holder_address_number: Optional[str] = None
    card_holder_phone: Optional[str] = None


def _gerar_codigo(length: int = 6) -> str:
    """Gera código alfanumérico único (ex: A3B7K9)."""
    chars = string.ascii_uppercase + string.digits
    # Remove chars ambíguos (0/O, 1/I/L)
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")
    return "".join(secrets.choice(chars) for _ in range(length))


def _normalizar_telefone(tel: str) -> str:
    """Remove formatação e garante formato 55XXXXXXXXXXX."""
    digits = "".join(c for c in tel if c.isdigit())
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


async def _criar_cliente_asaas(nome: str, email: str, cpf: str, telefone: str) -> dict:
    """Cria cliente no Asaas e retorna o response."""
    settings = get_settings()
    headers = {"access_token": settings.ASAAS_API_KEY, "Content-Type": "application/json"}

    payload = {
        "name": nome,
        "email": email,
        "cpfCnpj": cpf.replace(".", "").replace("-", ""),
        "mobilePhone": telefone,
        "notificationDisabled": False,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{ASAAS_BASE_URL}/customers", json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(f"Asaas criar cliente falhou: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=502, detail="Erro ao criar cliente no gateway de pagamento")
        return resp.json()


async def _criar_assinatura_asaas(
    customer_id: str, plano: dict, metodo: str, card_data: dict = None
) -> dict:
    """Cria assinatura no Asaas com trial de 7 dias."""
    settings = get_settings()
    headers = {"access_token": settings.ASAAS_API_KEY, "Content-Type": "application/json"}

    # Primeiro pagamento em 7 dias (trial gratuito)
    primeiro_pagamento = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

    payload = {
        "customer": customer_id,
        "billingType": metodo,
        "value": plano["valor"],
        "cycle": plano["ciclo"],
        "nextDueDate": primeiro_pagamento,
        "description": plano["descricao"],
    }

    # Se cartão de crédito, adicionar dados do cartão
    if metodo == "CREDIT_CARD" and card_data:
        payload["creditCard"] = {
            "holderName": card_data.get("holder_name", ""),
            "number": card_data.get("number", "").replace(" ", ""),
            "expiryMonth": card_data.get("expiry_month", ""),
            "expiryYear": card_data.get("expiry_year", ""),
            "ccv": card_data.get("cvv", ""),
        }
        payload["creditCardHolderInfo"] = {
            "name": card_data.get("holder_name", ""),
            "email": card_data.get("email", ""),
            "cpfCnpj": card_data.get("holder_cpf", "").replace(".", "").replace("-", ""),
            "postalCode": card_data.get("holder_cep", "").replace("-", ""),
            "addressNumber": card_data.get("holder_address_number", ""),
            "phone": card_data.get("holder_phone", ""),
        }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{ASAAS_BASE_URL}/subscriptions", json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(f"Asaas criar assinatura falhou: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=502, detail="Erro ao criar assinatura no gateway de pagamento")
        return resp.json()


async def _enviar_codigo_whatsapp(telefone: str, codigo: str, nome: str, plano_nome: str):
    """Envia código de acesso via WhatsApp usando o sender existente."""
    mensagem = (
        f"Olá, {nome}! 🎉\n\n"
        f"Sua assinatura do *TerapeutasAgent — Plano {plano_nome}* foi confirmada!\n\n"
        f"🔑 Seu código de acesso: *{codigo}*\n\n"
        f"Para ativar, envie o código nesta conversa.\n"
        f"Quando quiser começar, é só me avisar! 🚀"
    )

    try:
        from src.agents.whatsapp_sender import enviar_mensagem

        ok = await enviar_mensagem(numero=telefone, texto=mensagem)
        if ok:
            logger.info(f"Código {codigo} enviado via WhatsApp para {telefone}")
        else:
            logger.warning(f"WhatsApp sender retornou False para {telefone} — código: {codigo}")
    except Exception as e:
        # Não falhar o checkout por falha no envio — pode ser enviado manualmente
        logger.error(f"Falha ao enviar código WhatsApp: {e}")


@router.post("/checkout", summary="Processa checkout e cria assinatura")
async def processar_checkout(dados: CheckoutRequest):
    """
    Fluxo completo de checkout:
    1. Valida plano
    2. Cria cliente no Asaas
    3. Cria assinatura no Asaas (trial 7 dias)
    4. Gera código de liberação
    5. Salva no Supabase
    6. Envia código via WhatsApp
    7. Retorna sucesso
    """
    # 1. Validar plano
    plano = PLANOS.get(dados.plano)
    if not plano:
        raise HTTPException(status_code=400, detail=f"Plano inválido: {dados.plano}")

    # Validar método de pagamento
    if dados.metodo_pagamento not in ("PIX", "CREDIT_CARD", "BOLETO"):
        raise HTTPException(status_code=400, detail="Método de pagamento inválido")

    telefone = _normalizar_telefone(dados.telefone)

    # 2. Criar cliente no Asaas
    cliente_asaas = await _criar_cliente_asaas(
        nome=dados.nome,
        email=dados.email,
        cpf=dados.cpf,
        telefone=telefone,
    )
    customer_id = cliente_asaas.get("id", "")

    # 3. Criar assinatura no Asaas
    card_data = None
    if dados.metodo_pagamento == "CREDIT_CARD":
        card_data = {
            "holder_name": dados.card_holder_name or dados.nome,
            "number": dados.card_number or "",
            "expiry_month": dados.card_expiry_month or "",
            "expiry_year": dados.card_expiry_year or "",
            "cvv": dados.card_cvv or "",
            "email": dados.email,
            "holder_cpf": dados.card_holder_cpf or dados.cpf,
            "holder_cep": dados.card_holder_cep or "",
            "holder_address_number": dados.card_holder_address_number or "",
            "holder_phone": dados.card_holder_phone or dados.telefone,
        }

    assinatura = await _criar_assinatura_asaas(
        customer_id=customer_id,
        plano=plano,
        metodo=dados.metodo_pagamento,
        card_data=card_data,
    )
    subscription_id = assinatura.get("id", "")

    # 4. Gerar código único
    codigo = _gerar_codigo(6)

    # 5. Salvar no Supabase via função existente
    TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"
    criar_codigo_assinatura(
        terapeuta_id=TERAPEUTA_ID,
        codigo=codigo,
        meses=1,  # Mensal (renovado via webhook)
        descricao=f"{dados.nome} — {plano['nome']} ({dados.email})",
        asaas_subscription_id=subscription_id,
        asaas_customer_id=customer_id,
    )

    # 6. Enviar código via WhatsApp (async, não bloqueia resposta)
    asyncio.create_task(
        _enviar_codigo_whatsapp(
            telefone=telefone,
            codigo=codigo,
            nome=dados.nome.split()[0],  # Primeiro nome
            plano_nome=plano["nome"],
        )
    )

    # 7. Retornar para frontend
    response_data = {
        "sucesso": True,
        "plano": dados.plano,
        "nome": dados.nome,
        "mensagem": "Assinatura criada com sucesso!",
    }

    # Se PIX, buscar QR code do primeiro pagamento
    if dados.metodo_pagamento == "PIX" and subscription_id:
        try:
            settings = get_settings()
            headers = {"access_token": settings.ASAAS_API_KEY}
            async with httpx.AsyncClient(timeout=15) as client:
                # Buscar pagamentos da assinatura
                payments_resp = await client.get(
                    f"{ASAAS_BASE_URL}/subscriptions/{subscription_id}/payments",
                    headers=headers,
                )
                if payments_resp.status_code == 200:
                    payments = payments_resp.json().get("data", [])
                    if payments:
                        payment_id = payments[0].get("id")
                        # Buscar QR code PIX
                        pix_resp = await client.get(
                            f"{ASAAS_BASE_URL}/payments/{payment_id}/pixQrCode",
                            headers=headers,
                        )
                        if pix_resp.status_code == 200:
                            pix_data = pix_resp.json()
                            response_data["pix_qr_code"] = pix_data.get("encodedImage", "")
                            response_data["pix_copia_cola"] = pix_data.get("payload", "")
        except Exception as e:
            logger.warning(f"Falha ao buscar QR PIX: {e}")

    # Se BOLETO, incluir URL do boleto
    if dados.metodo_pagamento == "BOLETO" and subscription_id:
        try:
            settings = get_settings()
            headers = {"access_token": settings.ASAAS_API_KEY}
            async with httpx.AsyncClient(timeout=15) as client:
                payments_resp = await client.get(
                    f"{ASAAS_BASE_URL}/subscriptions/{subscription_id}/payments",
                    headers=headers,
                )
                if payments_resp.status_code == 200:
                    payments = payments_resp.json().get("data", [])
                    if payments:
                        response_data["boleto_url"] = payments[0].get("bankSlipUrl", "")
        except Exception as e:
            logger.warning(f"Falha ao buscar boleto URL: {e}")

    logger.info(
        f"Checkout concluído: {dados.nome} | {plano['nome']} | "
        f"Asaas sub={subscription_id} | código={codigo}"
    )

    return response_data
