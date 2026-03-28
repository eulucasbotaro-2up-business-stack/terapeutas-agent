"""
Cliente da Evolution API v2 para envio/recebimento de mensagens WhatsApp.

Cada terapeuta conecta seu número WhatsApp via Evolution API.
Este módulo encapsula todas as chamadas HTTP à API.
"""

import logging
from typing import Any

import httpx

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Configurações de retry
MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 30.0


class EvolutionAPIError(Exception):
    """Erro genérico da Evolution API."""

    def __init__(self, status_code: int, detalhe: str) -> None:
        self.status_code = status_code
        self.detalhe = detalhe
        super().__init__(f"Evolution API erro {status_code}: {detalhe}")


class EvolutionClient:
    """
    Cliente assíncrono para a Evolution API v2.

    Uso:
        client = EvolutionClient()
        await client.enviar_mensagem("instancia-do-terapeuta", "5511999999999", "Olá!")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Inicializa o cliente. Se base_url/api_key não forem passados,
        carrega das variáveis de ambiente via Settings.
        """
        settings = get_settings()
        self.base_url = (base_url or settings.EVOLUTION_API_URL).rstrip("/")
        self.api_key = api_key or settings.EVOLUTION_API_KEY
        self._headers = {"apikey": self.api_key, "Content-Type": "application/json"}

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
        Loga cada tentativa e levanta EvolutionAPIError em caso de falha.
        """
        url = f"{self.base_url}{path}"
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
                    "Evolution API %s %s → status %d (tentativa %d)",
                    method,
                    path,
                    response.status_code,
                    tentativa,
                )

                # Verifica se houve erro HTTP
                if response.status_code >= 400:
                    corpo = response.text
                    logger.error(
                        "Erro na Evolution API: %d - %s",
                        response.status_code,
                        corpo,
                    )
                    raise EvolutionAPIError(response.status_code, corpo)

                return response.json()

            except EvolutionAPIError:
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
            f"Falha ao conectar com Evolution API após {MAX_TENTATIVAS} tentativas: {ultima_excecao}"
        )

    # ------------------------------------------------------------------
    # Mensagens
    # ------------------------------------------------------------------

    async def enviar_mensagem(
        self,
        instance: str,
        numero: str,
        texto: str,
    ) -> dict[str, Any]:
        """
        Envia mensagem de texto simples via WhatsApp.

        Args:
            instance: Nome da instância do terapeuta na Evolution API.
            numero: Número do destinatário (ex: "5511999999999").
            texto: Texto da mensagem.

        Returns:
            Resposta da API com status do envio.
        """
        logger.info(
            "Enviando mensagem para %s via instância '%s'",
            numero,
            instance,
        )
        return await self._request(
            method="POST",
            path=f"/message/sendText/{instance}",
            json_body={"number": numero, "text": texto},
        )

    async def enviar_mensagem_com_botoes(
        self,
        instance: str,
        numero: str,
        texto: str,
        botoes: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Envia mensagem com botões interativos via WhatsApp.

        Args:
            instance: Nome da instância do terapeuta.
            numero: Número do destinatário.
            texto: Texto principal da mensagem.
            botoes: Lista de botões, cada um com {"displayText": "Texto do botão"}.

        Returns:
            Resposta da API com status do envio.

        Exemplo de botoes:
            [{"displayText": "Sim"}, {"displayText": "Não"}]
        """
        logger.info(
            "Enviando mensagem com %d botões para %s via instância '%s'",
            len(botoes),
            numero,
            instance,
        )
        return await self._request(
            method="POST",
            path=f"/message/sendText/{instance}",
            json_body={
                "number": numero,
                "text": texto,
                "buttons": botoes,
            },
        )

    # ------------------------------------------------------------------
    # Gerenciamento de instâncias
    # ------------------------------------------------------------------

    async def criar_instancia(self, nome: str) -> dict[str, Any]:
        """
        Cria uma nova instância WhatsApp na Evolution API.
        Cada terapeuta precisa de uma instância própria.

        Args:
            nome: Nome único da instância (ex: "terapeuta-uuid-curto").

        Returns:
            Dados da instância criada.
        """
        logger.info("Criando instância WhatsApp: '%s'", nome)
        return await self._request(
            method="POST",
            path="/instance/create",
            json_body={
                "instanceName": nome,
                "integration": "WHATSAPP-BAILEYS",
            },
        )

    async def conectar_instancia(self, nome: str) -> dict[str, Any]:
        """
        Conecta uma instância e retorna o QR code para pareamento.
        O terapeuta escaneia este QR code com o WhatsApp do celular.

        Args:
            nome: Nome da instância a conectar.

        Returns:
            Dict com QR code (base64 ou texto) para pareamento.
        """
        logger.info("Solicitando QR code para instância: '%s'", nome)
        return await self._request(
            method="GET",
            path=f"/instance/connect/{nome}",
        )

    async def status_instancia(self, nome: str) -> dict[str, Any]:
        """
        Verifica o status de conexão de uma instância.

        Args:
            nome: Nome da instância.

        Returns:
            Dict com estado da conexão (open, close, connecting).
        """
        logger.info("Verificando status da instância: '%s'", nome)
        return await self._request(
            method="GET",
            path=f"/instance/connectionState/{nome}",
        )

    # ------------------------------------------------------------------
    # Configuração de webhook
    # ------------------------------------------------------------------

    async def baixar_midia(
        self,
        instance: str,
        mensagem_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Baixa mídia (áudio, imagem, vídeo, documento) via Evolution API.
        A Evolution API decripta e retorna a mídia como base64.

        Args:
            instance: Nome da instância do terapeuta.
            mensagem_data: O objeto "data" completo do webhook (inclui key + message).

        Returns:
            Dict com { base64, mediaType, fileName, mimeType }
        """
        logger.info("Baixando mídia via Evolution API (instância='%s')", instance)
        return await self._request(
            method="POST",
            path=f"/message/download-media/{instance}",
            json_body=mensagem_data,
        )

    async def enviar_imagem(
        self,
        instance: str,
        numero: str,
        imagem_bytes: bytes,
        caption: str = "",
        mimetype: str = "image/png",
        nome_arquivo: str = "mapa_natal.png",
    ) -> dict[str, Any]:
        """
        Envia imagem via WhatsApp usando a Evolution API (base64).

        Args:
            instance: Nome da instância do terapeuta.
            numero: Número do destinatário (ex: "5511999999999").
            imagem_bytes: Bytes da imagem PNG/JPEG.
            caption: Legenda opcional da imagem.
            mimetype: Tipo MIME da imagem (default: "image/png").
            nome_arquivo: Nome do arquivo para exibição.

        Returns:
            Resposta da API com status do envio.
        """
        import base64
        logger.info(
            "Enviando imagem (%d KB) para %s via instância '%s'",
            len(imagem_bytes) // 1024,
            numero,
            instance,
        )
        imagem_b64 = base64.b64encode(imagem_bytes).decode("utf-8")
        return await self._request(
            method="POST",
            path=f"/message/sendMedia/{instance}",
            json_body={
                "number": numero,
                "mediatype": "image",
                "mimetype": mimetype,
                "caption": caption,
                "media": f"data:{mimetype};base64,{imagem_b64}",
                "fileName": nome_arquivo,
            },
        )

    async def configurar_webhook(
        self,
        nome: str,
        webhook_url: str,
    ) -> dict[str, Any]:
        """
        Configura o webhook de uma instância para receber mensagens.
        O webhook é chamado pela Evolution API quando chega uma mensagem
        no WhatsApp do terapeuta.

        Args:
            nome: Nome da instância.
            webhook_url: URL do endpoint que receberá os webhooks.
                         Ex: "https://api.terapeutas.app/webhook/whatsapp"

        Returns:
            Confirmação da configuração.
        """
        logger.info(
            "Configurando webhook da instância '%s' para %s",
            nome,
            webhook_url,
        )
        return await self._request(
            method="POST",
            path=f"/webhook/set/{nome}",
            json_body={
                "url": webhook_url,
                "webhookByEvents": True,
                "events": ["MESSAGES_UPSERT"],
            },
        )
