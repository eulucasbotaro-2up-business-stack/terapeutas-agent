"""
Portal do Terapeuta — API completa para o ecossistema web de gestão clínica.

Endpoints:
  POST /portal/api/auth/login              → autenticação JWT
  GET  /portal/api/auth/me                 → perfil do terapeuta logado
  POST /portal/api/admin/setup-senha       → [admin] cria senha inicial

  GET/POST/PUT/DELETE /portal/api/pacientes
  POST /portal/api/pacientes/importar-whatsapp

  GET  /portal/api/prontuario/{paciente_id}
  GET  /portal/api/prontuario/{paciente_id}/timeline
  GET  /portal/api/prontuario/{paciente_id}/conversas

  GET/POST/PUT/DELETE /portal/api/diagnosticos
  POST /portal/api/diagnosticos/auto-extrair/{paciente_id}

  GET/POST/PUT/DELETE /portal/api/anotacoes/{paciente_id}
  PUT/DELETE          /portal/api/anotacoes/item/{id}

  GET  /portal/api/acompanhamentos
  GET  /portal/api/acompanhamentos/agenda
  POST /portal/api/acompanhamentos
  PUT  /portal/api/acompanhamentos/{id}

  GET  /portal/api/mapas
  GET  /portal/api/mapas/{id}

  GET  /portal/api/relatorios/visao-geral
  GET  /portal/api/relatorios/paciente/{id}
  GET  /portal/api/relatorios/diagnosticos
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal/api", tags=["Portal"])

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 24


# ─── Helpers de Auth ─────────────────────────────────────────────────────────

def _gerar_token(terapeuta_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": terapeuta_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS),
        "tipo": "portal",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_JWT_ALGORITHM)


def _decodificar_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")


def _get_terapeuta_id(authorization: str = Header(...)) -> str:
    """Dependency: extrai terapeuta_id do JWT Bearer."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization inválido.")
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decodificar_token(token)
    return payload["sub"]


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _verificar_senha(senha: str, hash_: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash_.encode())


def _verificar_admin(x_dashboard_token: str = Header(default="")) -> None:
    settings = get_settings()
    if x_dashboard_token != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Token admin inválido.")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    senha: str


class SetupSenhaIn(BaseModel):
    email: str
    senha: str


class PacienteIn(BaseModel):
    numero_telefone: str
    nome: str
    email: Optional[str] = None
    data_nascimento: Optional[str] = None
    hora_nascimento: Optional[str] = None
    cidade_nascimento: Optional[str] = None
    genero: Optional[str] = None
    tags: Optional[list[str]] = []
    notas_gerais: Optional[str] = None
    data_inicio_acompanhamento: Optional[str] = None
    status: Optional[str] = "ativo"


class PacienteUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    data_nascimento: Optional[str] = None
    hora_nascimento: Optional[str] = None
    cidade_nascimento: Optional[str] = None
    genero: Optional[str] = None
    tags: Optional[list[str]] = None
    notas_gerais: Optional[str] = None
    status: Optional[str] = None
    data_inicio_acompanhamento: Optional[str] = None


class DiagnosticoIn(BaseModel):
    paciente_id: str
    elemento_dominante: Optional[str] = None
    elemento_carente: Optional[str] = None
    elementos_detalhes: Optional[dict] = {}
    dna_comprometido: Optional[list[str]] = []
    dna_descricao: Optional[str] = None
    serpentes_ativas: Optional[list[str]] = []
    serpentes_descricao: Optional[str] = None
    setenio_atual: Optional[int] = None
    setenio_descricao: Optional[str] = None
    florais_prescritos: Optional[list[str]] = []
    protocolo_texto: Optional[str] = None
    sessao_data: Optional[str] = None
    status: Optional[str] = "rascunho"


class DiagnosticoUpdate(BaseModel):
    elemento_dominante: Optional[str] = None
    elemento_carente: Optional[str] = None
    elementos_detalhes: Optional[dict] = None
    dna_comprometido: Optional[list[str]] = None
    dna_descricao: Optional[str] = None
    serpentes_ativas: Optional[list[str]] = None
    serpentes_descricao: Optional[str] = None
    setenio_atual: Optional[int] = None
    setenio_descricao: Optional[str] = None
    florais_prescritos: Optional[list[str]] = None
    protocolo_texto: Optional[str] = None
    sessao_data: Optional[str] = None
    status: Optional[str] = None


