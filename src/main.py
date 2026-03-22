"""
Aplicação principal FastAPI — Terapeutas Agent.
Agente de IA no WhatsApp com base de conhecimento para terapeutas.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.api.webhook import router as webhook_router
from src.api.terapeutas import router as terapeutas_router
from src.api.documentos import router as documentos_router


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
        "asaas_configurado": bool(settings.ASAAS_API_KEY),
        "modelo_llm": settings.CLAUDE_MODEL,
        "modelo_embedding": settings.EMBEDDING_MODEL,
    }


# Registrar routers (cada um já define seu próprio prefix internamente)
app.include_router(webhook_router)
app.include_router(terapeutas_router)
app.include_router(documentos_router)
