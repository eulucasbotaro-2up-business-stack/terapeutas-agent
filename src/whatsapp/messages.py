"""
Formatador e parser de mensagens WhatsApp.

Contém funções utilitárias para:
- Formatar mensagens padronizadas (boas-vindas, urgência, etc.)
- Extrair dados do payload de webhook da Evolution API v2
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Mensagens formatadas
# ------------------------------------------------------------------

def formatar_boas_vindas(nome_terapeuta: str) -> str:
    """
    Mensagem de boas-vindas quando um paciente entra em contato
    pela primeira vez. Tom humanizado, sem parecer bot.

    Args:
        nome_terapeuta: Nome do terapeuta para personalizar a mensagem.
    """
    return (
        f"Oi, tudo bem? Aqui e do consultorio do(a) {nome_terapeuta}. "
        f"Posso te ajudar com informacoes sobre os materiais e "
        f"protocolos que o(a) {nome_terapeuta} disponibilizou pra voce.\n\n"
        f"Me conta, o que voce precisa?"
    )


def formatar_encaminhamento(nome_terapeuta: str, contato: str) -> str:
    """
    Mensagem para encaminhar o paciente ao terapeuta quando a questao
    foge do escopo da base de conhecimento. Tom humanizado.

    Args:
        nome_terapeuta: Nome do terapeuta.
        contato: Telefone ou e-mail de contato do terapeuta.
    """
    return (
        f"Essa questao precisa de um olhar mais direto do(a) {nome_terapeuta}. "
        f"O melhor caminho e entrar em contato diretamente pelo {contato}.\n\n"
        f"O(A) {nome_terapeuta} vai conseguir te orientar melhor nisso."
    )


def formatar_urgencia(nome_terapeuta: str, contato: str) -> str:
    """
    Mensagem para situacoes de urgencia/crise detectadas na conversa.
    Prioriza encaminhamento imediato e CVV. Tom acolhedor e humano.

    Args:
        nome_terapeuta: Nome do terapeuta.
        contato: Telefone de contato do terapeuta.
    """
    return (
        f"Ei, percebo que voce pode estar passando por um momento dificil. "
        f"Quero que saiba que voce nao esta sozinho(a).\n\n"
        f"Se estiver precisando de ajuda agora, liga pro CVV no 188, "
        f"funciona 24 horas e e gratuito. Tambem tem o chat em cvv.org.br\n\n"
        f"E entra em contato com {nome_terapeuta} tambem, pelo {contato}. "
        f"Sua saude vem primeiro, ta?"
    )


def formatar_agendamento(contato: str) -> str:
    """
    Mensagem quando o paciente pede para agendar consulta. Tom natural.

    Args:
        contato: Telefone ou link de agendamento do terapeuta.
    """
    return (
        f"Pra agendar ou remarcar sua consulta, o melhor e falar "
        f"direto com o consultorio pelo {contato}.\n\n"
        f"La eles encontram o melhor horario pra voce."
    )


def formatar_fora_escopo() -> str:
    """
    Mensagem quando a pergunta do paciente foge do escopo
    da base de conhecimento do terapeuta. Tom conversacional.
    """
    return (
        "Sobre isso eu nao tenho informacao nos materiais que "
        "o(a) terapeuta disponibilizou, infelizmente.\n\n"
        "Posso te ajudar com duvidas sobre os protocolos e "
        "materiais que foram compartilhados com voce. "
        "Se for sobre outro assunto, o melhor e falar direto "
        "com seu/sua terapeuta."
    )


# ------------------------------------------------------------------
# Parser do payload de webhook
# ------------------------------------------------------------------

def extrair_numero_mensagem(payload: dict[str, Any]) -> tuple[str, str]:
    """
    Extrai o número do remetente e o texto da mensagem do payload
    de webhook da Evolution API v2 (evento MESSAGES_UPSERT).

    Trata os seguintes tipos de mensagem:
    - conversation: texto simples
    - extendedTextMessage: texto com link preview ou citação
    - audioMessage: retorna aviso de que áudio não é suportado

    Args:
        payload: Payload JSON recebido no webhook.
            Formato esperado:
            {
                "event": "messages.upsert",
                "instance": "nome",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": false
                    },
                    "message": {
                        "conversation": "texto da mensagem"
                    }
                }
            }

    Returns:
        Tupla (numero, texto):
        - numero: Número limpo do remetente (ex: "5511999999999")
        - texto: Conteúdo da mensagem ou aviso para tipos não suportados

    Raises:
        ValueError: Se o payload não contém os campos esperados.
    """
    try:
        data = payload.get("data", {})
        key = data.get("key", {})
        message = data.get("message", {})

        # Extrai e limpa o número (remove @s.whatsapp.net)
        remote_jid = key.get("remoteJid", "")
        numero = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid

        # Ignora mensagens enviadas pelo próprio bot (fromMe = true)
        if key.get("fromMe", False):
            logger.debug("Mensagem ignorada (fromMe=true) de %s", numero)
            return numero, ""

        # Tenta extrair texto de diferentes formatos de mensagem
        texto = ""

        # 1. Mensagem de texto simples
        if "conversation" in message:
            texto = message["conversation"]

        # 2. Texto estendido (com link preview, citação, etc.)
        elif "extendedTextMessage" in message:
            texto = message["extendedTextMessage"].get("text", "")

        # 3. Mensagem de áudio — será transcrita via Whisper no webhook
        elif "audioMessage" in message:
            logger.info("Áudio recebido de %s — pendente transcrição Whisper", numero)
            texto = "[AUDIO_EVOLUTION_PENDENTE]"

        # 4. Mensagem de imagem com legenda ou pendente processamento
        elif "imageMessage" in message:
            caption = message["imageMessage"].get("caption", "")
            texto = caption if caption else "[IMAGEM_EVOLUTION_PENDENTE]"
            logger.info("Imagem recebida de %s", numero)

        # 5. Mensagem de vídeo
        elif "videoMessage" in message:
            caption = message["videoMessage"].get("caption", "")
            texto = caption if caption else "[VIDEO_EVOLUTION_PENDENTE]"
            logger.info("Vídeo recebido de %s", numero)

        # 6. Mensagem de documento
        elif "documentMessage" in message:
            mimetype = message["documentMessage"].get("mimetype", "")
            filename = message["documentMessage"].get("fileName", "")
            if "pdf" in mimetype or filename.lower().endswith(".pdf"):
                texto = "[DOCUMENTO_PDF_EVOLUTION_PENDENTE]"
            else:
                caption = message["documentMessage"].get("caption", "")
                texto = caption if caption else "[DOCUMENTO_RECEBIDO]"
            logger.info("Documento recebido de %s (tipo=%s)", numero, mimetype)

        # 7. Outros tipos não suportados
        else:
            tipos_encontrados = list(message.keys())
            logger.warning(
                "Tipo de mensagem não suportado de %s: %s",
                numero,
                tipos_encontrados,
            )
            texto = "[TIPO_NAO_SUPORTADO]"

        logger.info(
            "Mensagem recebida de %s: '%s' (%d caracteres)",
            numero,
            texto[:50] + "..." if len(texto) > 50 else texto,
            len(texto),
        )

        return numero, texto

    except (KeyError, TypeError, AttributeError) as exc:
        logger.error("Erro ao extrair dados do payload: %s", exc)
        raise ValueError(f"Payload de webhook inválido: {exc}") from exc


def eh_mensagem_valida(payload: dict[str, Any]) -> bool:
    """
    Verifica se o payload é uma mensagem válida que deve ser processada.
    Filtra mensagens do próprio bot, status updates, etc.

    Args:
        payload: Payload JSON do webhook.

    Returns:
        True se a mensagem deve ser processada, False caso contrário.
    """
    # Verifica se é o evento correto
    evento = payload.get("event", "")
    if evento != "messages.upsert":
        logger.debug("Evento ignorado: %s", evento)
        return False

    # Verifica se tem dados da mensagem
    data = payload.get("data", {})
    if not data:
        logger.debug("Payload sem dados")
        return False

    # Ignora mensagens do próprio bot
    key = data.get("key", {})
    if key.get("fromMe", False):
        return False

    # Ignora mensagens de grupo (somente atende 1:1)
    remote_jid = key.get("remoteJid", "")
    if "@g.us" in remote_jid:
        logger.debug("Mensagem de grupo ignorada: %s", remote_jid)
        return False

    # Ignora status/stories
    if "status@broadcast" in remote_jid:
        return False

    return True


def formatar_aviso_audio() -> str:
    """
    Mensagem quando o paciente envia audio.
    O sistema ainda nao processa audio. Tom natural.

    DEPRECATED: Esta funcao nao e chamada em nenhum lugar do codigo atualmente.
    O sistema agora transcreve audios via Whisper (webhook.py).
    Mantida para compatibilidade — remover em versao futura se nao for reutilizada.
    """
    return (
        "Nao consegui ouvir o audio, infelizmente. "
        "Consegue me mandar por texto? "
        "Assim fica mais facil te ajudar."
    )
