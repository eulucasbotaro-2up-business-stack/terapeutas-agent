"""
Cliente da Meta WhatsApp Cloud API para envio de mensagens.

Usa a Graph API v22.0 da Meta para enviar mensagens via WhatsApp Business.
Alternativa à Evolution API — integração direta com a Meta, sem servidor intermediário.
"""

import logging
from typing import Any

import httpx

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Configurações de retry e timeout
MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 30.0

# URL base da Graph API da Meta
META_GRAPH_API_URL = "https://graph.facebook.com/v22.0"


class MetaCloudAPIError(Exception):
    """Erro genérico da Meta WhatsApp Cloud API."""

    def __init__(self, status_code: int, detalhe: str) -> None:
        self.status_code = status_code
        self.detalhe = detalhe
        super().__init__(f"Meta Cloud API erro {status_code}: {detalhe}")


class MetaCloudClient:
    """
    Cliente assíncrono para a Meta WhatsApp Cloud API (Graph API v22.0).

    Uso:
        client = MetaCloudClient()
        await client.send_text_message("5511999999999", "Olá!")
    """

    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
    ) -> None:
        """
        Inicializa o cliente. Se access_token/phone_number_id não forem passados,
        carrega das variáveis de ambiente via Settings.
        """
        settings = get_settings()
        self.access_token = access_token or settings.META_WHATSAPP_TOKEN
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID
        self._headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Método interno para requests com retry
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Executa request HTTP com retry simples (máximo 3 tentativas).
        Loga cada tentativa e levanta MetaCloudAPIError em caso de falha.
        """
        url = f"{META_GRAPH_API_URL}{path}"
        ultima_excecao: Exception | None = None

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._headers,
                        json=json_body,
                    )

                # Loga a chamada
                logger.info(
                    "Meta Cloud API %s %s → status %d (tentativa %d)",
                    method,
                    path,
                    response.status_code,
                    tentativa,
                )

                # Verifica se houve erro HTTP
                if response.status_code >= 400:
                    corpo = response.text
                    logger.error(
                        "Erro na Meta Cloud API: %d - %s",
                        response.status_code,
                        corpo,
                    )
                    raise MetaCloudAPIError(response.status_code, corpo)

                return response.json()

            except MetaCloudAPIError:
                # Erro da API — não faz retry (erro de negócio)
                raise

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as exc:
                ultima_excecao = exc
                logger.warning(
                    "Tentativa %d/%d falhou para %s %s: %s",
                    tentativa,
                    MAX_TENTATIVAS,
                    method,
                    path,
                    str(exc),
                )
                # Continua para próxima tentativa

        # Esgotou todas as tentativas
        logger.error(
            "Todas as %d tentativas falharam para %s %s",
            MAX_TENTATIVAS,
            method,
            url,
        )
        raise ConnectionError(
            f"Falha ao conectar com Meta Cloud API após {MAX_TENTATIVAS} tentativas: {ultima_excecao}"
        )

    # ------------------------------------------------------------------
    # Envio de mensagens
    # ------------------------------------------------------------------

    async def send_text_message(
        self,
        phone_number: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Envia mensagem de texto simples via WhatsApp Cloud API.

        Args:
            phone_number: Número do destinatário (ex: "5511999999999").
            message: Texto da mensagem.

        Returns:
            Resposta da API com status do envio.
        """
        logger.info(
            "Enviando mensagem de texto para %s via Meta Cloud API",
            phone_number,
        )
        return await self._request(
            method="POST",
            path=f"/{self.phone_number_id}/messages",
            json_body={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "text",
                "text": {"body": message},
            },
        )

    async def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        language_code: str = "pt_BR",
    ) -> dict[str, Any]:
        """
        Envia mensagem de template pré-aprovado via WhatsApp Cloud API.

        Args:
            phone_number: Número do destinatário.
            template_name: Nome do template aprovado no Meta Business.
            language_code: Código do idioma do template (padrão: pt_BR).

        Returns:
            Resposta da API com status do envio.
        """
        logger.info(
            "Enviando template '%s' para %s via Meta Cloud API",
            template_name,
            phone_number,
        )
        return await self._request(
            method="POST",
            path=f"/{self.phone_number_id}/messages",
            json_body={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code},
                },
            },
        )

    async def mark_as_read(
        self,
        message_id: str,
    ) -> dict[str, Any]:
        """
        Marca uma mensagem como lida no WhatsApp.
        Envia o indicador de "visto" (double blue check) para o remetente.

        Args:
            message_id: ID da mensagem recebida (wamid.xxx).

        Returns:
            Resposta da API confirmando a marcação.
        """
        logger.info(
            "Marcando mensagem %s como lida via Meta Cloud API",
            message_id,
        )
        return await self._request(
            method="POST",
            path=f"/{self.phone_number_id}/messages",
            json_body={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
        )
