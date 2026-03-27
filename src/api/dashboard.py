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
    codigos_resp = sb.table("codigos_liberacao").select("ativo").execute()
    codigos_ativos = sum(1 for c in codigos_resp.data if c.get("ativo"))
    codigos_expirados = sum(1 for c in codigos_resp.data if not c.get("ativo"))

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
        "usuarios_ativos": usuarios_ativos,
        "usuarios_pendentes": usuarios_pendentes,
        "usuarios_bloqueados": usuarios_bloqueados,
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

        resultado.append({
            "id": c.get("id"),
            "codigo": codigo_mascarado,
            "descricao": c.get("descricao", ""),
            "numero_ativo": _mascarar_telefone(numero_ativo) if numero_ativo else "",
            "nome_usuario": nome_usuario,
            "status_assinatura": c.get("status_assinatura", "disponivel"),
            "data_expiracao": c.get("data_expiracao"),
            "meses_contratados": c.get("meses_contratados"),
            "terapeuta_nome": terapeutas_map.get(c.get("terapeuta_id"), "Desconhecido"),
            "terapeuta_id": c.get("terapeuta_id"),
            "reutilizavel": c.get("reutilizavel", False),
            "ativo": c.get("ativo", False),
            "criado_em": c.get("criado_em"),
        })

    return {"assinaturas": resultado}
