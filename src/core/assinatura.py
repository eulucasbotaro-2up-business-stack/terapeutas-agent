"""
Gerenciamento de assinaturas — sistema de acesso por tempo (1-12 meses).

Integrado com Asaas (gateway de pagamento) via webhooks.
Cada assinatura é vinculada a um código de liberação.

Fluxo:
  1. Terapeuta/admin cria código com prazo (criar_codigo_assinatura)
  2. Código é enviado ao cliente após pagamento confirmado
  3. Cliente ativa com o código → prazo começa a contar
  4. Asaas webhook notifica renovação/falha/cancelamento
  5. Ao expirar: bloquear chat_estado vinculado ao código
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def criar_codigo_assinatura(
    terapeuta_id: str,
    codigo: str,
    meses: int,
    descricao: str = "",
    asaas_subscription_id: str = "",
    asaas_customer_id: str = "",
) -> dict:
    """
    Cria um código de liberação vinculado a uma assinatura paga.

    O código NÃO tem data_expiracao ainda — ela é definida quando o usuário
    ATIVA o código pela primeira vez (a partir daquele momento contam os meses).

    Args:
        terapeuta_id: UUID do terapeuta.
        codigo: Código único que será enviado ao cliente.
        meses: Duração da assinatura em meses (1-12).
        descricao: Descrição interna (ex: "Cliente Ana Lima - Plano 3 meses").
        asaas_subscription_id: ID da assinatura no Asaas (para webhook).
        asaas_customer_id: ID do cliente no Asaas.

    Returns:
        Dicionário com os dados do código criado.

    Raises:
        ValueError: Se meses não estiver entre 1 e 12.
    """
    if not 1 <= meses <= 12:
        raise ValueError(f"meses deve ser entre 1 e 12, recebido: {meses}")

    supabase = get_supabase()

    dados = {
        "terapeuta_id": terapeuta_id,
        "codigo": codigo.strip().lower(),
        "descricao": descricao,
        "reutilizavel": False,  # assinaturas são sempre 1 código = 1 usuário
        "meses_contratados": meses,
        "status_assinatura": "disponivel",
        "ativo": True,
    }

    if asaas_subscription_id:
        dados["asaas_subscription_id"] = asaas_subscription_id
    if asaas_customer_id:
        dados["asaas_customer_id"] = asaas_customer_id

    resultado = (
        supabase.table("codigos_liberacao")
        .insert(dados)
        .execute()
    )

    logger.info(
        f"Código de assinatura criado: '{codigo}' | "
        f"{meses} meses | terapeuta={terapeuta_id}"
    )
    return resultado.data[0] if resultado.data else {}


def ativar_acesso_com_codigo(
    terapeuta_id: str,
    codigo: str,
    numero_telefone: str,
) -> Optional[datetime]:
    """
    Ativa o acesso de um código quando o usuário o usa pela primeira vez.
    Define a data_expiracao com base nos meses_contratados a partir de AGORA.

    Chamado internamente por validar_codigo em estado.py após validação bem-sucedida.

    Args:
        terapeuta_id: UUID do terapeuta.
        codigo: Código normalizado (lower).
        numero_telefone: Número que ativou o código.

    Returns:
        data_expiracao calculada, ou None se falhar.
    """
    supabase = get_supabase()

    # Buscar o código para saber quantos meses
    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, meses_contratados, data_expiracao")
        .eq("terapeuta_id", terapeuta_id)
        .eq("codigo", codigo.strip().lower())
        .limit(1)
        .execute()
    )

    if not resultado.data:
        return None

    row = resultado.data[0]
    meses = row.get("meses_contratados") or 1

    # Se já tem data_expiracao, não sobrescrever (renovação não vai aqui)
    if row.get("data_expiracao"):
        logger.info(f"Código '{codigo}' já tem data_expiracao definida — mantendo")
        return datetime.fromisoformat(row["data_expiracao"])

    # Calcular expiração
    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(days=30 * meses)

    supabase.table("codigos_liberacao").update({
        "numero_ativo": numero_telefone,
        "status_assinatura": "ativo",
        "data_expiracao": expiracao.isoformat(),
        "usado": True,
        "usado_por": numero_telefone,
        "usado_em": agora.isoformat(),
    }).eq("id", row["id"]).execute()

    logger.info(
        f"Código '{codigo}' ativado por {numero_telefone} — "
        f"expira em {expiracao.strftime('%d/%m/%Y')}"
    )
    return expiracao


def renovar_assinatura(
    asaas_subscription_id: str,
    meses_adicionais: int = 1,
) -> bool:
    """
    Renova (estende) a data_expiracao de uma assinatura após pagamento confirmado.

    Chamado pelo webhook Asaas no evento PAYMENT_RECEIVED.

    Args:
        asaas_subscription_id: ID da assinatura no Asaas.
        meses_adicionais: Meses a adicionar (geralmente 1 para planos mensais).

    Returns:
        True se renovada com sucesso.
    """
    supabase = get_supabase()

    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, data_expiracao, status_assinatura, numero_ativo, terapeuta_id, codigo")
        .eq("asaas_subscription_id", asaas_subscription_id)
        .limit(1)
        .execute()
    )

    if not resultado.data:
        logger.warning(f"Assinatura não encontrada: {asaas_subscription_id}")
        return False

    row = resultado.data[0]
    agora = datetime.now(timezone.utc)

    # Calcular nova expiração: a partir da expiração atual (ou agora se já expirou)
    if row.get("data_expiracao"):
        expiracao_atual = datetime.fromisoformat(row["data_expiracao"])
        base = max(expiracao_atual, agora)  # nunca regredir
    else:
        base = agora

    nova_expiracao = base + timedelta(days=30 * meses_adicionais)

    supabase.table("codigos_liberacao").update({
        "data_expiracao": nova_expiracao.isoformat(),
        "status_assinatura": "ativo",
        "asaas_payment_status": "RECEIVED",
        "ativo": True,
    }).eq("id", row["id"]).execute()

    # Se o chat estava bloqueado por pagamento, reativar
    if row.get("numero_ativo") and row.get("terapeuta_id"):
        _reativar_chat(
            terapeuta_id=row["terapeuta_id"],
            numero_telefone=row["numero_ativo"],
            codigo=row["codigo"],
        )

    logger.info(
        f"Assinatura {asaas_subscription_id} renovada — "
        f"nova expiração: {nova_expiracao.strftime('%d/%m/%Y')}"
    )
    return True


def suspender_por_falha_pagamento(
    asaas_subscription_id: str,
    payment_status: str = "OVERDUE",
) -> bool:
    """
    Suspende o acesso quando o pagamento falha ou atrasa.

    Chamado pelo webhook Asaas nos eventos PAYMENT_OVERDUE ou PAYMENT_DELETED.
    Bloqueia o chat_estado vinculado ao código.

    Args:
        asaas_subscription_id: ID da assinatura no Asaas.
        payment_status: Status do pagamento vindo do Asaas.

    Returns:
        True se suspenso com sucesso.
    """
    supabase = get_supabase()

    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, numero_ativo, terapeuta_id, codigo")
        .eq("asaas_subscription_id", asaas_subscription_id)
        .limit(1)
        .execute()
    )

    if not resultado.data:
        logger.warning(f"Assinatura não encontrada para suspender: {asaas_subscription_id}")
        return False

    row = resultado.data[0]

    supabase.table("codigos_liberacao").update({
        "status_assinatura": "suspenso_pagamento",
        "asaas_payment_status": payment_status,
    }).eq("id", row["id"]).execute()

    # Bloquear o chat do usuário
    if row.get("numero_ativo") and row.get("terapeuta_id"):
        bloquear_chat_por_codigo(
            terapeuta_id=row["terapeuta_id"],
            numero_telefone=row["numero_ativo"],
            motivo="PAGAMENTO_FALHOU",
        )

    logger.warning(
        f"Assinatura {asaas_subscription_id} suspensa por "
        f"falha de pagamento ({payment_status})"
    )
    return True


def cancelar_assinatura(asaas_subscription_id: str) -> bool:
    """
    Cancela uma assinatura definitivamente (usuário cancelou ou admin cancelou).

    Chamado pelo webhook Asaas no evento SUBSCRIPTION_DELETED.
    Bloqueia o chat e invalida o código.
    """
    supabase = get_supabase()

    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, numero_ativo, terapeuta_id, codigo")
        .eq("asaas_subscription_id", asaas_subscription_id)
        .limit(1)
        .execute()
    )

    if not resultado.data:
        return False

    row = resultado.data[0]

    supabase.table("codigos_liberacao").update({
        "status_assinatura": "cancelado",
        "ativo": False,
        "asaas_payment_status": "CANCELLED",
    }).eq("id", row["id"]).execute()

    if row.get("numero_ativo") and row.get("terapeuta_id"):
        bloquear_chat_por_codigo(
            terapeuta_id=row["terapeuta_id"],
            numero_telefone=row["numero_ativo"],
            motivo="CANCELADO",
        )

    logger.info(f"Assinatura {asaas_subscription_id} cancelada")
    return True


def bloquear_chat_por_codigo(
    terapeuta_id: str,
    numero_telefone: str,
    motivo: str,
) -> None:
    """
    Bloqueia o chat_estado de um usuário com o motivo específico.

    Args:
        terapeuta_id: UUID do terapeuta.
        numero_telefone: Número do WhatsApp do usuário.
        motivo: 'PAGAMENTO_FALHOU' | 'ASSINATURA_EXPIRADA' | 'CANCELADO' | 'ADMIN'
    """
    supabase = get_supabase()

    from datetime import datetime, timezone
    supabase.table("chat_estado").update({
        "estado": "BLOQUEADO",
        "motivo_bloqueio": motivo,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()

    logger.info(
        f"Chat bloqueado: {numero_telefone} | motivo={motivo} | "
        f"terapeuta={terapeuta_id}"
    )


def _reativar_chat(terapeuta_id: str, numero_telefone: str, codigo: str) -> None:
    """Reativa um chat bloqueado por pagamento após renovação."""
    supabase = get_supabase()

    from datetime import datetime, timezone
    # Só reativa se o motivo foi pagamento (não por violação)
    result = (
        supabase.table("chat_estado")
        .select("motivo_bloqueio")
        .eq("terapeuta_id", terapeuta_id)
        .eq("numero_telefone", numero_telefone)
        .limit(1)
        .execute()
    )

    if result.data:
        motivo = result.data[0].get("motivo_bloqueio", "")
        if motivo in ("PAGAMENTO_FALHOU", "ASSINATURA_EXPIRADA"):
            supabase.table("chat_estado").update({
                "estado": "ATIVO",
                "motivo_bloqueio": None,
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
            }).eq("terapeuta_id", terapeuta_id).eq(
                "numero_telefone", numero_telefone
            ).execute()
            logger.info(f"Chat reativado após renovação: {numero_telefone}")


def verificar_e_bloquear_expirados(terapeuta_id: str) -> int:
    """
    Verifica todos os códigos expirados de um terapeuta e bloqueia os chats.

    Deve ser executado via cron job (recomendado: diariamente às 3h).

    Args:
        terapeuta_id: UUID do terapeuta a verificar.

    Returns:
        Número de assinaturas bloqueadas.
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    # Buscar códigos ativos com data_expiracao no passado
    expirados = (
        supabase.table("codigos_liberacao")
        .select("id, codigo, numero_ativo")
        .eq("terapeuta_id", terapeuta_id)
        .eq("status_assinatura", "ativo")
        .lt("data_expiracao", agora)
        .execute()
    )

    bloqueados = 0
    for row in (expirados.data or []):
        # Marcar código como expirado
        supabase.table("codigos_liberacao").update({
            "status_assinatura": "expirado",
        }).eq("id", row["id"]).execute()

        # Bloquear o chat vinculado
        if row.get("numero_ativo"):
            bloquear_chat_por_codigo(
                terapeuta_id=terapeuta_id,
                numero_telefone=row["numero_ativo"],
                motivo="ASSINATURA_EXPIRADA",
            )
            bloqueados += 1

    if bloqueados:
        logger.info(
            f"Verificação de expirados: {bloqueados} assinatura(s) bloqueada(s) "
            f"para terapeuta={terapeuta_id}"
        )

    return bloqueados
