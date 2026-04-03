"""
Dashboard API — Endpoints de métricas e BI para o CEO.
Protegido por token (SECRET_KEY).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

router = APIRouter(prefix="/dashboard/api", tags=["Dashboard"])


# =============================================
# AUTENTICAÇÃO
# =============================================

def _verificar_token(
    token: Optional[str] = None,
    x_dashboard_token: Optional[str] = None,
) -> bool:
    """Verifica se o token fornecido bate com SECRET_KEY."""
    settings = get_settings()
    tk = token or x_dashboard_token
    if not tk or tk != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Token inválido ou ausente")
    return True


def _mascarar_telefone(numero: str) -> str:
    """Mascara número de telefone, mostrando apenas últimos 4 dígitos."""
    if not numero:
        return "****"
    if len(numero) <= 4:
        return numero
    return "*" * (len(numero) - 4) + numero[-4:]


# =============================================
# OVERVIEW
# =============================================

@router.get("/overview")
async def overview(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """Retorna métricas gerais do sistema."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    # Datas de referência
    agora = datetime.now(timezone.utc)
    inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    inicio_semana = (agora - timedelta(days=7)).isoformat()

    # --- Usuários por estado ---
    estados = sb.table("chat_estado").select("estado").execute()
    usuarios_ativos = sum(1 for u in estados.data if u.get("estado") == "ATIVO")
    usuarios_pendentes = sum(1 for u in estados.data if u.get("estado") == "PENDENTE_CODIGO")
    usuarios_bloqueados = sum(1 for u in estados.data if u.get("estado") == "BLOQUEADO")

    # --- Conversas ---
    conversas_total_resp = sb.table("conversas").select("id", count="exact").execute()
    conversas_total = conversas_total_resp.count or 0

    conversas_hoje_resp = (
        sb.table("conversas")
        .select("id", count="exact")
        .gte("criado_em", inicio_hoje)
        .execute()
    )
    conversas_hoje = conversas_hoje_resp.count or 0

    conversas_semana_resp = (
        sb.table("conversas")
        .select("id", count="exact")
        .gte("criado_em", inicio_semana)
        .execute()
    )
    conversas_semana = conversas_semana_resp.count or 0

    # --- Terapeutas ativos ---
    terapeutas_resp = (
        sb.table("terapeutas")
        .select("id", count="exact")
        .eq("ativo", True)
        .execute()
    )
    terapeutas_ativos = terapeutas_resp.count or 0

    # --- Códigos ---
    codigos_resp = sb.table("codigos_liberacao").select("ativo, descricao, status_assinatura").execute()
    codigos_ativos = sum(1 for c in (codigos_resp.data or []) if c.get("ativo"))
    codigos_expirados = sum(1 for c in (codigos_resp.data or []) if not c.get("ativo"))

    # --- Assinantes por plano ---
    por_plano_count: dict = {"Iniciante": 0, "Essencial": 0, "Profissional": 0, "Clínica": 0}
    assinantes_pagantes = 0
    for cod in (codigos_resp.data or []):
        if not cod.get("ativo"):
            continue
        plano_nome, _, _, _ = _parse_descricao(cod.get("descricao", ""))
        if plano_nome in por_plano_count:
            por_plano_count[plano_nome] += 1
        assinantes_pagantes += 1

    # Trial = usuários ATIVO no bot mas sem assinatura paga ativa
    usuarios_trial = max(0, usuarios_ativos - assinantes_pagantes)

    # Total de todos os usuários que já conversaram
    total_usuarios = usuarios_ativos + usuarios_pendentes + usuarios_bloqueados

    # --- Média de mensagens por dia (últimos 30 dias) ---
    inicio_30d = (agora - timedelta(days=30)).isoformat()
    conversas_30d_resp = (
        sb.table("conversas")
        .select("id", count="exact")
        .gte("criado_em", inicio_30d)
        .execute()
    )
    conversas_30d = conversas_30d_resp.count or 0
    mensagem_media_dia = round(conversas_30d / 30, 1) if conversas_30d else 0

    return {
        "total_usuarios": total_usuarios,
        "usuarios_ativos": usuarios_ativos,
        "usuarios_pendentes": usuarios_pendentes,
        "usuarios_bloqueados": usuarios_bloqueados,
        "usuarios_trial": usuarios_trial,
        "assinantes_pagantes": assinantes_pagantes,
        "por_plano": por_plano_count,
        "conversas_hoje": conversas_hoje,
        "conversas_semana": conversas_semana,
        "conversas_total": conversas_total,
        "terapeutas_ativos": terapeutas_ativos,
        "codigos_ativos": codigos_ativos,
        "codigos_expirados": codigos_expirados,
        "mensagem_media_dia": mensagem_media_dia,
    }


