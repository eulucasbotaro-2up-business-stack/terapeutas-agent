"""
Módulo de integração WhatsApp via Evolution API v2 e Meta WhatsApp Cloud API.

Exporta os clientes das APIs e utilitários de mensagens.
"""

from src.whatsapp.evolution import EvolutionClient, EvolutionAPIError
from src.whatsapp.meta_cloud import MetaCloudClient, MetaCloudAPIError
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
    "MetaCloudClient",
    "MetaCloudAPIError",
    "extrair_numero_mensagem",
    "eh_mensagem_valida",
    "formatar_agendamento",
    "formatar_aviso_audio",
    "formatar_boas_vindas",
    "formatar_encaminhamento",
    "formatar_fora_escopo",
    "formatar_urgencia",
]
