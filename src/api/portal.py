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

  GET  /portal/api/conversas                → todas as conversas (agrupáveis por paciente)

  GET  /portal/api/mapas
  GET  /portal/api/mapas/{id}

  GET  /portal/api/relatorios/visao-geral
  GET  /portal/api/relatorios/paciente/{id}
  GET  /portal/api/relatorios/diagnosticos

  GET  /portal/api/pacientes/{id}/analise-elementos
  GET  /portal/api/pacientes/{id}/progresso
  GET  /portal/api/financeiro/resumo
"""

import logging
import random
from collections import Counter
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
    if settings.SECRET_KEY == "trocar-em-producao":
        logger.critical("SEGURANCA: SECRET_KEY com valor padrao! JWTs podem ser forjados. Configure no Railway AGORA.")
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
    # Substâncias alquímicas (Enxofre, Sal, Mercúrio)
    substancias: Optional[dict] = {}  # {"enxofre": 45, "sal": 30, "mercurio": 25}
    substancias_descricao: Optional[str] = None
    # Níveis de florais (1=momentâneo, 2=espiritual+material, 3=espiritual urgente)
    nivel_floral: Optional[int] = None
    florais_nivel_descricao: Optional[str] = None
    # Fluxo Contínuo
    fluxo_continuo: Optional[bool] = None  # True=conectado, False=desconectado
    fluxo_continuo_descricao: Optional[str] = None
    # Matriz Alquímica
    matriz_alquimica: Optional[dict] = {}
    aliastrons: Optional[list[str]] = []
    # Progresso
    progresso_status: Optional[str] = None  # "progredindo", "estavel", "regredindo", "surto"
    progresso_observacoes: Optional[str] = None


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
    # Substâncias alquímicas (Enxofre, Sal, Mercúrio)
    substancias: Optional[dict] = None
    substancias_descricao: Optional[str] = None
    # Níveis de florais (1=momentâneo, 2=espiritual+material, 3=espiritual urgente)
    nivel_floral: Optional[int] = None
    florais_nivel_descricao: Optional[str] = None
    # Fluxo Contínuo
    fluxo_continuo: Optional[bool] = None
    fluxo_continuo_descricao: Optional[str] = None
    # Matriz Alquímica
    matriz_alquimica: Optional[dict] = None
    aliastrons: Optional[list[str]] = None
    # Progresso
    progresso_status: Optional[str] = None
    progresso_observacoes: Optional[str] = None


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
    hora_prevista: Optional[str] = None
    prioridade: Optional[int] = 2


class AcompanhamentoUpdate(BaseModel):
    tipo: Optional[str] = None
    descricao: Optional[str] = None
    data_prevista: Optional[str] = None
    hora_prevista: Optional[str] = None
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


# ─── RECUPERAÇÃO DE SENHA ───────────────────────────────────────────────────

class RecuperarSenhaIn(BaseModel):
    email: str


class VerificarCodigoIn(BaseModel):
    email: str
    codigo: str


class RedefinirSenhaIn(BaseModel):
    email: str
    codigo: str
    nova_senha: str


class AlterarSenhaIn(BaseModel):
    senha_atual: str
    nova_senha: str


@router.post("/auth/recuperar-senha", summary="Solicitar código de recuperação de senha")
async def recuperar_senha(body: RecuperarSenhaIn):
    sb = get_supabase()

    # 1. Buscar terapeuta pelo email
    res = sb.table("terapeutas").select("id").eq("email", body.email).limit(1).execute()
    if not res.data:
        # Retornar sucesso mesmo se email não existir (segurança)
        return {"ok": True, "mensagem": "Se o email estiver cadastrado, um código foi enviado."}
    terapeuta_id = res.data[0]["id"]

    # 2. Gerar código de 6 dígitos
    codigo = f"{random.randint(100000, 999999)}"
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    # 3. Salvar código no portal_auth
    auth_res = sb.table("portal_auth").select("id").eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not auth_res.data:
        return {"ok": True, "mensagem": "Se o email estiver cadastrado, um código foi enviado."}

    sb.table("portal_auth").update({
        "codigo_recuperacao": codigo,
        "codigo_expira_em": expira_em,
    }).eq("terapeuta_id", terapeuta_id).execute()

    # TODO: Enviar email com o código. Por enquanto, logamos.
    logger.info(f"[PORTAL] Código de recuperação para {body.email}: {codigo}")

    # Tentar enviar código via WhatsApp se terapeuta tem telefone
    try:
        terapeuta_res = sb.table("terapeutas").select("telefone, numero_whatsapp, nome_instancia_evolution").eq("id", terapeuta_id).limit(1).execute()
        terapeuta_info = terapeuta_res.data[0] if terapeuta_res.data else {}
        telefone = terapeuta_info.get("telefone") or terapeuta_info.get("numero_whatsapp")
        instancia = terapeuta_info.get("nome_instancia_evolution")
        if telefone and instancia:
            from src.whatsapp.evolution import EvolutionClient
            client = EvolutionClient()
            await client.enviar_mensagem(
                instance=instancia,
                numero=telefone,
                texto=f"Seu código de recuperação de senha: {codigo}\n\nVálido por 15 minutos.",
            )
            logger.info(f"[PORTAL] Código enviado via WhatsApp para {telefone}")
        elif telefone:
            logger.info(f"[PORTAL] Código de recuperação para {body.email}: {codigo} (sem instância Evolution para envio)")
    except Exception as e:
        logger.warning(f"[PORTAL] Falha ao enviar código via WhatsApp: {e}. Código logado: {codigo}")

    return {"ok": True, "mensagem": "Se o email estiver cadastrado, um código foi enviado."}


@router.post("/auth/verificar-codigo", summary="Verificar código de recuperação")
async def verificar_codigo(body: VerificarCodigoIn):
    sb = get_supabase()

    # 1. Buscar terapeuta pelo email
    res = sb.table("terapeutas").select("id").eq("email", body.email).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    terapeuta_id = res.data[0]["id"]

    # 2. Buscar auth record e validar código
    auth_res = sb.table("portal_auth").select("codigo_recuperacao, codigo_expira_em").eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not auth_res.data:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    auth = auth_res.data[0]
    codigo_salvo = auth.get("codigo_recuperacao")
    expira_em = auth.get("codigo_expira_em")

    if not codigo_salvo or codigo_salvo != body.codigo:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    if expira_em:
        expira_dt = datetime.fromisoformat(expira_em.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expira_dt:
            raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    return {"ok": True, "mensagem": "Código verificado com sucesso."}


@router.post("/auth/redefinir-senha", summary="Redefinir senha com código de recuperação")
async def redefinir_senha(body: RedefinirSenhaIn):
    sb = get_supabase()

    if not body.nova_senha or len(body.nova_senha) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 8 caracteres.")

    # 1. Buscar terapeuta pelo email
    res = sb.table("terapeutas").select("id").eq("email", body.email).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    terapeuta_id = res.data[0]["id"]

    # 2. Validar código
    auth_res = sb.table("portal_auth").select("codigo_recuperacao, codigo_expira_em").eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not auth_res.data:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    auth = auth_res.data[0]
    codigo_salvo = auth.get("codigo_recuperacao")
    expira_em = auth.get("codigo_expira_em")

    if not codigo_salvo or codigo_salvo != body.codigo:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    if expira_em:
        expira_dt = datetime.fromisoformat(expira_em.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expira_dt:
            raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    # 3. Atualizar senha e limpar código
    senha_hash = _hash_senha(body.nova_senha)
    sb.table("portal_auth").update({
        "senha_hash": senha_hash,
        "codigo_recuperacao": None,
        "codigo_expira_em": None,
        "tentativas_falhas": 0,
        "bloqueado_ate": None,
    }).eq("terapeuta_id", terapeuta_id).execute()

    logger.info(f"[PORTAL] Senha redefinida para terapeuta {terapeuta_id}")
    return {"ok": True, "mensagem": "Senha redefinida com sucesso."}


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

    # Enriquecer com stats — batch queries para evitar N+1
    if pacientes:
        numeros = [p["numero_telefone"] for p in pacientes]
        paciente_ids = [p["id"] for p in pacientes]

        # Batch: contagem de conversas por número
        conv_all = sb.table("conversas").select("paciente_numero", count="exact").eq("terapeuta_id", terapeuta_id).in_("paciente_numero", numeros).execute()
        # Agrupar contagens por número (Supabase retorna todos os registros, usamos count por filtro individual)
        # Como o .in_() retorna o total, precisamos contar por número individualmente via dados retornados
        conv_por_numero: dict[str, int] = {}
        for row in (conv_all.data or []):
            num = row.get("paciente_numero", "")
            conv_por_numero[num] = conv_por_numero.get(num, 0) + 1

        # Batch: contagem de diagnósticos por paciente_id
        diag_all = sb.table("diagnosticos_alquimicos").select("paciente_id").in_("paciente_id", paciente_ids).execute()
        diag_por_paciente: dict[str, int] = {}
        for row in (diag_all.data or []):
            pid = row.get("paciente_id", "")
            diag_por_paciente[pid] = diag_por_paciente.get(pid, 0) + 1

        # Batch: próximo acompanhamento pendente por paciente_id
        acomp_all = sb.table("acompanhamentos").select("paciente_id, data_prevista").in_("paciente_id", paciente_ids).eq("status", "pendente").order("data_prevista").execute()
        acomp_por_paciente: dict[str, str] = {}
        for row in (acomp_all.data or []):
            pid = row.get("paciente_id", "")
            # Só guarda o primeiro (mais próximo) de cada paciente
            if pid not in acomp_por_paciente:
                acomp_por_paciente[pid] = row["data_prevista"]

        for p in pacientes:
            p["total_mensagens"] = conv_por_numero.get(p["numero_telefone"], 0)
            p["total_diagnosticos"] = diag_por_paciente.get(p["id"], 0)
            p["proximo_retorno"] = acomp_por_paciente.get(p["id"])

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
    data = body.model_dump(exclude_unset=True)
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

    # Conversas — busca por numero E por paciente_vinculado_id
    conv_by_num = []
    if numero and numero != "sem-numero":
        r1 = sb.table("conversas").select("id, mensagem_paciente, resposta_agente, intencao, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).order("criado_em", desc=True).limit(50).execute()
        conv_by_num = r1.data or []
    conv_by_link = sb.table("conversas").select("id, mensagem_paciente, resposta_agente, intencao, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_vinculado_id", paciente_id).order("criado_em", desc=True).limit(50).execute()
    # Merge sem duplicatas
    seen_ids = set()
    all_convs = []
    for c in (conv_by_num + (conv_by_link.data or [])):
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            all_convs.append(c)
    all_convs.sort(key=lambda x: x.get("criado_em", ""), reverse=True)
    conv_res_data = all_convs[:50]

    # Diagnósticos
    diag_res = sb.table("diagnosticos_alquimicos").select("*").eq("paciente_id", paciente_id).eq("terapeuta_id", terapeuta_id).order("sessao_data", desc=True).execute()

    # Anotações
    anot_res = sb.table("anotacoes_prontuario").select("*").eq("paciente_id", paciente_id).order("data_anotacao", desc=True).execute()

    # Acompanhamentos pendentes
    acomp_res = sb.table("acompanhamentos").select("*").eq("paciente_id", paciente_id).eq("status", "pendente").order("data_prevista").execute()

    # Mapas natais — busca por numero E por nome do paciente
    nome_paciente = paciente.get("nome", "")
    mapas_by_num = []
    if numero and numero != "sem-numero":
        r2 = sb.table("mapas_astrais").select("id, nome, data_nascimento, hora_nascimento, cidade_nascimento, imagem_url, mapa_json, tipo_mapa, criado_em").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).order("criado_em", desc=True).execute()
        mapas_by_num = r2.data or []
    mapas_by_name = []
    if nome_paciente:
        r3 = sb.table("mapas_astrais").select("id, nome, data_nascimento, hora_nascimento, cidade_nascimento, imagem_url, mapa_json, tipo_mapa, criado_em").eq("terapeuta_id", terapeuta_id).eq("nome", nome_paciente).order("criado_em", desc=True).execute()
        mapas_by_name = r3.data or []
    seen_mids = set()
    all_mapas = []
    for m in (mapas_by_num + mapas_by_name):
        if m["id"] not in seen_mids:
            seen_mids.add(m["id"])
            all_mapas.append(m)
    mapas_res_data = all_mapas

    # Resumos de sessão (memória de longo prazo)
    resumos_res = sb.table("resumos_sessao").select("*").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).order("sessao_inicio", desc=True).limit(20).execute()

    # Perfil de memória do paciente
    perfil_res = sb.table("perfil_usuario").select("*").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).limit(1).execute()

    return {
        "paciente": paciente,
        "conversas": conv_res_data,
        "diagnosticos": diag_res.data or [],
        "anotacoes": anot_res.data or [],
        "acompanhamentos": acomp_res.data or [],
        "mapas_natais": mapas_res_data,
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
    nome_paciente = ""
    pac_full = sb.table("pacientes").select("nome").eq("id", paciente_id).limit(1).execute()
    if pac_full.data:
        nome_paciente = pac_full.data[0].get("nome", "")

    # Conversas — agrupar em sessões (início/fim), não listar cada mensagem
    all_convs = []
    if numero and numero != "sem-numero":
        r1 = sb.table("conversas").select("id, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).order("criado_em").execute()
        all_convs.extend(r1.data or [])
    r2 = sb.table("conversas").select("id, criado_em").eq("terapeuta_id", terapeuta_id).eq("paciente_vinculado_id", paciente_id).order("criado_em").execute()
    seen_cids = set()
    for c in all_convs + (r2.data or []):
        if c["id"] not in seen_cids:
            seen_cids.add(c["id"])
    # Agrupar conversas em sessões (gap > 30min = nova sessão)
    conv_all = sorted([c for c in all_convs + (r2.data or []) if c["id"] in seen_cids], key=lambda x: x["criado_em"])
    # Deduplicate
    conv_dedup = []
    conv_seen = set()
    for c in conv_all:
        if c["id"] not in conv_seen:
            conv_seen.add(c["id"])
            conv_dedup.append(c)
    if conv_dedup:
        from datetime import datetime as dt
        sessions = []
        sess_start = conv_dedup[0]["criado_em"]
        sess_end = conv_dedup[0]["criado_em"]
        sess_count = 1
        for c in conv_dedup[1:]:
            try:
                t_prev = dt.fromisoformat(sess_end.replace("Z", "+00:00"))
                t_curr = dt.fromisoformat(c["criado_em"].replace("Z", "+00:00"))
                gap = (t_curr - t_prev).total_seconds()
            except Exception:
                gap = 0
            if gap > 1800:  # 30 min gap = new session
                sessions.append((sess_start, sess_end, sess_count))
                sess_start = c["criado_em"]
                sess_count = 0
            sess_end = c["criado_em"]
            sess_count += 1
        sessions.append((sess_start, sess_end, sess_count))
        for start, end, count in sessions:
            eventos.append({"tipo": "conversa_inicio", "data": start, "resumo": f"Conversa iniciada ({count} mensagens)"})
            eventos.append({"tipo": "conversa_fim", "data": end, "resumo": f"Conversa finalizada"})

    # Diagnósticos
    diag = sb.table("diagnosticos_alquimicos").select("id, sessao_data, elemento_dominante, status, criado_em").eq("paciente_id", paciente_id).execute()
    for d in (diag.data or []):
        eventos.append({"tipo": "diagnostico", "data": d.get("criado_em") or d["sessao_data"], "resumo": f"Diagnóstico — {d.get('elemento_dominante') or 'Sem elemento'}", "id": d["id"]})

    # Anotações
    anot = sb.table("anotacoes_prontuario").select("id, data_anotacao, tipo, titulo, conteudo").eq("paciente_id", paciente_id).execute()
    for a in (anot.data or []):
        eventos.append({"tipo": f"anotacao_{a['tipo']}", "data": a["data_anotacao"], "resumo": a.get("titulo") or (a.get("conteudo") or "")[:80], "id": a["id"]})

    # Mapas — busca por numero e por nome do paciente
    mapas_tl = []
    if numero and numero != "sem-numero":
        try:
            r_m1 = sb.table("mapas_astrais").select("id, criado_em, data_nascimento, tipo_mapa").eq("terapeuta_id", terapeuta_id).eq("numero_telefone", numero).execute()
            mapas_tl.extend(r_m1.data or [])
        except Exception:
            pass
    if nome_paciente:
        try:
            r_m2 = sb.table("mapas_astrais").select("id, criado_em, data_nascimento, tipo_mapa").eq("terapeuta_id", terapeuta_id).eq("nome", nome_paciente).execute()
            seen_m = {m["id"] for m in mapas_tl}
            mapas_tl.extend([m for m in (r_m2.data or []) if m["id"] not in seen_m])
        except Exception:
            pass
    for m in mapas_tl:
        tipo_label = m.get("tipo_mapa") or "Mapa Natal"
        eventos.append({"tipo": "mapa_natal", "data": m["criado_em"], "resumo": f"{tipo_label} — {m.get('data_nascimento') or ''}", "id": m["id"]})

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

    # Buscar conversas por número do paciente (diretas) E por paciente_vinculado_id (segmentadas)
    q1 = sb.table("conversas").select("*").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero)
    if busca:
        q1 = q1.ilike("mensagem_paciente", f"%{busca}%")

    offset = (pagina - 1) * por_pagina
    res1 = q1.order("criado_em", desc=True).range(offset, offset + por_pagina - 1).execute()

    # Buscar conversas vinculadas pelo sistema de segmentação (terapeuta falando SOBRE este paciente)
    try:
        q2 = sb.table("conversas").select("*").eq("terapeuta_id", terapeuta_id).eq("paciente_vinculado_id", paciente_id)
        if busca:
            q2 = q2.ilike("mensagem_paciente", f"%{busca}%")
        res2 = q2.order("criado_em", desc=True).range(offset, offset + por_pagina - 1).execute()
    except Exception:
        res2 = type("R", (), {"data": []})()

    # Mesclar e deduplicar por ID, ordenar por data
    todas = {c["id"]: c for c in (res1.data or [])}
    for c in (res2.data or []):
        todas[c["id"]] = c
    conversas = sorted(todas.values(), key=lambda x: x.get("criado_em", ""), reverse=True)

    return {"conversas": conversas[:por_pagina], "pagina": pagina, "por_pagina": por_pagina}


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


_DIAG_COLS_DB = {
    "id", "terapeuta_id", "paciente_id", "status", "sessao_data",
    "elemento_dominante", "elemento_carente", "elementos_detalhes",
    "dna_comprometido", "dna_descricao", "serpentes_ativas", "serpentes_descricao",
    "setenio_atual", "setenio_descricao", "florais_prescritos", "protocolo_texto",
    "fonte", "conversa_origem_id", "origem",
    # Novas colunas (adicionadas via migration quando disponível)
    "substancias", "substancias_descricao", "nivel_floral", "florais_nivel_descricao",
    "fluxo_continuo", "fluxo_continuo_descricao", "matriz_alquimica", "aliastrons",
    "progresso_status", "progresso_observacoes",
}


def _filtrar_campos_diag(data: dict) -> dict:
    """Remove campos que não existem como colunas na tabela diagnosticos_alquimicos."""
    return {k: v for k, v in data.items() if k in _DIAG_COLS_DB and v is not None and v != {} and v != []}


@router.post("/diagnosticos", summary="Criar diagnóstico")
async def criar_diagnostico(body: DiagnosticoIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = _filtrar_campos_diag(body.model_dump(exclude_none=True))
    data["terapeuta_id"] = terapeuta_id
    if not data.get("sessao_data"):
        data["sessao_data"] = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("diagnosticos_alquimicos").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/diagnosticos/{diagnostico_id}", summary="Editar diagnóstico")
async def editar_diagnostico(diagnostico_id: str, body: DiagnosticoUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = _filtrar_campos_diag(body.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    res = sb.table("diagnosticos_alquimicos").update(data).eq("id", diagnostico_id).eq("terapeuta_id", terapeuta_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Diagnóstico não encontrado.")
    return res.data[0]


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
    import asyncio
    settings = get_settings()
    # Usa AsyncAnthropic para não bloquear o event loop do FastAPI
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    resposta = await client.messages.create(
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
    data = body.model_dump(exclude_unset=True)
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


@router.get("/acompanhamentos/agenda", summary="Agenda dos próximos 7 dias + atrasados")
async def get_agenda(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    hoje = datetime.now(timezone.utc).date()
    em_7_dias = (hoje + timedelta(days=7)).isoformat()

    # Buscar pendentes: atrasados (sem limite inferior) + próximos 7 dias
    res = sb.table("acompanhamentos").select("*, pacientes(nome, numero_telefone)").eq("terapeuta_id", terapeuta_id).eq("status", "pendente").lte("data_prevista", em_7_dias).order("data_prevista").execute()

    # Agrupar por data e ordenar itens por hora_prevista
    agenda: dict = {}
    for a in (res.data or []):
        data = a.get("data_prevista") or "sem_data"
        if data not in agenda:
            agenda[data] = []
        agenda[data].append(a)

    # Ordenar itens dentro de cada dia por hora_prevista
    for data in agenda:
        agenda[data].sort(key=lambda x: x.get("hora_prevista") or "23:59")

    return {"agenda": agenda, "hoje": hoje.isoformat()}


_ACOMP_COLS_DB = {
    "id", "terapeuta_id", "paciente_id", "tipo", "descricao",
    "data_prevista", "hora_prevista", "data_realizado", "status", "prioridade",
}


@router.post("/acompanhamentos", summary="Criar acompanhamento")
async def criar_acompanhamento(body: AcompanhamentoIn, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ACOMP_COLS_DB}
    data["terapeuta_id"] = terapeuta_id
    res = sb.table("acompanhamentos").insert(data).execute()
    return res.data[0] if res.data else {}


@router.put("/acompanhamentos/{acomp_id}", summary="Atualizar acompanhamento")
async def atualizar_acompanhamento(acomp_id: str, body: AcompanhamentoUpdate, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    data = body.model_dump(exclude_unset=True)
    data["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    if data.get("status") == "realizado" and not data.get("data_realizado"):
        data["data_realizado"] = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("acompanhamentos").update(data).eq("id", acomp_id).eq("terapeuta_id", terapeuta_id).execute()
    return res.data[0] if res.data else {}


# ─── CONVERSAS WHATSAPP ──────────────────────────────────────────────────────

@router.get("/conversas", summary="Todas as conversas do terapeuta (agrupáveis por paciente)")
async def listar_conversas(
    authorization: str = Header(...),
    limite: int = Query(200, ge=1, le=500),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Buscar conversas com join de pacientes para obter o nome
    res = (
        sb.table("conversas")
        .select("id, paciente_numero, mensagem_paciente, resposta_agente, intencao, criado_em")
        .eq("terapeuta_id", terapeuta_id)
        .order("criado_em", desc=True)
        .limit(limite)
        .execute()
    )

    # Enriquecer com nomes de pacientes
    conversas = res.data or []
    numeros = list(set(c["paciente_numero"] for c in conversas if c.get("paciente_numero")))
    nomes_map = {}
    if numeros:
        pac_res = sb.table("pacientes").select("numero_telefone, nome").eq("terapeuta_id", terapeuta_id).in_("numero_telefone", numeros).execute()
        for p in (pac_res.data or []):
            nomes_map[p["numero_telefone"]] = p["nome"]

    for c in conversas:
        c["paciente_nome"] = nomes_map.get(c["paciente_numero"], c["paciente_numero"])

    return {"conversas": conversas}


# ─── MAPAS NATAIS ────────────────────────────────────────────────────────────

@router.get("/mapas", summary="Galeria de mapas natais")
async def listar_mapas(
    authorization: str = Header(...),
    paciente_id: str = Query(""),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Se paciente_id fornecido, buscar número do paciente
    numeros = None
    if paciente_id:
        pac = sb.table("pacientes").select("numero_telefone").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
        if pac.data:
            numeros = [pac.data[0]["numero_telefone"]]

    # Buscar TODOS os mapas do terapeuta (via terapeuta_id direto)
    offset = (pagina - 1) * por_pagina
    q = sb.table("mapas_astrais").select("id, numero_telefone, nome, data_nascimento, hora_nascimento, cidade_nascimento, mapa_json, imagem_url, tipo_mapa, criado_em").eq("terapeuta_id", terapeuta_id)
    if numeros:
        # Filtro por paciente específico: busca por numero OU nome
        pac_nome = None
        if paciente_id:
            pac2 = sb.table("pacientes").select("nome").eq("id", paciente_id).limit(1).execute()
            pac_nome = pac2.data[0]["nome"] if pac2.data else None
        if pac_nome:
            q = q.or_(f"numero_telefone.in.({','.join(numeros)}),nome.eq.{pac_nome}")
        else:
            q = q.in_("numero_telefone", numeros)
    res = q.order("criado_em", desc=True).range(offset, offset + por_pagina - 1).execute()

    mapas = res.data or []
    for m in mapas:
        m["nome_paciente"] = m.get("nome") or m.get("numero_telefone", "")

    return {"mapas": mapas, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/mapas/{mapa_id}", summary="Detalhes de um mapa natal")
async def get_mapa(mapa_id: str, authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    # SEGURANÇA: filtra por terapeuta_id para impedir acesso cross-tenant
    res = sb.table("mapas_astrais").select("*").eq("id", mapa_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
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
        "conversas_mes": conv_mes.count or 0,
        "diagnosticos_mes": diag_mes.count or 0,
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
    mapas = sb.table("mapas_astrais").select("data_nascimento, imagem_url, tipo_mapa, criado_em").eq("numero_telefone", numero).execute()
    conv_count = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("paciente_numero", numero).execute()

    # Resumo de florais usados
    todos_florais: list = []
    for d in (diag.data or []):
        todos_florais.extend(d.get("florais_prescritos") or [])
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
    body: AlterarSenhaIn,
    authorization: str = Header(...),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    if not body.nova_senha or len(body.nova_senha) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 8 caracteres.")

    sb = get_supabase()

    # Verificar senha atual antes de permitir alteração
    auth_res = sb.table("portal_auth").select("senha_hash").eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not auth_res.data or not _verificar_senha(body.senha_atual, auth_res.data[0]["senha_hash"]):
        raise HTTPException(status_code=401, detail="Senha atual incorreta.")

    senha_hash = bcrypt.hashpw(body.nova_senha.encode(), bcrypt.gensalt()).decode()
    sb.table("portal_auth").update({"senha_hash": senha_hash}).eq("terapeuta_id", terapeuta_id).execute()
    return {"ok": True}


@router.put("/configuracoes", summary="Atualizar configurações do terapeuta (nome, nome_agente)")
async def atualizar_configuracoes(
    body: dict,
    authorization: str = Header(...),
):
    terapeuta_id = _get_terapeuta_id(authorization)
    campos_permitidos = {"nome", "nome_agente", "tom_de_voz", "contato_agendamento",
                         "horario_atendimento", "telefone", "foto_url",
                         "horario_inicio", "horario_fim", "mensagem_boas_vindas"}
    update_data = {k: v for k, v in body.items() if k in campos_permitidos and v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualizar.")

    sb = get_supabase()
    sb.table("terapeutas").update(update_data).eq("id", terapeuta_id).execute()
    return {"ok": True}


@router.get("/assinatura", summary="Informações da assinatura do terapeuta")
async def obter_assinatura(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    try:
        res = sb.table("codigos_liberacao").select("*").eq("terapeuta_id", terapeuta_id).eq("ativo", True).order("criado_em", desc=True).limit(1).execute()
        if res.data:
            codigo = res.data[0]
            return {
                "status": codigo.get("status_assinatura", "disponivel"),
                "valor": 297,
                "plano": "Mensal",
                "codigo": codigo.get("codigo"),
                "meses_contratados": codigo.get("meses_contratados", 1),
                "criado_em": codigo.get("criado_em"),
                "pagamentos": []
            }
    except Exception:
        pass
    # Fallback trial
    return {"status": "trial", "valor": 297, "dias_restantes": 7, "pagamentos": []}


@router.get("/documentos", summary="Lista documentos indexados do terapeuta")
async def listar_documentos(authorization: str = Header(...)):
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    res = sb.table("documentos").select("id, nome_arquivo, status, total_chunks, criado_em").eq("terapeuta_id", terapeuta_id).order("criado_em", desc=True).execute()
    return res.data or []


# ─── ANÁLISE DE ELEMENTOS ────────────────────────────────────────────────────

@router.get("/pacientes/{paciente_id}/analise-elementos", summary="Análise agregada de elementos do paciente")
async def analise_elementos(paciente_id: str, authorization: str = Header(...)):
    """Retorna análise agregada de elementos, substâncias, tendência e alertas
    calculados a partir de todos os diagnósticos do paciente."""
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Verificar paciente pertence ao terapeuta
    pac_res = sb.table("pacientes").select("id, nome").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

    # Buscar todos os diagnósticos ordenados por data
    diag_res = sb.table("diagnosticos_alquimicos").select("*").eq("paciente_id", paciente_id).eq("terapeuta_id", terapeuta_id).order("sessao_data").execute()
    diagnosticos = diag_res.data or []

    if not diagnosticos:
        return {
            "paciente_id": paciente_id,
            "ultimo_diagnostico": None,
            "elementos_atuais": {},
            "substancias_atuais": {},
            "tendencia": "sem_dados",
            "alertas": [],
            "historico_elementos": [],
        }

    ultimo = diagnosticos[-1]

    # Elementos atuais (do último diagnóstico)
    elementos_atuais = ultimo.get("elementos_detalhes") or {}

    # Substâncias atuais — usar do diagnóstico se disponível, senão calcular
    substancias_atuais = ultimo.get("substancias") or {}
    if not substancias_atuais and elementos_atuais:
        terra = elementos_atuais.get("Terra", elementos_atuais.get("terra", 0))
        fogo = elementos_atuais.get("Fogo", elementos_atuais.get("fogo", 0))
        ar = elementos_atuais.get("Ar", elementos_atuais.get("ar", 0))
        agua = elementos_atuais.get("Água", elementos_atuais.get("agua", 0))
        todos_vals = [terra, fogo, ar, agua]
        avg_all = sum(todos_vals) / 4 if todos_vals else 0
        substancias_atuais = {
            "enxofre": round((terra + fogo) / 2, 1),
            "sal": round(avg_all, 1),
            "mercurio": round((ar + agua) / 2, 1),
        }

    # Histórico de elementos por data
    historico_elementos = []
    for d in diagnosticos:
        detalhes = d.get("elementos_detalhes") or {}
        if detalhes:
            entry = {"data": d.get("sessao_data") or ""}
            entry.update(detalhes)
            historico_elementos.append(entry)

    # Tendência — comparar último com penúltimo (ou primeiro se só 2)
    alertas: list[str] = []
    tendencia = "estavel"

    if len(diagnosticos) >= 2:
        anterior = diagnosticos[-2]
        el_anterior = anterior.get("elementos_detalhes") or {}
        el_atual = elementos_atuais

        # Verificar variação > 20% entre consultas (surto)
        surto_detectado = False
        for chave in set(list(el_anterior.keys()) + list(el_atual.keys())):
            val_ant = el_anterior.get(chave, 0)
            val_atual = el_atual.get(chave, 0)
            if val_ant > 0 and abs(val_atual - val_ant) / val_ant > 0.20:
                surto_detectado = True
                if val_atual > val_ant:
                    alertas.append(f"Excesso de {chave} detectado (+{round(val_atual - val_ant)}%)")
                else:
                    alertas.append(f"Falta de {chave} crítica ({round(val_atual - val_ant)}%)")

        # Usar progresso_status do último diagnóstico se disponível
        if ultimo.get("progresso_status"):
            tendencia = ultimo["progresso_status"]
        elif surto_detectado:
            tendencia = "surto"
        else:
            # Heurística: se elemento carente mudou para dominante, progresso
            if (anterior.get("elemento_carente") and
                anterior["elemento_carente"] != ultimo.get("elemento_carente")):
                tendencia = "progredindo"

    return {
        "paciente_id": paciente_id,
        "ultimo_diagnostico": ultimo,
        "elementos_atuais": elementos_atuais,
        "substancias_atuais": substancias_atuais,
        "tendencia": tendencia,
        "alertas": alertas,
        "historico_elementos": historico_elementos,
    }


# ─── PROGRESSO ───────────────────────────────────────────────────────────────

@router.get("/pacientes/{paciente_id}/progresso", summary="Progressão do paciente ao longo dos diagnósticos")
async def progresso_paciente(paciente_id: str, authorization: str = Header(...)):
    """Compara primeiro diagnóstico vs último e detecta padrões de regressão."""
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()

    # Verificar paciente
    pac_res = sb.table("pacientes").select("id, nome").eq("id", paciente_id).eq("terapeuta_id", terapeuta_id).limit(1).execute()
    if not pac_res.data:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

    # Buscar diagnósticos ordenados por data
    diag_res = sb.table("diagnosticos_alquimicos").select("*").eq("paciente_id", paciente_id).eq("terapeuta_id", terapeuta_id).order("sessao_data").execute()
    diagnosticos = diag_res.data or []

    if not diagnosticos:
        return {
            "paciente_id": paciente_id,
            "total_diagnosticos": 0,
            "primeiro": None,
            "ultimo": None,
            "evolucao_elementos": {},
            "evolucao_serpentes": {},
            "evolucao_dna": {},
            "padroes_regressao": [],
            "resumo": "Nenhum diagnóstico registrado.",
        }

    primeiro = diagnosticos[0]
    ultimo = diagnosticos[-1]

    # Evolução de elementos
    el_primeiro = primeiro.get("elementos_detalhes") or {}
    el_ultimo = ultimo.get("elementos_detalhes") or {}
    evolucao_elementos = {}
    for chave in set(list(el_primeiro.keys()) + list(el_ultimo.keys())):
        val_ini = el_primeiro.get(chave, 0)
        val_fim = el_ultimo.get(chave, 0)
        evolucao_elementos[chave] = {
            "inicial": val_ini,
            "atual": val_fim,
            "variacao": round(val_fim - val_ini, 1),
        }

    # Evolução de serpentes (ativas → resolvidas?)
    serp_primeiro = set(primeiro.get("serpentes_ativas") or [])
    serp_ultimo = set(ultimo.get("serpentes_ativas") or [])
    evolucao_serpentes = {
        "resolvidas": list(serp_primeiro - serp_ultimo),
        "persistentes": list(serp_primeiro & serp_ultimo),
        "novas": list(serp_ultimo - serp_primeiro),
    }

    # Evolução de DNA comprometido
    dna_primeiro = set(primeiro.get("dna_comprometido") or [])
    dna_ultimo = set(ultimo.get("dna_comprometido") or [])
    evolucao_dna = {
        "resolvidos": list(dna_primeiro - dna_ultimo),
        "persistentes": list(dna_primeiro & dna_ultimo),
        "novos": list(dna_ultimo - dna_primeiro),
    }

    # Detectar padrões de regressão
    padroes_regressao: list[str] = []
    if len(diagnosticos) >= 3:
        # Verificar se serpentes que sumiram voltaram
        for i in range(1, len(diagnosticos) - 1):
            serp_meio = set(diagnosticos[i].get("serpentes_ativas") or [])
            resolvidas_no_meio = serp_primeiro - serp_meio
            retornaram = resolvidas_no_meio & serp_ultimo
            if retornaram:
                padroes_regressao.append(f"Serpentes retornaram após resolução: {', '.join(retornaram)}")

        # Verificar se progresso_status indica regressão consecutiva
        ultimos_status = [d.get("progresso_status") for d in diagnosticos[-3:] if d.get("progresso_status")]
        if ultimos_status.count("regredindo") >= 2:
            padroes_regressao.append("Regressão detectada em 2+ diagnósticos consecutivos recentes")

    # Resumo textual
    total = len(diagnosticos)
    if total == 1:
        resumo = "Apenas 1 diagnóstico registrado. Necessário mais dados para avaliar progressão."
    elif evolucao_serpentes["resolvidas"] and not evolucao_serpentes["novas"]:
        resumo = f"Progresso positivo: {len(evolucao_serpentes['resolvidas'])} serpente(s) resolvida(s), nenhuma nova."
    elif evolucao_serpentes["novas"]:
        resumo = f"Atenção: {len(evolucao_serpentes['novas'])} serpente(s) nova(s) desde o início."
    else:
        resumo = f"Acompanhamento com {total} diagnósticos. Padrão estável."

    return {
        "paciente_id": paciente_id,
        "total_diagnosticos": total,
        "primeiro": primeiro,
        "ultimo": ultimo,
        "evolucao_elementos": evolucao_elementos,
        "evolucao_serpentes": evolucao_serpentes,
        "evolucao_dna": evolucao_dna,
        "padroes_regressao": padroes_regressao,
        "resumo": resumo,
    }


# ─── FINANCEIRO ──────────────────────────────────────────────────────────────

@router.get("/financeiro/resumo", summary="Resumo financeiro do terapeuta")
async def financeiro_resumo(authorization: str = Header(...)):
    """Retorna contagens de pacientes ativos, diagnósticos do mês e receita estimada."""
    terapeuta_id = _get_terapeuta_id(authorization)
    sb = get_supabase()
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Pacientes ativos
    pac_res = sb.table("pacientes").select("id", count="exact").eq("terapeuta_id", terapeuta_id).eq("status", "ativo").execute()
    pacientes_ativos = pac_res.count or 0

    # Diagnósticos este mês
    diag_res = sb.table("diagnosticos_alquimicos").select("id", count="exact").eq("terapeuta_id", terapeuta_id).gte("criado_em", inicio_mes.isoformat()).execute()
    diagnosticos_mes = diag_res.count or 0

    # Conversas este mês
    conv_res = sb.table("conversas").select("id", count="exact").eq("terapeuta_id", terapeuta_id).gte("criado_em", inicio_mes.isoformat()).execute()
    conversas_mes = conv_res.count or 0

    # Informações de assinatura (se existir tabela)
    assinatura = None
    try:
        assin_res = sb.table("assinaturas").select("*").eq("terapeuta_id", terapeuta_id).eq("status", "ativa").limit(1).execute()
        if assin_res.data:
            assinatura = assin_res.data[0]
    except Exception:
        pass  # Tabela pode não existir ainda

    # Receita estimada (R$197-297 por terapeuta/mês — base do modelo de negócio)
    valor_plano = 197.0
    if assinatura:
        valor_plano = assinatura.get("valor", 197.0)

    return {
        "terapeuta_id": terapeuta_id,
        "periodo": {
            "inicio": inicio_mes.date().isoformat(),
            "fim": agora.date().isoformat(),
        },
        "pacientes_ativos": pacientes_ativos,
        "diagnosticos_mes": diagnosticos_mes,
        "conversas_mes": conversas_mes,
        "assinatura": assinatura,
        "receita_estimada": valor_plano,
        "custo_estimado_ia": round(conversas_mes * 0.005, 2),  # ~R$0.005 por conversa
        "margem_estimada": round(valor_plano - (conversas_mes * 0.005), 2),
    }


def agora_utc_str() -> str:
    return datetime.now(timezone.utc).isoformat()