# =============================================
# CONVERSAS
# =============================================

@router.get("/conversas")
async def listar_conversas(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
    terapeuta_id: Optional[str] = Query(None),
    limite: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    busca: Optional[str] = Query(None),
):
    """Retorna lista de conversas recentes com detalhes."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    # Buscar conversas
    query = (
        sb.table("conversas")
        .select("id, terapeuta_id, paciente_numero, mensagem_paciente, resposta_agente, intencao, criado_em")
        .order("criado_em", desc=True)
        .range(offset, offset + limite - 1)
    )

    if terapeuta_id:
        query = query.eq("terapeuta_id", terapeuta_id)

    if busca:
        query = query.ilike("mensagem_paciente", f"%{busca}%")

    conversas_resp = query.execute()
    conversas = conversas_resp.data or []

    # Buscar terapeutas para nome
    terapeutas_resp = sb.table("terapeutas").select("id, nome").execute()
    terapeutas_map = {t["id"]: t["nome"] for t in (terapeutas_resp.data or [])}

    # Buscar chat_estado para nome do paciente
    estados_resp = sb.table("chat_estado").select("numero_telefone, nome_usuario, terapeuta_id").execute()
    # Chave: (terapeuta_id, numero_telefone) -> nome
    estados_map = {}
    for e in (estados_resp.data or []):
        key = (e.get("terapeuta_id"), e.get("numero_telefone"))
        estados_map[key] = e.get("nome_usuario", "")

    resultado = []
    for c in conversas:
        # Extrair modo da intenção (parte antes do "|")
        intencao = c.get("intencao", "") or ""
        modo = intencao.split("|")[0].strip() if "|" in intencao else intencao

        # Truncar resposta em 200 chars
        resposta = c.get("resposta_agente", "") or ""
        resposta_truncada = resposta[:200] + "..." if len(resposta) > 200 else resposta

        resultado.append({
            "id": c["id"],
            "terapeuta_nome": terapeutas_map.get(c.get("terapeuta_id"), "Desconhecido"),
            "paciente_numero": _mascarar_telefone(c.get("paciente_numero", "")),
            "paciente_nome": estados_map.get(
                (c.get("terapeuta_id"), c.get("paciente_numero")), ""
            ),
            "mensagem_paciente": c.get("mensagem_paciente", ""),
            "resposta_agente": resposta_truncada,
            "intencao": intencao,
            "modo": modo,
            "criado_em": c.get("criado_em"),
        })

    return {"conversas": resultado, "total": len(resultado)}


# =============================================
# TERAPEUTAS
# =============================================

@router.get("/terapeutas")
async def listar_terapeutas(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """Retorna métricas por terapeuta."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    agora = datetime.now(timezone.utc)
    inicio_semana = (agora - timedelta(days=7)).isoformat()

    # Buscar todos os terapeutas
    terapeutas_resp = sb.table("terapeutas").select("*").execute()
    terapeutas = terapeutas_resp.data or []

    # Buscar todas as conversas
    conversas_resp = sb.table("conversas").select("terapeuta_id, criado_em").execute()
    conversas = conversas_resp.data or []

    # Buscar estados de chat
    estados_resp = sb.table("chat_estado").select("terapeuta_id, estado").execute()
    estados = estados_resp.data or []

    # Buscar documentos
    docs_resp = sb.table("documentos").select("terapeuta_id, id").execute()
    docs = docs_resp.data or []

    resultado = []
    for t in terapeutas:
        tid = t["id"]

        # Conversas do terapeuta
        conversas_t = [c for c in conversas if c.get("terapeuta_id") == tid]
        conversas_semana_t = [
            c for c in conversas_t
            if c.get("criado_em", "") >= inicio_semana
        ]

        # Usuários do terapeuta
        estados_t = [e for e in estados if e.get("terapeuta_id") == tid]
        usuarios_ativos_t = sum(1 for e in estados_t if e.get("estado") == "ATIVO")

        # Documentos do terapeuta
        docs_t = [d for d in docs if d.get("terapeuta_id") == tid]

        # Última conversa
        datas_conversas = [c.get("criado_em") for c in conversas_t if c.get("criado_em")]
        ultima_conversa = max(datas_conversas) if datas_conversas else None

        resultado.append({
            "id": tid,
            "nome": t.get("nome", ""),
            "email": t.get("email", ""),
            "total_usuarios": len(estados_t),
            "usuarios_ativos": usuarios_ativos_t,
            "conversas_total": len(conversas_t),
            "conversas_semana": len(conversas_semana_t),
            "documentos_indexados": len(docs_t),
            "ultima_conversa": ultima_conversa,
        })

    return {"terapeutas": resultado}


