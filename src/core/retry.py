"""
Decorator reutilizavel de retry com backoff exponencial.

Uso:
    from src.core.retry import retry_async

    @retry_async(max_tentativas=3, delay_base=1.0, delay_max=30.0, excecoes=(HTTPError,))
    async def minha_funcao():
        ...

Ou diretamente:
    resultado = await retry_async(max_tentativas=3)(minha_funcao)(args)
"""

import asyncio
import functools
import logging
from typing import Callable, Type

logger = logging.getLogger(__name__)


def retry_async(
    max_tentativas: int = 3,
    delay_base: float = 1.0,
    delay_max: float = 30.0,
    excecoes: tuple[Type[BaseException], ...] = (Exception,),
    nome_operacao: str | None = None,
) -> Callable:
    """
    Decorator para retry assincrono com backoff exponencial.

    O delay entre tentativas segue a formula: min(delay_base * 2^(tentativa-1), delay_max).
    Exemplo com delay_base=1.0: 1s, 2s, 4s, 8s, 16s...

    Args:
        max_tentativas: Numero maximo de tentativas (incluindo a primeira).
        delay_base: Delay inicial em segundos antes do primeiro retry.
        delay_max: Delay maximo em segundos (cap do backoff exponencial).
        excecoes: Tupla de tipos de excecao que devem ser retentados.
            Excecoes fora desta lista sao propagadas imediatamente.
        nome_operacao: Nome legivel da operacao para logs. Se None, usa o
            nome da funcao decorada.

    Returns:
        Decorator que envolve a funcao async com logica de retry.

    Raises:
        A ultima excecao capturada se todas as tentativas falharem.
    """
    def decorator(func: Callable) -> Callable:
        op_name = nome_operacao or func.__qualname__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            ultima_excecao: BaseException | None = None

            for tentativa in range(1, max_tentativas + 1):
                try:
                    return await func(*args, **kwargs)
                except excecoes as e:
                    ultima_excecao = e

                    if tentativa >= max_tentativas:
                        logger.error(
                            f"[RETRY] {op_name} falhou apos {max_tentativas} tentativas. "
                            f"Ultimo erro: {type(e).__name__}: {e}"
                        )
                        raise

                    # Backoff exponencial com cap
                    delay = min(delay_base * (2 ** (tentativa - 1)), delay_max)
                    logger.warning(
                        f"[RETRY] {op_name} — tentativa {tentativa}/{max_tentativas} falhou "
                        f"({type(e).__name__}: {e}). Retry em {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

            # Seguranca: nunca deveria chegar aqui, mas garante que nao retorna None silenciosamente
            if ultima_excecao:
                raise ultima_excecao
            raise RuntimeError(f"[RETRY] {op_name} — estado inesperado apos {max_tentativas} tentativas")

        return wrapper
    return decorator
