"""
Rate limiting para Meta WhatsApp Cloud API.

Regras oficiais da Meta (2025-2026):
- Limite global de throughput: 80 msg/s (tier padrão)
- Limite por usuário: 1 mensagem a cada 6 segundos (mínimo oficial)
- Recomendado pela Meta: buffer conservador de 15s para templates
- Para respostas sequenciais dentro de uma conversa: 3s de segurança

Referência:
https://developers.facebook.com/docs/whatsapp/throughput
https://developers.facebook.com/docs/whatsapp/messaging-limits/

Este módulo centraliza o controle de envio para evitar ban ou
degradação do quality rating.
"""

import asyncio
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Intervalo mínimo entre mensagens para o MESMO número (segundos)
# Oficial: 6s | Nosso buffer: 3s para respostas sequenciais (chat normal)
MIN_INTERVAL_SEQUENTIAL_S = 3.0

# Intervalo para mensagens isoladas (não sequenciais) — buffer conservador
MIN_INTERVAL_STANDALONE_S = 6.0


class _PerUserRateLimiter:
    """
    Rate limiter por número de telefone.
    Garante que não enviamos mensagens rápido demais para o mesmo usuário.
    Thread-safe via asyncio.Lock por usuário.

    NOTA: asyncio.Lock deve ser criado no event loop ativo — por isso usamos
    um dict simples em vez de defaultdict(asyncio.Lock), que criaria os locks
    fora do loop e causaria DeprecationWarning em Python 3.10+ / falha em 3.12+.
    """

    def __init__(self):
        self._last_sent: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = {}

    async def aguardar(self, numero: str, intervalo: float = MIN_INTERVAL_SEQUENTIAL_S) -> None:
        """
        Aguarda o tempo necessário antes de enviar para este número.
        Atualiza o timestamp ao sair (reserva o slot).

        Args:
            numero: Número de destino (formato internacional).
            intervalo: Intervalo mínimo desejado em segundos.
        """
        # Cria o Lock sob demanda dentro de uma coroutine (garante event loop correto)
        if numero not in self._locks:
            self._locks[numero] = asyncio.Lock()
        lock = self._locks[numero]
        async with lock:
            agora = time.monotonic()
            ultimo = self._last_sent[numero]
            espera = intervalo - (agora - ultimo)

            if espera > 0:
                logger.debug(f"Rate limiter: aguardando {espera:.1f}s antes de enviar para {numero}")
                await asyncio.sleep(espera)

            self._last_sent[numero] = time.monotonic()


# Singleton global
_limiter = _PerUserRateLimiter()


async def aguardar_antes_de_enviar(
    numero: str,
    sequencial: bool = True,
) -> None:
    """
    Ponto de entrada público. Chame antes de cada send_text_message.

    Args:
        numero: Número de destino.
        sequencial: True = mensagem em sequência rápida (3s), False = isolada (6s).
    """
    intervalo = MIN_INTERVAL_SEQUENTIAL_S if sequencial else MIN_INTERVAL_STANDALONE_S
    await _limiter.aguardar(numero, intervalo)