# =============================================
# EVOLUÇÃO (conversas por dia)
# =============================================

@router.get("/evolucao")
async def evolucao(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
    dias: int = Query(30, ge=1, le=365),
):
    """Retorna conversas agrupadas por dia nos últimos N dias."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    agora = datetime.now(timezone.utc)
    inicio = (agora - timedelta(days=dias)).isoformat()

    conversas_resp = (
        sb.table("conversas")
        .select("criado_em")
        .gte("criado_em", inicio)
        .order("criado_em", desc=False)
        .execute()
    )
    conversas = conversas_resp.data or []

    # Agrupar por dia
    contagem_por_dia = {}
    for c in conversas:
        data_str = c.get("criado_em", "")
        if data_str:
            dia = data_str[:10]  # YYYY-MM-DD
            contagem_por_dia[dia] = contagem_por_dia.get(dia, 0) + 1

    # Preencher dias sem conversas com 0
    resultado = []
    for i in range(dias):
        dia = (agora - timedelta(days=dias - 1 - i)).strftime("%Y-%m-%d")
        resultado.append({
            "data": dia,
            "total": contagem_por_dia.get(dia, 0),
        })

    return {"evolucao": resultado}


# =============================================
# MODOS (distribuição de intenções)
# =============================================

@router.get("/modos")
async def modos(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """Retorna distribuição de modos de operação das intenções."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    conversas_resp = sb.table("conversas").select("intencao").execute()
    conversas = conversas_resp.data or []

    contagem = {}
    for c in conversas:
        intencao = c.get("intencao", "") or ""
        # Extrair modo (parte antes do "|")
        modo = intencao.split("|")[0].strip() if intencao else "SEM_MODO"
        if not modo:
            modo = "SEM_MODO"
        contagem[modo] = contagem.get(modo, 0) + 1

    resultado = [
        {"modo": modo, "total": total}
        for modo, total in sorted(contagem.items(), key=lambda x: -x[1])
    ]

    return {"modos": resultado}


# =============================================
# USUÁRIOS
# =============================================

