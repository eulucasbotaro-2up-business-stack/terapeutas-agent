"""
Cliente Supabase singleton.
Garante uma única conexão reutilizada em toda a aplicação.
Thread-safe via threading.Lock para uso seguro com asyncio.to_thread().
"""

import threading

from supabase import Client, create_client

from src.core.config import get_settings

# Variável global para o cliente singleton
_supabase_client: Client | None = None
_supabase_lock = threading.Lock()


def get_supabase() -> Client:
    """
    Retorna o cliente Supabase singleton.
    Cria a conexão na primeira chamada e reutiliza nas seguintes.
    Thread-safe: usa lock para evitar race conditions com asyncio.to_thread().
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    with _supabase_lock:
        # Double-checked locking: verifica novamente dentro do lock
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