class AnotacaoIn(BaseModel):
    paciente_id: str
    tipo: Optional[str] = "sessao"
    titulo: Optional[str] = None
    conteudo: str
    data_anotacao: Optional[str] = None
    proxima_sessao: Optional[str] = None
    privada: Optional[bool] = False


class AnotacaoUpdate(BaseModel):
    tipo: Optional[str] = None
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    data_anotacao: Optional[str] = None
    proxima_sessao: Optional[str] = None
    privada: Optional[bool] = None


class AcompanhamentoIn(BaseModel):
    paciente_id: str
    tipo: Optional[str] = "retorno"
    descricao: str
    data_prevista: Optional[str] = None
    prioridade: Optional[int] = 2


class AcompanhamentoUpdate(BaseModel):
    tipo: Optional[str] = None
    descricao: Optional[str] = None
    data_prevista: Optional[str] = None
    data_realizado: Optional[str] = None
    status: Optional[str] = None
    prioridade: Optional[int] = None


# ─── AUTH ────────────────────────────────────────────────────────────────────

@router.post("/auth/login", summary="Login do terapeuta no portal")
async def login(body: LoginIn):
    sb = get_supabase()

    # 1. Buscar terapeuta pelo email
    res = sb.table("terapeutas").select("id, nome, email, especialidade").eq("email", body.email).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")
    terapeuta = res.data[0]
    terapeuta_id = terapeuta["id"]

    # 2. Buscar auth record
    auth_res = sb.table("portal_auth").select("*").eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not auth_res.data:
        raise HTTPException(status_code=401, detail="Acesso ao portal não configurado. Contate o administrador.")
    auth = auth_res.data[0]

    # 3. Verificar bloqueio por tentativas
    if auth.get("bloqueado_ate"):
        bloqueado_ate = datetime.fromisoformat(auth["bloqueado_ate"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < bloqueado_ate:
            raise HTTPException(status_code=429, detail="Conta temporariamente bloqueada. Aguarde 15 minutos.")

    # 4. Verificar senha
    if not _verificar_senha(body.senha, auth["senha_hash"]):
        novas_tentativas = auth.get("tentativas_falhas", 0) + 1
        update_data: dict = {"tentativas_falhas": novas_tentativas}
        if novas_tentativas >= 5:
            update_data["bloqueado_ate"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        sb.table("portal_auth").update(update_data).eq("terapeuta_id", terapeuta_id).execute()
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")

    # 5. Verificar se é primeiro login → auto-importar pacientes
    primeiro_login = auth.get("primeiro_login", False)

    # 6. Atualizar login info
    sb.table("portal_auth").update({
        "ultimo_login": datetime.now(timezone.utc).isoformat(),
        "tentativas_falhas": 0,
        "bloqueado_ate": None,
        "primeiro_login": False,
    }).eq("terapeuta_id", terapeuta_id).execute()

    # 7. Auto-importar pacientes no primeiro login
    if primeiro_login:
        try:
            await _importar_pacientes_whatsapp(terapeuta_id)
        except Exception as e:
            logger.warning(f"[PORTAL] Auto-import falhou no primeiro login: {e}")

    token = _gerar_token(terapeuta_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": _JWT_EXPIRE_HOURS * 3600,
        "terapeuta": terapeuta,
        "primeiro_login": primeiro_login,
    }


@router.get("/auth/me", summary="Perfil do terapeuta logado")
async def me(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    res = sb.table("terapeutas").select("id, nome, email, especialidade, nome_agente, tom_de_voz").eq("id", terapeuta_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Terapeuta não encontrado.")

    # Stats rápidos
    total_pacientes = sb.table("pacientes").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("status", "ativo").execute()
    total_conversas = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).execute()

    return {
        **res.data[0],
        "stats": {
            "pacientes_ativos": total_pacientes.count or 0,
            "total_conversas": total_conversas.count or 0,
        }
    }


@router.post("/admin/setup-senha", summary="[Admin] Cria ou redefine senha de um terapeuta")
async def setup_senha(body: SetupSenhaIn, x_dashboard_token: str = Header(default="")):
    _verificar_admin(x_dashboard_token)
    sb = get_supabase()

    res = sb.table("terapeutas").select("id").eq("email", body.email).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Terapeuta não encontrado.")
    terapeuta_id = res.data[0]["id"]

    hash_ = _hash_senha(body.senha)
    existente = sb.table("portal_auth").select("id").eq("terapeuta_id", terapeuta_id).limit(1).execute()

    if existente.data:
        sb.table("portal_auth").update({"senha_hash": hash_, "tentativas_falhas": 0, "bloqueado_ate": None}).eq("terapeuta_id", terapeuta_id).execute()
    else:
        sb.table("portal_auth").insert({"terapeuta_id": terapeuta_id, "senha_hash": hash_, "primeiro_login": True}).execute()

    logger.info(f"[PORTAL] Senha configurada para terapeuta {terapeuta_id}")
    return {"ok": True, "mensagem": "Senha configurada com sucesso."}


# ─── PACIENTES ───────────────────────────────────────────────────────────────

async def _importar_pacientes_whatsapp(terapeuta_id: str) -> dict:
    """Importa perfis do WhatsApp (perfil_usuario) para a tabela pacientes."""
    sb = get_supabase()
    perfis = sb.table("perfil_usuario").select("numero_telefone, nome, criado_em, ultima_sessao_em").eq("terapeuta_id", terapeuta_id).execute()

    ja_existem_res = sb.table("pacientes").select("numero_telefone").eq("terapeuta_id", terapeuta_id).execute()
    ja_existem = {r["numero_telefone"] for r in (ja_existem_res.data or [])}

    importados = 0
    for p in (perfis.data or []):
        numero = p.get("numero_telefone")
        if not numero or numero in ja_existem:
            continue
        nome = p.get("nome") or numero
        sb.table("pacientes").insert({
            "terapeuta_id": terapeuta_id,
            "numero_telefone": numero,
            "nome": nome,
            "ultima_sessao_em": p.get("ultima_sessao_em"),
            "data_inicio_acompanhamento": (p.get("criado_em") or "")[:10] or None,
        }).execute()
        importados += 1

    logger.info(f"[PORTAL] Importados {importados} pacientes para terapeuta {terapeuta_id}")
    return {"importados": importados, "ja_existiam": len(ja_existem)}


@router.post("/pacientes/importar-whatsapp", summary="Importa pacientes do WhatsApp")
async def importar_whatsapp(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    return await _importar_pacientes_whatsapp(terapeuta_id)


@router.get("/pacientes", summary="Lista pacientes do terapeuta")
async def listar_pacientes(
    authorization: str = Header(...),
    busca: str = Query(""),
    status_: str = Query("ativo", alias="status"),
    tag: str = Query(""),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    q = sb.table("pacientes").select("*").eq("terapeuta_id", terapeuta_id)
    if status_ and status_ != "todos":
        q = q.eq("status", status_)
    if busca:
        q = q.ilike("nome", f"%{busca}%")
    if tag:
        q = q.contains("tags", [tag])

    offset = (pagina - 1) * por_pagina
    res = q.order("nome").range(offset, offset + por_pagina - 1).execute()
    pacientes = res.data or []

    # Enriquecer com stats
    for p in pacientes:
        numero = p["numero_telefone"]
        conv = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).execute()
        diag = sb.table("diagnosticos_alquimicos").select("id", count="exact").eq("paciente_id", p["id"]).execute()
        acomp = sb.table("acompanhamentos").select("data_prevista").eq("paciente_id", p["id"]).eq("status", "pendente").order("data_prevista").limit(1).execute()
        p["total_mensagens"] = conv.count or 0
        p["total_diagnosticos"] = diag.count or 0
        p["proximo_retorno"] = acomp.data[0]["data_prevista"] if acomp.data else None

    total_res = sb.table("pacientes").select("id", count="exact").eq("terapeuta_id", terapeuta_id).execute()
    return {
        "pacientes": pacientes,
        "total": total_res.count or 0,
        "pagina": pagina,
        "por_pagina": por_pagina,
    }


@router.get("/pacientes/{paciente_id}", summary="Perfil completo de um paciente")
async def get_paciente(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    res = sb.table("pacientes").select("*").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return res.data[0]


@router.post("/pacientes", summary="Criar paciente")
async def criar_paciente(body: PacienteIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["terapeuta_id"] = terapeuta_id
    res = sb.table("pacientes").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/pacientes/{paciente_id}", summary="Editar paciente")
async def editar_paciente(paciente_id: str, body: PacienteUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    res = sb.table("pacientes").update(data).eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return res.data[0]


@router.delete("/pacientes/{paciente_id}", summary="Arquivar paciente (soft delete)")
async def arquivar_paciente(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    sb.table("pacientes").update({"status": "arquivado", "atualizado_em": datetime.now(timezone.utc).isoformat()}).eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).execute()
    return {"ok": True}


# ─── PRONTUÁRIO ──────────────────────────────────────────────────────────────

@router.get("/prontuario/{paciente_id}", summary="Prontuário completo do paciente")
async def get_prontuario(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Paciente
    pac_res = sb.table("pacientes").select("*").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    paciente = pac_res.data[0]
    numero = paciente["numero_telefone"]

    # Conversas (últimas 20)
    conv_res = sb.table("conversas").select("id, mensagem_paciente, resposta_agente, intencao, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).order("criado_em", desc=True).limit(20).execute()

    # Diagnósticos
    diag_res = sb.table("diagnosticos_alquimicos").select("*").eq("paciente_id", paciente_id).eq("terapeuta_id", terapeuta_id).order("sessao_data", desc=True).execute()

    # Anotações
    anot_res = sb.table("anotacoes_prontuario").select("*").eq("paciente_id", paciente_id).order("data_anotacao", desc=True).execute()

    # Acompanhamentos pendentes
    acomp_res = sb.table("acompanhamentos").select("*").eq("paciente_id", paciente_id).eq("status", "pendente").order("data_prevista").execute()

    # Mapas natais
    mapas_res = sb.table("mapas_astrais").select("id, data_nascimento, imagem_url, criado_em").eq("numero_telefone", numero).order("criado_em", desc=True).execute()

    # Resumos de sessão (memória de longo prazo)
    resumos_res = sb.table("resumos_sessao").select("*").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).order("sessao_inicio", desc=True).limit(20).execute()

    # Perfil de memória do paciente
    perfil_res = sb.table("perfil_usuario").select("*").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).limit(1).execute()

    return {
        "paciente": paciente,
        "conversas": conv_res.data or [],
        "diagnosticos": diag_res.data or [],
        "anotacoes": anot_res.data or [],
        "acompanhamentos": acomp_res.data or [],
        "mapas_natais": mapas_res.data or [],
        "resumos_sessao": resumos_res.data or [],
        "perfil_memoria": perfil_res.data[0] if perfil_res.data else None,
    }


@router.get("/prontuario/{paciente_id}/timeline", summary="Timeline unificada do paciente")
async def get_timeline(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    pac_res = sb.table("pacientes").select("numero_telefone").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    numero = pac_res.data[0]["numero_telefone"]

    eventos = []

    # Conversas
    conv = sb.table("conversas").select("id, mensagem_paciente, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).order("criado_em", desc=True).limit(50).execute()
    for c in (conv.data or []):
        eventos.append({"tipo": "conversa", "data": c["criado_em"], "resumo": (c.get("mensagem_paciente") or "")[:100], "id": c["id"]})

    # Diagnósticos
    diag = sb.table("diagnosticos_alquimicos").select("id, sessao_data, elemento_dominante, status").eq("paciente_id", paciente_id).execute()
    for d in (diag.data or []):
        eventos.append({"tipo": "diagnostico", "data": d["sessao_data"], "resumo": f"Diagnóstico — {d.get('elemento_dominante') or 'Sem elemento'}", "id": d["id"]})

    # Anotações
    anot = sb.table("anotacoes_prontuario").select("id, data_anotacao, tipo, titulo, conteudo").eq("paciente_id", paciente_id).execute()
    for a in (anot.data or []):
        eventos.append({"tipo": f"anotacao_{a['tipo']}", "data": a["data_anotacao"], "resumo": a.get("titulo") or (a.get("conteudo") or "")[:80], "id": a["id"]})

    # Mapas
    mapas = sb.table("mapas_astrais").select("id, criado_em, data_nascimento").eq("numero_telefone", numero).execute()
    for m in (mapas.data or []):
        eventos.append({"tipo": "mapa_natal", "data": m["criado_em"], "resumo": f"Mapa natal — {m.get('data_nascimento') or ''}", "id": m["id"]})

    # Resumos de sessão (memória IA)
    resumos = sb.table("resumos_sessao").select("id, sessao_inicio, resumo, total_mensagens").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).execute()
    for r in (resumos.data or []):
        resumo_raw = r.get("resumo", "")
        if isinstance(resumo_raw, dict):
            texto = resumo_raw.get("resumo", "")[:100]
            humor = resumo_raw.get("humor_percebido", "")
            resumo_str = f"Sessão IA — {texto}" + (f" (humor: {humor})" if humor else "")
        else:
            resumo_str = f"Sessão IA — {str(resumo_raw)[:100]}"
        eventos.append({"tipo": "resumo_sessao", "data": r["sessao_inicio"], "resumo": resumo_str, "id": r["id"]})

    eventos.sort(key=lambda x: x.get("data") or "", reverse=True)
    return {"timeline": eventos[:100]}


@router.get("/prontuario/{paciente_id}/conversas", summary="Histórico de conversas paginado")
async def get_conversas_paciente(
    paciente_id: str,
    authorization: str = Header(...),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    busca: str = Query(""),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    pac_res = sb.table("pacientes").select("numero_telefone").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    numero = pac_res.data[0]["numero_telefone"]

    q = sb.table("conversas").select("*").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero)
    if busca:
        q = q.ilike("mensagem_paciente", f"%{busca}%")

    offset = (pagina - 1) * por_pagina
    res = q.order("criado_em", desc=True).range(offset, offset + por_pagina - 1).execute()
    return {"conversas": res.data or [], "pagina": pagina, "por_pagina": por_pagina}


# ─── DIAGNÓSTICOS ────────────────────────────────────────────────────────────

@router.get("/diagnosticos", summary="Lista diagnósticos")
async def listar_diagnosticos(
    authorization: str = Header(...),
    paciente_id: str = Query(""),
    status_: str = Query("", alias="status"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    q = sb.table("diagnosticos_alquimicos").select("*, pacientes(nome, numero_telefone)").eq("terapeuta_id", terapeuta_id)
    if paciente_id:
        q = q.eq("paciente_id", paciente_id)
    if status_:
        q = q.eq("status", status_)
    offset = (pagina - 1) * por_pagina
    res = q.order("sessao_data", desc=True).range(offset, offset + por_pagina - 1).execute()
    return {"diagnosticos": res.data or [], "pagina": pagina}


@router.post("/diagnosticos", summary="Criar diagnóstico")
async def criar_diagnostico(body: DiagnosticoIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["terapeuta_id"] = terapeuta_id
    if not data.get("sessao_data"):
        data["sessao_data"] = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("diagnosticos_alquimicos").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/diagnosticos/{diagnostico_id}", summary="Editar diagnóstico")
async def editar_diagnostico(diagnostico_id: str, body: DiagnosticoUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    res = sb.table("diagnosticos_alquimicos").update(data).eq("id", diagnostico_id).eq("terapeuta_id", terapeuta_id).execute()
    return res.data[0] if res.data else {}


@router.delete("/diagnosticos/{diagnostico_id}", summary="Arquivar diagnóstico")
async def arquivar_diagnostico(diagnostico_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    sb.table("diagnosticos_alquimicos").update({"status": "arquivado"}).eq("id", diagnostico_id).eq("terapeuta_id", terapeuta_id).execute()
    return {"ok": True}


@router.post("/diagnosticos/auto-extrair/{paciente_id}", summary="[IA] Extrai diagnóstico das conversas")
async def auto_extrair_diagnostico(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Verificar paciente
    pac_res = sb.table("pacientes").select("nome, numero_telefone").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    pac = pac_res.data[0]

    # Buscar últimas 50 conversas
    conv = sb.table("conversas").select("mensagem_paciente, resposta_agente, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", pac["numero_telefone"]).order("criado_em", desc=True).limit(50).execute()

    if not conv.data:
        raise HTTPException(status_code=400, detail="Nenhuma conversa encontrada para este paciente.")

    historico = "\n".join([
        f"[{c['criado_em'][:10]}] Paciente: {c.get('mensagem_paciente', '')}\nAssistente: {(c.get('resposta_agente') or '')[:300]}"
        for c in reversed(conv.data)
    ])

    prompt = f"""Analise o histórico de atendimento alquímico do paciente {pac['nome']} e extraia os dados diagnósticos no formato JSON.

HISTÓRICO:
{historico[:8000]}

Retorne APENAS um JSON válido com esta estrutura (sem markdown, sem explicação):
{{
  "elemento_dominante": "Fogo|Água|Ar|Terra ou null",
  "elemento_carente": "Fogo|Água|Ar|Terra ou null",
  "elementos_detalhes": {{"Fogo": 0, "Água": 0, "Ar": 0, "Terra": 0}},
  "dna_comprometido": ["lista de padrões DNA comprometidos mencionados"],
  "dna_descricao": "descrição breve ou null",
  "serpentes_ativas": ["lista de serpentes/padrões de sabotagem mencionados"],
  "serpentes_descricao": "descrição breve ou null",
  "setenio_atual": null,
  "setenio_descricao": null,
  "florais_prescritos": ["lista de florais mencionados"],
  "protocolo_texto": "resumo do protocolo terapêutico mencionado ou null"
}}"""

    import anthropic
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    resposta = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    texto = resposta.content[0].text.strip()
    # Remove markdown se houver
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        draft = json.loads(texto)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao parsear resposta da IA. Tente novamente.")

    draft["paciente_id"] = paciente_id
    draft["fonte"] = "whatsapp_auto"
    draft["status"] = "rascunho"
    draft["sessao_data"] = datetime.now(timezone.utc).date().isoformat()

    logger.info(f"[PORTAL] Diagnóstico auto-extraído para paciente {paciente_id}")
    return {"draft": draft, "mensagem": "Diagnóstico extraído. Revise e salve."}


# ─── ANOTAÇÕES ───────────────────────────────────────────────────────────────

@router.get("/anotacoes/{paciente_id}", summary="Lista anotações do paciente")
async def listar_anotacoes(
    paciente_id: str,
    authorization: str = Header(...),
    tipo: str = Query(""),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    q = sb.table("anotacoes_prontuario").select("*").eq("paciente_id", paciente_id).eq("terapeuta_id", terapeuta_id)
    if tipo:
        q = q.eq("tipo", tipo)
    offset = (pagina - 1) * por_pagina
    res = q.order("data_anotacao", desc=True).range(offset, offset + por_pagina - 1).execute()
    return {"anotacoes": res.data or [], "pagina": pagina}


@router.post("/anotacoes", summary="Criar anotação")
async def criar_anotacao(body: AnotacaoIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["terapeuta_id"] = terapeuta_id
    if not data.get("data_anotacao"):
        data["data_anotacao"] = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("anotacoes_prontuario").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/anotacoes/item/{anotacao_id}", summary="Editar anotação")
async def editar_anotacao(anotacao_id: str, body: AnotacaoUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    res = sb.table("anotacoes_prontuario").update(data).eq("id", anotacao_id).eq("terapeuta_id", terapeuta_id).execute()
    return res.data[0] if res.data else {}


@router.delete("/anotacoes/item/{anotacao_id}", summary="Deletar anotação")
async def deletar_anotacao(anotacao_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    sb.table("anotacoes_prontuario").delete().eq("id", anotacao_id).eq("terapeuta_id", terapeuta_id).execute()
    return {"ok": True}


# ─── ACOMPANHAMENTOS ─────────────────────────────────────────────────────────

@router.get("/acompanhamentos", summary="Lista acompanhamentos")
async def listar_acompanhamentos(
    authorization: str = Header(...),
    status_: str = Query("pendente", alias="status"),
    paciente_id: str = Query(""),
    data_ate: str = Query(""),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    q = sb.table("acompanhamentos").select("*, pacientes(nome, numero_telefone)").eq("terapeuta_id", terapeuta_id)
    if status_ and status_ != "todos":
        q = q.eq("status", status_)
    if paciente_id:
        q = q.eq("paciente_id", paciente_id)
    if data_ate:
        q = q.lte("data_prevista", data_ate)
    res = q.order("data_prevista").execute()
    return {"acompanhamentos": res.data or []}


@router.get("/acompanhamentos/agenda", summary="Agenda dos próximos 7 dias")
async def get_agenda(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    hoje = datetime.now(timezone.utc).date()
    em_7_dias = (hoje + timedelta(days=7)).isoformat()

    res = sb.table("acompanhamentos").select("*, pacientes(nome, numero_telefone)").eq("terapeuta_id", terapeuta_id).eq("status", "pendente").lte("data_prevista", em_7_dias).order("data_prevista").execute()

    # Agrupar por data
    agenda: dict = {}
    for a in (res.data or []):
        data = a.get("data_prevista") or "sem_data"
        if data not in agenda:
            agenda[data] = []
        agenda[data].append(a)

    return {"agenda": agenda, "hoje": hoje.isoformat()}


@router.post("/acompanhamentos", summary="Criar acompanhamento")
async def criar_acompanhamento(body: AcompanhamentoIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["terapeuta_id"] = terapeuta_id
    res = sb.table("acompanhamentos").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/acompanhamentos/{acomp_id}", summary="Atualizar acompanhamento")
async def atualizar_acompanhamento(acomp_id: str, body: AcompanhamentoUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    if data.get("status") == "realizado" and not data.get("data_realizado"):
        data["data_realizado"] = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("acompanhamentos").update(data).eq("id", acomp_id).eq("terapeuta_id", terapeuta_id).execute()
    return res.data[0] if res.data else {}


# ─── MAPAS NATAIS ────────────────────────────────────────────────────────────

@router.get("/mapas", summary="Galeria de mapas natais")
async def listar_mapas(
    authorization: str = Header(...),
    paciente_id: str = Query(""),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Se paciente_id fornecido, buscar número do paciente
    numeros = None
    if paciente_id:
        pac = sb.table("pacientes").select("numero_telefone").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
        if pac.data:
            numeros = [pac.data[0]["numero_telefone"]]

    # Buscar mapas da instância do terapeuta via perfil_usuario
    if numeros is None:
        perfis = sb.table("perfil_usuario").select("numero_telefone").eq("terapeuta_id", terapeuta_id).execute()
        numeros = [p["numero_telefone"] for p in (perfis.data or [])]

    if not numeros:
        return {"mapas": [], "total": 0}

    offset = (pagina - 1) * por_pagina
    res = sb.table("mapas_astrais").select("id, numero_telefone, data_nascimento, imagem_url, criado_em").in_("numero_telefone", numeros).order("criado_em", desc=True).range(offset, offset + por_pagina - 1).execute()

    # Enriquecer com nome do paciente
    mapas = res.data or []
    for m in mapas:
        pac = sb.table("pacientes").select("nome").eq("numero_telefone", m["numero_telefone"]).eq("terapeuta_id", terapeuta_id).limit(1).execute()
        m["nome_paciente"] = pac.data[0]["nome"] if pac.data else m["numero_telefone"]

    return {"mapas": mapas, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/mapas/{mapa_id}", summary="Detalhes de um mapa natal")
async def get_mapa(mapa_id: str, authorization: str = Header(...)):
    _get_terapeuta_id(authorization)
    sb = get_supabase()
    res = sb.table("mapas_astrais").select("*").eq("id", mapa_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Mapa não encontrado.")
    return res.data[0]


# ─── RELATÓRIOS ──────────────────────────────────────────────────────────────

@router.get("/relatorios/visao-geral", summary="Visão geral do terapeuta")
async def relatorio_visao_geral(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_pac = sb.table("pacientes").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("status", "ativo").execute()
    total_conv = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).execute()
    conv_mes = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).gte("criado_em", inicio_mes.isoformat()).execute()
    diag_mes = sb.table("diagnosticos_alquimicos").select("id", count="exact").eq("terapeuta_id", terapeuta_id).gte("criado_em", inicio_mes.isoformat()).execute()

    proximos = sb.table("acompanhamentos").select("*, pacientes(nome)").eq("terapeuta_id", terapeuta_id).eq("status", "pendente").order("data_prevista").limit(5).execute()

    # Distribuição de elementos
    diag_all = sb.table("diagnosticos_alquimicos").select("elemento_dominante").eq("terapeuta_id", terapeuta_id).eq("status", "finalizado").execute()
    elementos: dict = {}
    for d in (diag_all.data or []):
        el = d.get("elemento_dominante")
        if el:
            elementos[el] = elementos.get(el, 0) + 1

    return {
        "pacientes_ativos": total_pac.count or 0,
        "total_conversas": total_conv.count or 0,
        "conversas_este_mes": conv_mes.count or 0,
        "diagnosticos_este_mes": diag_mes.count or 0,
        "proximos_retornos": proximos.data or [],
        "elementos_distribuicao": elementos,
    }


@router.get("/relatorios/paciente/{paciente_id}", summary="Relatório completo do paciente (para impressão)")
async def relatorio_paciente(paciente_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    pac_res = sb.table("pacientes").select("*").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    paciente = pac_res.data[0]
    numero = paciente["numero_telefone"]

    diag = sb.table("diagnosticos_alquimicos").select("*").eq("paciente_id", paciente_id).eq("status", "finalizado").order("sessao_data").execute()
    anot = sb.table("anotacoes_prontuario").select("*").eq("paciente_id", paciente_id).order("data_anotacao").execute()
    mapas = sb.table("mapas_astrais").select("data_nascimento, imagem_url, criado_em").eq("numero_telefone", numero).execute()
    conv_count = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).execute()

    # Resumo de florais usados
    todos_florais: list = []
    for d in (diag.data or []):
        todos_florais.extend(d.get("florais_prescritos") or [])
    from collections import Counter
    florais_ranking = Counter(todos_florais).most_common(10)

    ter_res = sb.table("terapeutas").select("nome, especialidade").eq("id", terapeuta_id).limit(1).execute()

    return {
        "gerado_em": agora_utc_str(),
        "terapeuta": ter_res.data[0] if ter_res.data else {},
        "paciente": paciente,
        "total_sessoes_whatsapp": conv_count.count or 0,
        "diagnosticos": diag.data or [],
        "anotacoes": anot.data or [],
        "mapas_natais": mapas.data or [],
        "florais_mais_prescritos": [{"floral": f, "vezes": n} for f, n in florais_ranking],
    }


@router.get("/relatorios/diagnosticos", summary="Rankings de diagnósticos")
async def relatorio_diagnosticos(
    authorization: str = Header(...),
    periodo: str = Query("90d"),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    dias = {"30d": 30, "90d": 90, "365d": 365}.get(periodo, 90)
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).date().isoformat()

    res = sb.table("diagnosticos_alquimicos").select("elemento_dominante, dna_comprometido, serpentes_ativas, florais_prescritos").eq("terapeuta_id", terapeuta_id).gte("sessao_data", desde).execute()

    from collections import Counter
    elementos: list[str] = []
    dna: list[str] = []
    serpentes: list[str] = []
    florais: list[str] = []

    for d in (res.data or []):
        if d.get("elemento_dominante"):
            elementos.append(d["elemento_dominante"])
        dna.extend(d.get("dna_comprometido") or [])
        serpentes.extend(d.get("serpentes_ativas") or [])
        florais.extend(d.get("florais_prescritos") or [])

    return {
        "periodo": periodo,
        "total_diagnosticos": len(res.data or []),
        "elementos_ranking": Counter(elementos).most_common(),
        "dna_ranking": Counter(dna).most_common(10),
        "serpentes_ranking": Counter(serpentes).most_common(10),
        "florais_ranking": Counter(florais).most_common(15),
    }


@router.post("/auth/alterar-senha", summary="Alterar senha do terapeuta logado")
async def alterar_senha(
    body: dict,
    authorization: str = Header(...),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    nova_senha = body.get("nova_senha", "")
    if not nova_senha or len(nova_senha) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 8 caracteres.")

    sb = get_supabase()
    senha_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
    sb.table("portal_auth").update({"senha_hash": senha_hash}).eq("terapeuta_id", terapeuta_id).execute()
    return {"ok": True}


@router.put("/configuracoes", summary="Atualizar configurações do terapeuta (nome, nome_agente)")
async def atualizar_configuracoes(
    body: dict,
    authorization: str = Header(...),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    campos_permitidos = {"nome", "nome_agente", "tom_de_voz", "contato_agendamento", "horario_atendimento"}
    update_data = {k: v for k, v in body.items() if k in campos_permitidos and v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualizar.")

    sb = get_supabase()
    sb.table("terapeutas").update(update_data).eq("id", terapeuta_id).execute()
    return {"ok": True}


@router.get("/documentos", summary="Lista documentos indexados do terapeuta")
async def listar_documentos(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    res = sb.table("documentos").select("id, nome_arquivo, status, total_chunks, criado_em").eq("terapeuta_id", terapeuta_id).order("criado_em", desc=True).execute()
    return res.data or []


def agora_utc_str() -> str:
    return datetime.now(timezone.utc).isoformat()