@router.get("/usuarios")
async def listar_usuarios(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
    terapeuta_id: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
):
    """Retorna lista de usuários com detalhes."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    # Buscar estados de chat
    query = sb.table("chat_estado").select("*")
    if terapeuta_id:
        query = query.eq("terapeuta_id", terapeuta_id)
    if estado:
        query = query.eq("estado", estado)

    estados_resp = query.order("criado_em", desc=True).execute()
    estados = estados_resp.data or []

    # Buscar terapeutas para nomes
    terapeutas_resp = sb.table("terapeutas").select("id, nome").execute()
    terapeutas_map = {t["id"]: t["nome"] for t in (terapeutas_resp.data or [])}

    # Buscar códigos de liberação para data de expiração
    codigos_resp = sb.table("codigos_liberacao").select(
        "codigo, numero_ativo, data_expiracao, status_assinatura"
    ).execute()
    codigos_map = {}
    for cod in (codigos_resp.data or []):
        if cod.get("numero_ativo"):
            codigos_map[cod["numero_ativo"]] = {
                "data_expiracao": cod.get("data_expiracao"),
                "status_assinatura": cod.get("status_assinatura"),
            }

    # Buscar última mensagem de cada usuário
    conversas_resp = sb.table("conversas").select(
        "paciente_numero, terapeuta_id, criado_em"
    ).order("criado_em", desc=True).execute()

    # Mapear (terapeuta_id, numero) -> ultima_mensagem
    ultimas = {}
    for c in (conversas_resp.data or []):
        key = (c.get("terapeuta_id"), c.get("paciente_numero"))
        if key not in ultimas:
            ultimas[key] = c.get("criado_em")

    resultado = []
    for e in estados:
        numero = e.get("numero_telefone", "")
        codigo_info = codigos_map.get(numero, {})

        resultado.append({
            "numero_telefone": _mascarar_telefone(numero),
            "nome_usuario": e.get("nome_usuario", ""),
            "estado": e.get("estado", ""),
            "terapeuta_nome": terapeutas_map.get(e.get("terapeuta_id"), "Desconhecido"),
            "terapeuta_id": e.get("terapeuta_id"),
            "codigo_usado": e.get("codigo_usado", ""),
            "violacoes_conteudo": e.get("violacoes_conteudo", 0),
            "motivo_bloqueio": e.get("motivo_bloqueio", ""),
            "data_expiracao_assinatura": codigo_info.get("data_expiracao"),
            "status_assinatura": codigo_info.get("status_assinatura"),
            "criado_em": e.get("criado_em"),
            "ultima_mensagem": ultimas.get(
                (e.get("terapeuta_id"), numero), None
            ),
        })

    return {"usuarios": resultado}


# =============================================
# ASSINATURAS
# =============================================

@router.get("/assinaturas")
async def listar_assinaturas(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """Retorna lista de códigos/assinaturas com detalhes."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    codigos_resp = sb.table("codigos_liberacao").select("*").order("criado_em", desc=True).execute()
    codigos = codigos_resp.data or []

    # Buscar terapeutas
    terapeutas_resp = sb.table("terapeutas").select("id, nome").execute()
    terapeutas_map = {t["id"]: t["nome"] for t in (terapeutas_resp.data or [])}

    # Buscar nomes de usuários do chat_estado
    estados_resp = sb.table("chat_estado").select("numero_telefone, nome_usuario").execute()
    nomes_map = {e.get("numero_telefone"): e.get("nome_usuario", "") for e in (estados_resp.data or [])}

    resultado = []
    for c in codigos:
        codigo_raw = c.get("codigo", "")
        codigo_mascarado = codigo_raw[:4] + "***" if len(codigo_raw) >= 4 else codigo_raw

        numero_ativo = c.get("numero_ativo", "")
        nome_usuario = nomes_map.get(numero_ativo, "") if numero_ativo else ""

        descricao = c.get("descricao", "")
        plano_nome, plano_valor, email_cliente, nome_cliente = _parse_descricao(descricao)

        resultado.append({
            "id": c.get("id"),
            "codigo": codigo_mascarado,
            "descricao": descricao,
            "nome_cliente": nome_cliente or nome_usuario,
            "email_cliente": email_cliente,
            "plano": plano_nome,
            "valor_mensal": plano_valor,
            "numero_ativo": _mascarar_telefone(numero_ativo) if numero_ativo else "",
            "nome_usuario": nome_usuario,
            "status_assinatura": c.get("status_assinatura", "disponivel"),
            "data_expiracao": c.get("data_expiracao"),
            "meses_contratados": c.get("meses_contratados"),
            "terapeuta_nome": terapeutas_map.get(c.get("terapeuta_id"), "Desconhecido"),
            "terapeuta_id": c.get("terapeuta_id"),
            "asaas_subscription_id": c.get("asaas_subscription_id", ""),
            "asaas_customer_id": c.get("asaas_customer_id", ""),
            "reutilizavel": c.get("reutilizavel", False),
            "ativo": c.get("ativo", False),
            "usado": c.get("usado", False),
            "usado_em": c.get("usado_em"),
            "criado_em": c.get("criado_em"),
        })

    return {"assinaturas": resultado}


