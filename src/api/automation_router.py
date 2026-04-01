"""
Router de automação — endpoints para cron jobs e ações dos agentes CEO.

Endpoints:
  POST /automation/renovacao/run      → executa campanha de renovação
  POST /automation/reengajamento/run  → executa campanha de reengajamento
  POST /automation/relatorio/diario   → gera e envia relatório CEO
  GET  /automation/status             → saúde do sistema de automação

Segurança: todos os endpoints POST exigem header X-Automation-Token
(configurado via AUTOMATION_SECRET env var)
"""

import logging
import os

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["Automação"])

_AUTOMATION_SECRET = os.getenv("AUTOMATION_SECRET", "")


def _validar_token(x_automation_token: str = Header(default="")) -> None:
    """Valida o token de segurança para endpoints de automação.
    SEGURANÇA: Se AUTOMATION_SECRET não estiver configurado, bloqueia TODOS os requests."""
    if not _AUTOMATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTOMATION_SECRET não configurado. Endpoints de automação desabilitados.",
        )
    if x_automation_token != _AUTOMATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de automação inválido.",
        )


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ResultadoAutomacao(BaseModel):
    ok: bool
    acao: str
    stats: dict


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/renovacao/run",
    response_model=ResultadoAutomacao,
    summary="Executa campanha de renovação",
    description=(
        "Verifica assinaturas expirando em ≤ 15 dias e envia mensagens de renovação. "
        "Deve ser chamado diariamente (cron às 9h)."
    ),
)
async def executar_renovacao(x_automation_token: str = Header(default="")):
    _validar_token(x_automation_token)

    try:
        from src.agents.renovacao import executar_campanha_renovacao
        stats = await executar_campanha_renovacao()
        return ResultadoAutomacao(ok=True, acao="renovacao", stats=stats)
    except Exception as e:
        logger.error(f"[AUTOMATION] Erro ao executar renovação: {e}")
        return ResultadoAutomacao(ok=False, acao="renovacao", stats={"erro": str(e)})


@router.post(
    "/reengajamento/run",
    response_model=ResultadoAutomacao,
    summary="Executa campanha de reengajamento",
    description=(
        "Recupera clientes suspensos ou com assinatura expirada há ≤ 90 dias. "
        "Deve ser chamado diariamente (cron às 10h)."
    ),
)
async def executar_reengajamento(x_automation_token: str = Header(default="")):
    _validar_token(x_automation_token)

    try:
        from src.agents.reengajamento import executar_campanha_reengajamento
        stats = await executar_campanha_reengajamento()
        return ResultadoAutomacao(ok=True, acao="reengajamento", stats=stats)
    except Exception as e:
        logger.error(f"[AUTOMATION] Erro ao executar reengajamento: {e}")
        return ResultadoAutomacao(ok=False, acao="reengajamento", stats={"erro": str(e)})


@router.post(
    "/relatorio/diario",
    summary="Gera relatório CEO diário",
    description=(
        "Gera relatório completo do negócio (MRR, churn, alertas, projeções) "
        "e retorna o texto formatado. Deve ser chamado diariamente (cron às 8h)."
    ),
)
async def gerar_relatorio_diario(
    enviar_whatsapp: bool = False,
    numero_admin: str = "",
    x_automation_token: str = Header(default=""),
):
    _validar_token(x_automation_token)

    try:
        from src.agents.ceo import gerar_relatorio_diario, formatar_relatorio_texto
        relatorio = await gerar_relatorio_diario()
        texto = formatar_relatorio_texto(relatorio)

        # Enviar para admin via WhatsApp se solicitado
        if enviar_whatsapp and numero_admin:
            from src.agents.whatsapp_sender import enviar_mensagem
            await enviar_mensagem(numero_admin, texto)

        return {
            "ok": True,
            "relatorio": relatorio,
            "texto": texto,
        }
    except Exception as e:
        logger.error(f"[AUTOMATION] Erro ao gerar relatório: {e}")
        return {"ok": False, "erro": str(e)}


