"""
Cliente Supabase singleton.
Garante uma única conexão reutilizada em toda a aplicação.
"""

from supabase import Client, create_client

from src.core.config import get_settings

# Variável global para o cliente singleton
_supabase_client: Client | None = None


def get_supabase() -> Client:
    """
    Retorna o cliente Supabase singleton.
    Cria a conexão na primeira chamada e reutiliza nas seguintes.
    """
    global _supabase_client

    if _supabase_client is None:
        settings = get_settings()

        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_URL e SUPABASE_SERVICE_KEY precisam estar configurados no .env"
            )

        _supabase_client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_KEY,
        )

    return _supabase_client