# =============================================
# FINANCEIRO / MRR
# =============================================

def _parse_descricao(descricao: str) -> tuple:
    """Extrai nome, plano, valor, email da descricao do codigo."""
    nome_cliente = ""
    email_cliente = ""
    plano_nome = "Desconhecido"
    plano_valor = 0.0

    if not descricao:
        return plano_nome, plano_valor, email_cliente, nome_cliente

    # Formato: "Nome — Plano (email)"
    try:
        if " — " in descricao:
            partes = descricao.split(" — ", 1)
            nome_cliente = partes[0].strip()
            resto = partes[1] if len(partes) > 1 else ""
            if " (" in resto:
                plano_raw = resto.split(" (")[0].strip()
                email_raw = resto.split("(")[1].rstrip(")")
                email_cliente = email_raw.strip()
            else:
                plano_raw = resto.strip()
        else:
            plano_raw = descricao
    except Exception:
        plano_raw = descricao

    d = plano_raw.lower()
    if "clínica" in d or "clinica" in d:
        plano_nome, plano_valor = "Clínica", 697.0
    elif "profissional" in d:
        plano_nome, plano_valor = "Profissional", 297.0
    elif "essencial" in d:
        plano_nome, plano_valor = "Essencial", 197.0
    elif "iniciante" in d:
        plano_nome, plano_valor = "Iniciante", 97.0

    return plano_nome, plano_valor, email_cliente, nome_cliente