@router.post(
    "/full/run",
    summary="Executa toda a rotina diária",
    description=(
        "Atalho que executa em sequência: relatório CEO → renovação → reengajamento. "
        "Ideal para configurar um único cron diário."
    ),
)
async def executar_rotina_completa(
    enviar_whatsapp: bool = False,
    numero_admin: str = "",
    x_automation_token: str = Header(default=""),
):
    _validar_token(x_automation_token)

    resultados = {}

    # 1. Relatório CEO
    try:
        from src.agents.ceo import gerar_relatorio_diario, formatar_relatorio_texto
        relatorio = await gerar_relatorio_diario()
        texto = formatar_relatorio_texto(relatorio)
        resultados["relatorio"] = {"ok": True, "mrr": relatorio["mrr_atual"]}

        if enviar_whatsapp and numero_admin:
            from src.agents.whatsapp_sender import enviar_mensagem
            await enviar_mensagem(numero_admin, texto)
    except Exception as e:
        resultados["relatorio"] = {"ok": False, "erro": str(e)}

    # 2. Renovação
    try:
        from src.agents.renovacao import executar_campanha_renovacao
        stats_renov = await executar_campanha_renovacao()
        resultados["renovacao"] = {"ok": True, **stats_renov}
    except Exception as e:
        resultados["renovacao"] = {"ok": False, "erro": str(e)}

    # 3. Reengajamento
    try:
        from src.agents.reengajamento import executar_campanha_reengajamento
        stats_reeng = await executar_campanha_reengajamento()
        resultados["reengajamento"] = {"ok": True, **stats_reeng}
    except Exception as e:
        resultados["reengajamento"] = {"ok": False, "erro": str(e)}

    return {"ok": True, "resultados": resultados}


@router.get(
    "/status",
    summary="Status do sistema de automação",
    description="Retorna contadores rápidos do sistema sem executar nenhuma campanha.",
)
async def status_automacao():
    """Health check rápido sem autenticação."""
    try:
        from src.core.supabase_client import get_supabase
        from datetime import timezone, timedelta
        supabase = get_supabase()
        agora = __import__("datetime").datetime.now(timezone.utc)

        ativos = supabase.table("codigos_liberacao").select("id", count="exact").eq("status_assinatura", "ativo").execute()
        camprenov = supabase.table("campanhas_renovacao").select("id", count="exact").eq("status", "ativa").execute()
        campreeng = supabase.table("campanhas_reengajamento").select("id", count="exact").eq("status", "ativa").execute()

        return {
            "ok": True,
            "clientes_ativos": ativos.count or 0,
            "campanhas_renovacao_ativas": camprenov.count or 0,
            "campanhas_reengajamento_ativas": campreeng.count or 0,
        }
    except Exception as e:
        return {"ok": False, "erro": str(e)}


# ─── Endpoint de Lead (chamado pela landing page) ─────────────────────────────

class LeadIn(BaseModel):
    nome: str
    email: str
    telefone: str = ""
    plano_interesse: str = "terapeuta"
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""


@router.post(
    "/leads",
    summary="Registra lead da landing page",
    description="Salva lead capturado pela landing page e notifica agente Vendedor.",
)
async def registrar_lead(lead: LeadIn):
    """Sem autenticação — chamado publicamente pela landing page."""
    try:
        from src.core.supabase_client import get_supabase
        supabase = get_supabase()

        # Verificar se já existe pelo email
        existente = (
            supabase.table("leads_landing")
            .select("id")
            .eq("email", lead.email)
            .limit(1)
            .execute()
        )

        if existente.data:
            return {"ok": True, "novo": False, "mensagem": "Lead já registrado"}

        supabase.table("leads_landing").insert({
            "nome":            lead.nome,
            "email":           lead.email,
            "telefone":        lead.telefone,
            "plano_interesse": lead.plano_interesse,
            "utm_source":      lead.utm_source,
            "utm_medium":      lead.utm_medium,
            "utm_campaign":    lead.utm_campaign,
            "status":          "novo",
        }).execute()

        logger.info(f"[LEAD] Novo lead: {lead.nome} ({lead.email}) — plano {lead.plano_interesse}")
        return {"ok": True, "novo": True, "mensagem": "Lead registrado com sucesso"}

    except Exception as e:
        logger.error(f"[LEAD] Erro ao registrar lead: {e}")
        return {"ok": False, "mensagem": "Erro ao registrar. Tente novamente."}
