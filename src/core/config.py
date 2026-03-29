"""
Configurações centrais da aplicação.
Carrega variáveis de ambiente do arquivo .env usando pydantic-settings.
"""

import logging
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Caminho absoluto do .env (raiz do projeto)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

# Forçar carregamento do .env nas variáveis de ambiente
load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    """
    Configurações da aplicação carregadas automaticamente do .env.
    Todos os campos são obrigatórios em produção.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- Claude API (LLM principal) ---
    ANTHROPIC_API_KEY: str = ""

    # --- OpenAI (apenas para embeddings) ---
    OPENAI_API_KEY: str = ""

    # --- Supabase (banco de dados + storage + pgvector) ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # --- Evolution API (WhatsApp) ---
    EVOLUTION_API_URL: str = ""
    EVOLUTION_API_KEY: str = ""

    # --- Meta WhatsApp Cloud API (alternativa à Evolution API) ---
    META_WHATSAPP_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_BUSINESS_ID: str = ""
    META_VERIFY_TOKEN: str = ""

    # --- Asaas (cobrança e pagamentos) ---
    ASAAS_API_KEY: str = ""
    # Token de validação dos webhooks do Asaas (configure no painel Asaas → Webhooks)
    ASAAS_WEBHOOK_TOKEN: str = ""

    # --- Controle de acesso ---
    # Contato exibido ao usuário quando o chat é bloqueado
    CONTATO_ADMIN: str = "https://wa.me/5511999999999"

    # --- Aplicação ---
    SECRET_KEY: str = "trocar-em-producao"
    DATABASE_URL: str = ""

    # --- CORS ---
    # Origens permitidas separadas por vírgula. Use "*" para desenvolvimento.
    # Em produção, restringir para o(s) domínio(s) do painel/portal.
    # Ex: "https://meusite.com,https://portal.meusite.com"
    ALLOWED_ORIGINS: str = "*"

    # --- Configurações do agente ---
    # Modelo Claude usado para respostas
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    # Modelo de embedding da OpenAI
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Dimensão dos vetores de embedding
    EMBEDDING_DIMENSION: int = 1536
    # Quantidade de chunks retornados na busca vetorial
    RAG_TOP_K: int = 5
    # Tamanho máximo de cada chunk (em tokens aproximados)
    CHUNK_SIZE: int = 500
    # Sobreposição entre chunks
    CHUNK_OVERLAP: int = 50


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna instância singleton das configurações.
    Usa lru_cache para garantir que só carrega uma vez.
    """
    return Settings()


def check_startup_config() -> None:
    """
    Verifica configurações críticas na inicialização e emite warnings.
    Não interrompe a execução — apenas avisa sobre problemas potenciais.
    """
    settings = get_settings()

    # Chaves obrigatórias para funcionamento básico
    required = {
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "SUPABASE_URL": settings.SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": settings.SUPABASE_SERVICE_KEY,
    }
    for name, value in required.items():
        if not value:
            logger.warning("CONFIG: %s não configurada — funcionalidades dependentes falharão", name)

    # Chaves importantes (uma ou outra deve estar configurada)
    tem_evolution = bool(settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY)
    tem_meta = bool(settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID)
    if not tem_evolution and not tem_meta:
        logger.warning("CONFIG: nenhuma integração WhatsApp configurada (Evolution API ou Meta Cloud API)")

    # SECRET_KEY padrão é insegura em produção
    if settings.SECRET_KEY == "trocar-em-producao":
        logger.warning(
            "CONFIG: SECRET_KEY está com o valor padrão 'trocar-em-producao'. "
            "Defina uma chave forte no .env antes de ir para produção."
        )

    # CORS aberto demais
    if settings.ALLOWED_ORIGINS == "*":
        logger.info("CONFIG: ALLOWED_ORIGINS=* (aberto). Em produção, defina os domínios no .env.")