@router.get("/financeiro")
async def financeiro(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """MRR, ARR, breakdown por plano, crescimento mensal."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    inicio_semana = (agora - timedelta(days=7)).isoformat()

    codigos_resp = sb.table("codigos_liberacao").select("*").order("criado_em", desc=False).execute()
    codigos = codigos_resp.data or []

    mrr = 0.0
    por_plano: dict = {}
    novos_mes = 0
    novos_semana = 0
    total_ativos = 0
    total_trial = 0
    total_cancelados = 0
    total_pendentes = 0
    evolucao_mensal: dict = {}

    for c in codigos:
        plano_nome, preco, _, _ = _parse_descricao(c.get("descricao", ""))
        status = c.get("status_assinatura", "disponivel")
        criado = c.get("criado_em", "")

        if status == "ativo":
            total_ativos += 1
            if preco > 0:
                mrr += preco
                por_plano[plano_nome] = por_plano.get(plano_nome, {"count": 0, "valor": 0.0})
                por_plano[plano_nome]["count"] += 1
                por_plano[plano_nome]["valor"] += preco
        elif status == "disponivel":
            total_pendentes += 1
        elif status in ("cancelado", "suspenso_pagamento"):
            total_cancelados += 1

        if criado >= inicio_mes:
            novos_mes += 1
        if criado >= inicio_semana:
            novos_semana += 1

        if criado:
            mes = criado[:7]
            if mes not in evolucao_mensal:
                evolucao_mensal[mes] = {"novos": 0, "receita": 0.0}
            evolucao_mensal[mes]["novos"] += 1
            if status == "ativo" and preco > 0:
                evolucao_mensal[mes]["receita"] += preco

    return {
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "total_ativos": total_ativos,
        "total_pendentes": total_pendentes,
        "total_cancelados": total_cancelados,
        "total_codigos": len(codigos),
        "novos_este_mes": novos_mes,
        "novos_esta_semana": novos_semana,
        "por_plano": [
            {"plano": k, "count": v["count"], "valor": v["valor"]}
            for k, v in sorted(por_plano.items(), key=lambda x: -x[1]["valor"])
        ],
        "evolucao": [
            {"mes": k, **v}
            for k, v in sorted(evolucao_mensal.items())
        ][-12:],
    }


# =============================================
# CLIENTES (todos os usuários que conversaram)
# =============================================

@router.get("/clientes")
async def listar_clientes(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
):
    """
    Retorna TODOS os usuários que já conversaram (chat_estado),
    enriquecidos com total de mensagens, média mensal e dados de assinatura.
    """
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    # 1. Todos os estados de chat (um por usuário por terapeuta)
    estados_resp = sb.table("chat_estado").select("*").order("criado_em", desc=True).execute()
    estados = estados_resp.data or []

    # 2. Terapeutas para nome
    teraps_resp = sb.table("terapeutas").select("id, nome, email").execute()
    teraps_map = {t["id"]: t for t in (teraps_resp.data or [])}

    # 3. Todas as conversas — para contar mensagens por (terapeuta, numero)
    convs_resp = sb.table("conversas").select("paciente_numero, terapeuta_id, criado_em").execute()
    convs = convs_resp.data or []

    # Indexar: (terapeuta_id, numero) -> lista de datas
    convs_index: dict = {}
    for c in convs:
        key = (c.get("terapeuta_id"), c.get("paciente_numero"))
        if key not in convs_index:
            convs_index[key] = []
        convs_index[key].append(c.get("criado_em", ""))

    # 4. Codigos de liberacao — para dados de assinatura por numero
    codigos_resp = sb.table("codigos_liberacao").select(
        "numero_ativo, status_assinatura, data_expiracao, descricao, meses_contratados, criado_em"
    ).execute()
    # Chave: numero_ativo -> código mais recente
    codigos_por_numero: dict = {}
    for cod in (codigos_resp.data or []):
        num = cod.get("numero_ativo")
        if num:
            existing = codigos_por_numero.get(num)
            if not existing or (cod.get("criado_em", "") > existing.get("criado_em", "")):
                codigos_por_numero[num] = cod

    resultado = []
    for e in estados:
        numero = e.get("numero_telefone", "")
        tid = e.get("terapeuta_id")
        key = (tid, numero)

        datas_msgs = convs_index.get(key, [])
        total_msgs = len(datas_msgs)
        msgs_mes = sum(1 for d in datas_msgs if d >= inicio_mes)

        # Média mensal: total / meses desde criação (mín 1)
        criado = e.get("criado_em") or agora.isoformat()
        dias_ativo = max(1, (agora - datetime.fromisoformat(criado.replace("Z", "+00:00"))).days)
        media_mes = round(total_msgs / max(1, dias_ativo / 30), 1)

        # Assinatura
        cod = codigos_por_numero.get(numero, {})
        plano_nome, plano_valor, email_cliente, _ = _parse_descricao(cod.get("descricao", ""))

        terapeuta = teraps_map.get(tid, {})

        resultado.append({
            "numero_telefone": _mascarar_telefone(numero),
            "numero_raw": numero,
            "nome": e.get("nome_usuario") or "",
            "email": email_cliente,
            "estado": e.get("estado", ""),
            "terapeuta_nome": terapeuta.get("nome", "Desconhecido"),
            "terapeuta_id": tid,
            "total_msgs": total_msgs,
            "msgs_este_mes": msgs_mes,
            "media_msgs_mes": media_mes,
            "plano": plano_nome if cod else "—",
            "valor_mensal": plano_valor if cod else 0,
            "status_assinatura": cod.get("status_assinatura", "sem_assinatura") if cod else "sem_assinatura",
            "data_expiracao": cod.get("data_expiracao"),
            "criado_em": e.get("criado_em"),
            "ultima_msg": max(datas_msgs) if datas_msgs else None,
        })

    # Ordenar por total de mensagens desc
    resultado.sort(key=lambda x: x["total_msgs"], reverse=True)
    return {"clientes": resultado, "total": len(resultado)}


# =============================================
# DETALHE DE CLIENTE
# =============================================

@router.get("/cliente-detalhe")
async def cliente_detalhe(
    token: Optional[str] = Query(None),
    x_dashboard_token: Optional[str] = Header(None, alias="X-Dashboard-Token"),
    terapeuta_id: str = Query(...),
    numero: str = Query(...),
):
    """Retorna perfil completo + histórico de conversas de um usuário."""
    _verificar_token(token, x_dashboard_token)
    sb = get_supabase()

    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Perfil do usuário
    estado_resp = (
        sb.table("chat_estado")
        .select("*")
        .eq("terapeuta_id", terapeuta_id)
        .eq("numero_telefone", numero)
        .limit(1)
        .execute()
    )
    estado = (estado_resp.data or [{}])[0]

    # Terapeuta
    terapeuta_resp = (
        sb.table("terapeutas")
        .select("id, nome, email, whatsapp_numero")
        .eq("id", terapeuta_id)
        .limit(1)
        .execute()
    )
    terapeuta = (terapeuta_resp.data or [{}])[0]

    # Histórico de conversas (última 200)
    convs_resp = (
        sb.table("conversas")
        .select("id, mensagem_paciente, resposta_agente, intencao, criado_em")
        .eq("terapeuta_id", terapeuta_id)
        .eq("paciente_numero", numero)
        .order("criado_em", desc=False)
        .limit(200)
        .execute()
    )
    conversas = convs_resp.data or []

    # Código de assinatura
    codigo_resp = (
        sb.table("codigos_liberacao")
        .select("*")
        .eq("numero_ativo", numero)
        .order("criado_em", desc=True)
        .limit(1)
        .execute()
    )
    codigo = (codigo_resp.data or [{}])[0]
    plano_nome, plano_valor, email_cliente, _ = _parse_descricao(codigo.get("descricao", ""))

    msgs_este_mes = sum(1 for c in conversas if (c.get("criado_em") or "") >= inicio_mes)
    criado = estado.get("criado_em") or agora.isoformat()
    dias_ativo = max(1, (agora - datetime.fromisoformat(criado.replace("Z", "+00:00"))).days)
    media_mes = round(len(conversas) / max(1, dias_ativo / 30), 1)

    return {
        "nome": estado.get("nome_usuario") or "",
        "numero": numero,
        "estado": estado.get("estado", ""),
        "criado_em": estado.get("criado_em"),
        "codigo_acesso": estado.get("codigo_usado", ""),
        "violacoes": estado.get("violacoes_conteudo", 0),
        "terapeuta": {
            "id": terapeuta.get("id"),
            "nome": terapeuta.get("nome", "Desconhecido"),
            "email": terapeuta.get("email", ""),
            "whatsapp": terapeuta.get("whatsapp_numero", ""),
        },
        "plano": plano_nome if codigo else "—",
        "valor_mensal": plano_valor if codigo else 0,
        "status_assinatura": codigo.get("status_assinatura", "sem_assinatura") if codigo else "sem_assinatura",
        "data_expiracao": codigo.get("data_expiracao"),
        "email": email_cliente,
        "total_msgs": len(conversas),
        "msgs_este_mes": msgs_este_mes,
        "media_msgs_mes": media_mes,
        "conversas": [
            {
                "id": c.get("id"),
                "mensagem_paciente": c.get("mensagem_paciente", ""),
                "resposta_agente": c.get("resposta_agente", ""),
                "intencao": c.get("intencao", ""),
                "criado_em": c.get("criado_em"),
            }
            for c in conversas
        ],
    }
