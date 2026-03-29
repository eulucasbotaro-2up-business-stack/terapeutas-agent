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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import get_settings
from src.api.webhook import router as webhook_router
from src.api.asaas_webhook import router as asaas_webhook_router
from src.api.terapeutas import router as terapeutas_router
from src.api.documentos import router as documentos_router
from src.api.teste import router as teste_router
from src.api.dashboard import router as dashboard_router
from src.api.evolution import router as evolution_router
from src.api.automation_router import router as automation_router
from src.api.portal import router as portal_router


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

# Configuração de CORS — permitir acesso do painel web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restringir para o domínio do painel
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
        "build": "feat-mapas-astrais-cache-db",
    }


@app.get("/config", tags=["Sistema"])
async def verificar_config():
    """
    Verifica quais configurações estão preenchidas (sem expor valores sensíveis).
    Útil para debug durante setup.
    """
    settings = get_settings()
    return {
        "anthropic_configurado": bool(settings.ANTHROPIC_API_KEY),
        "openai_configurado": bool(settings.OPENAI_API_KEY),
        "supabase_configurado": bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY),
        "evolution_configurado": bool(settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY),
        "meta_cloud_configurado": bool(settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID),
        "asaas_configurado": bool(settings.ASAAS_API_KEY),
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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@app.get("/chat", tags=["Teste"])
async def chat_page():
    """Serve a pagina de chat de teste."""
    return FileResponse(_PROJECT_ROOT / "chat.html")


@app.get("/dashboard", tags=["Dashboard"])
async def dashboard_page():
    """Serve a página do dashboard de BI."""
    return FileResponse(_PROJECT_ROOT / "dashboard.html")


@app.get("/landing", tags=["Marketing"])
async def landing_page():
    """Serve a landing page de vendas."""
    return FileResponse(_PROJECT_ROOT / "landing.html")


@app.get("/portal", tags=["Portal"])
async def portal_page_root():
    """Serve o portal do terapeuta (SPA)."""
    return FileResponse(_PROJECT_ROOT / "portal.html")


@app.get("/portal/{path:path}", tags=["Portal"])
async def portal_page(path: str = ""):
    """Serve o portal do terapeuta para todas as rotas de navegação SPA."""
    return FileResponse(_PROJECT_ROOT / "portal.html")
