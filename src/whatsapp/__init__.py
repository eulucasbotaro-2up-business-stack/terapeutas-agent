"""
Módulo de integração WhatsApp via Evolution API v2.

Exporta o cliente da API e utilitários de mensagens.
"""

from src.whatsapp.evolution import EvolutionClient, EvolutionAPIError
from src.whatsapp.messages import (
    extrair_numero_mensagem,
    eh_mensagem_valida,
    formatar_agendamento,
    formatar_aviso_audio,
    formatar_boas_vindas,
    formatar_encaminhamento,
    formatar_fora_escopo,
    formatar_urgencia,
)

__all__ = [
    "EvolutionClient",
    "EvolutionAPIError",
    "extrair_numero_mensagem",
    "eh_mensagem_valida",
    "formatar_agendamento",
    "formatar_aviso_audio",
    "formatar_boas_vindas",
    "formatar_encaminhamento",
    "formatar_fora_escopo",
    "formatar_urgencia",
]
