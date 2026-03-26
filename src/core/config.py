"""
Configurações centrais da aplicação.
Carrega variáveis de ambiente do arquivo .env usando pydantic-settings.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # --- Asaas (cobrança e pagamentos) ---
    ASAAS_API_KEY: str = ""

    # --- Aplicação ---
    SECRET_KEY: str = "trocar-em-producao"
    DATABASE_URL: str = ""

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
