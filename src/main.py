"""
Aplicação principal FastAPI — Terapeutas Agent.
Agente de IA no WhatsApp com base de conhecimento para terapeutas.
"""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import check_startup_config, get_settings
from src.api.webhook import router as webhook_router
from src.api.asaas_webhook import router as asaas_webhook_router
from src.api.terapeutas import router as terapeutas_router
from src.api.documentos import router as documentos_router
from src.api.teste import router as teste_router
from src.api.dashboard import router as dashboard_router
from src.api.evolution import router as evolution_router
from src.api.automation_router import router as automation_router
from src.api.portal import router as portal_router
from src.api.checkout import router as checkout_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Executa na inicialização e no encerramento do servidor.
    """
    settings = get_settings()
    print("=" * 50)
    print("  Terapeutas Agent - Iniciando...")
    print(f"  Modelo LLM: {settings.CLAUDE_MODEL}")
    print(f"  Modelo Embedding: {settings.EMBEDDING_MODEL}")
    print(f"  RAG Top K: {settings.RAG_TOP_K}")
    print("=" * 50)

    # Verifica configurações críticas e emite warnings no log
    check_startup_config()

    yield  # Aplicação rodando

    print("Terapeutas Agent - Encerrando...")


# Cria a aplicação FastAPI
app = FastAPI(
    title="Terapeutas Agent API",
    description=(
        "API do agente de IA no WhatsApp para terapeutas. "
        "Responde pacientes com base nos materiais (PDFs) do terapeuta."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Configuração de CORS — origens controladas via ALLOWED_ORIGINS no .env
# Em produção: ALLOWED_ORIGINS=https://meusite.com,https://portal.meusite.com
_settings = get_settings()
_allowed_origins = (
    ["*"]
    if _settings.ALLOWED_ORIGINS.strip() == "*"
    else [o.strip() for o in _settings.ALLOWED_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================
# ROTAS
# =============================================

@app.get("/", tags=["Sistema"])
async def health_check():
    """
    Health check — verifica se a API está rodando.
    Usado por Railway/monitoramento para confirmar que o serviço está ativo.
    """
    return {
        "status": "ok",
        "servico": "Terapeutas Agent API",
        "versao": "0.1.0",
        "build": "feat-ceo-improvements-v2",
    }


@app.get("/config", tags=["Sistema"])
async def verificar_config(x_admin_token: str = Header(default="")):
    """
    Verifica quais configurações estão preenchidas (sem expor valores sensíveis).
    PROTEGIDO: requer SECRET_KEY no header X-Admin-Token.
    Útil para debug durante setup.
    """
    settings = get_settings()

    # SEGURANÇA: requer autenticação para não expor info do sistema
    if not x_admin_token or x_admin_token != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Token admin inválido.")

    # Asaas: chave válida começa com '$aact_' (produção) ou '$aaah_' (sandbox)
    asaas_key = settings.ASAAS_API_KEY
    asaas_key_valida = bool(asaas_key and (asaas_key.startswith("$aact_") or asaas_key.startswith("$aaah_")))

    return {
        "anthropic_key_presente": bool(settings.ANTHROPIC_API_KEY),
        "openai_key_presente": bool(settings.OPENAI_API_KEY),
        "supabase_configurado": bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY),
        "evolution_configurado": bool(settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY),
        "meta_cloud_configurado": bool(settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID),
        "asaas_key_presente": bool(asaas_key),
        "asaas_key_valida": asaas_key_valida,
        "modelo_llm": settings.CLAUDE_MODEL,
        "modelo_embedding": settings.EMBEDDING_MODEL,
    }


# Registrar routers (cada um já define seu próprio prefix internamente)
app.include_router(webhook_router)
app.include_router(asaas_webhook_router)
app.include_router(terapeutas_router)
app.include_router(documentos_router)
app.include_router(teste_router)
app.include_router(dashboard_router)
app.include_router(evolution_router)
app.include_router(automation_router)
app.include_router(portal_router)
app.include_router(checkout_router)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@app.get("/chat", tags=["Teste"])
async def chat_page():
    """Serve a pagina de chat de teste."""
    return FileResponse(_PROJECT_ROOT / "chat.html")


@app.get("/dashboard", tags=["Dashboard"])
async def dashboard_page():
    """Serve a página do dashboard de BI."""
    return FileResponse(_PROJECT_ROOT / "dashboard.html")


@app.get("/admin", tags=["Admin"])
async def admin_page():
    """Serve o painel administrativo do CEO."""
    return FileResponse(_PROJECT_ROOT / "admin.html")


@app.get("/landing", tags=["Marketing"])
async def landing_page():
    """Serve a landing page de vendas."""
    return FileResponse(_PROJECT_ROOT / "landing.html")


@app.get("/checkout", tags=["Checkout"])
async def checkout_page():
    """Serve a página de checkout."""
    return FileResponse(_PROJECT_ROOT / "portal-vercel" / "checkout.html")


@app.get("/obrigado", tags=["Checkout"])
async def obrigado_page():
    """Serve a página de obrigado pós-pagamento."""
    return FileResponse(_PROJECT_ROOT / "portal-vercel" / "obrigado.html")


@app.get("/portal", tags=["Portal"])
async def portal_page_root():
    """Serve o portal do terapeuta (SPA)."""
    return FileResponse(_PROJECT_ROOT / "portal-vercel" / "index.html")


@app.get("/portal/{path:path}", tags=["Portal"])
async def portal_page(path: str = ""):
    """Serve o portal do terapeuta para todas as rotas de navegação SPA."""
    return FileResponse(_PROJECT_ROOT / "portal-vercel" / "index.html")
