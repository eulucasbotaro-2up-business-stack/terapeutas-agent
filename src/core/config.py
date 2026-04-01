"""
Configuracoes centrais da aplicacao.

Carrega variaveis de ambiente do arquivo .env usando pydantic-settings.
Valida campos obrigatorios na inicializacao e emite warnings para
configuracoes ausentes ou inseguras.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Caminho absoluto do .env (raiz do projeto)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

# Forçar carregamento do .env nas variáveis de ambiente
load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    """
    Configuracoes da aplicacao carregadas automaticamente do .env.

    Campos com default vazio ("") sao opcionais para inicializacao,
    mas obrigatorios em producao — verificados por check_startup_config().

    Validacoes:
    - SUPABASE_URL deve comecar com https://
    - RAG_TOP_K deve estar entre 1 e 20
    - CHUNK_SIZE deve estar entre 100 e 2000
    - EMBEDDING_DIMENSION deve ser positivo
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

    # --- Meta WhatsApp Cloud API (alternativa a Evolution API) ---
    META_WHATSAPP_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_BUSINESS_ID: str = ""
    META_VERIFY_TOKEN: str = ""

    # --- Asaas (cobranca e pagamentos) ---
    ASAAS_API_KEY: str = ""
    # Token de validacao dos webhooks do Asaas (configure no painel Asaas -> Webhooks)
    ASAAS_WEBHOOK_TOKEN: str = ""

    # --- Controle de acesso ---
    # Contato exibido ao usuario quando o chat e bloqueado
    CONTATO_ADMIN: str = "https://wa.me/5511999999999"

    # --- Aplicacao ---
    SECRET_KEY: str = "trocar-em-producao"
    DATABASE_URL: str = ""

    # --- CORS ---
    # Origens permitidas separadas por virgula. Use "*" para desenvolvimento.
    # Em producao, restringir para o(s) dominio(s) do painel/portal.
    # Ex: "https://meusite.com,https://portal.meusite.com"
    ALLOWED_ORIGINS: str = "*"

    # --- Configuracoes do agente ---
    # Modelo Claude usado para respostas
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    # Modelo de embedding da OpenAI
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Dimensao dos vetores de embedding
    EMBEDDING_DIMENSION: int = 1536
    # Quantidade de chunks retornados na busca vetorial (1-20)
    RAG_TOP_K: int = 5
    # Tamanho maximo de cada chunk em tokens aproximados (100-2000)
    CHUNK_SIZE: int = 500
    # Sobreposicao entre chunks
    CHUNK_OVERLAP: int = 50

    # --- Validacoes ---
    @field_validator("SUPABASE_URL")
    @classmethod
    def validar_supabase_url(cls, v: str) -> str:
        """Garante que a URL do Supabase usa HTTPS (quando configurada)."""
        if v and not v.startswith("https://"):
            raise ValueError(f"SUPABASE_URL deve comecar com https:// (recebido: {v[:30]}...)")
        return v

    @field_validator("RAG_TOP_K")
    @classmethod
    def validar_rag_top_k(cls, v: int) -> int:
        """RAG_TOP_K deve estar entre 1 e 20 para evitar buscas excessivas."""
        if not 1 <= v <= 20:
            raise ValueError(f"RAG_TOP_K deve estar entre 1 e 20 (recebido: {v})")
        return v

    @field_validator("CHUNK_SIZE")
    @classmethod
    def validar_chunk_size(cls, v: int) -> int:
        """CHUNK_SIZE deve estar entre 100 e 2000 tokens."""
        if not 100 <= v <= 2000:
            raise ValueError(f"CHUNK_SIZE deve estar entre 100 e 2000 (recebido: {v})")
        return v

    @field_validator("EMBEDDING_DIMENSION")
    @classmethod
    def validar_embedding_dimension(cls, v: int) -> int:
        """EMBEDDING_DIMENSION deve ser positivo."""
        if v <= 0:
            raise ValueError(f"EMBEDDING_DIMENSION deve ser positivo (recebido: {v})")
        return v


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

    # SECRET_KEY padrão é PERIGOSA em produção — qualquer um pode forjar JWTs
    if settings.SECRET_KEY == "trocar-em-producao":
        logger.critical(
            "SEGURANCA: SECRET_KEY está com o valor padrão 'trocar-em-producao'. "
            "QUALQUER PESSOA pode forjar tokens JWT e acessar dados de terapeutas. "
            "Defina uma chave forte no .env IMEDIATAMENTE."
        )

    # CORS aberto demais
    if settings.ALLOWED_ORIGINS == "*":
        logger.info("CONFIG: ALLOWED_ORIGINS=* (aberto). Em produção, defina os domínios no .env.")
