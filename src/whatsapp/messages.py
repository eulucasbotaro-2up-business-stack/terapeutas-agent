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
    pela primeira vez.

    Args:
        nome_terapeuta: Nome do terapeuta para personalizar a mensagem.
    """
    return (
        f"Olá! Sou o assistente virtual do(a) *{nome_terapeuta}*. "
        f"Estou aqui para ajudar com informações sobre os materiais e "
        f"protocolos disponibilizados pelo(a) seu/sua terapeuta.\n\n"
        f"Como posso ajudar você hoje?"
    )


def formatar_encaminhamento(nome_terapeuta: str, contato: str) -> str:
    """
    Mensagem para encaminhar o paciente ao terapeuta quando a questão
    foge do escopo da base de conhecimento.

    Args:
        nome_terapeuta: Nome do terapeuta.
        contato: Telefone ou e-mail de contato do terapeuta.
    """
    return (
        f"Essa questão precisa da atenção direta do(a) *{nome_terapeuta}*. "
        f"Por favor, entre em contato diretamente:\n\n"
        f"Contato: {contato}\n\n"
        f"O(A) {nome_terapeuta} poderá orientar você da melhor forma."
    )


def formatar_urgencia(nome_terapeuta: str, contato: str) -> str:
    """
    Mensagem para situações de urgência/crise detectadas na conversa.
    Prioriza encaminhamento imediato e CVV.

    Args:
        nome_terapeuta: Nome do terapeuta.
        contato: Telefone de contato do terapeuta.
    """
    return (
        f"Percebo que você pode estar passando por um momento difícil. "
        f"Quero que saiba que você não está sozinho(a).\n\n"
        f"*Se estiver em crise, ligue agora:*\n"
        f"CVV (Centro de Valorização da Vida): *188*\n"
        f"Chat: https://www.cvv.org.br\n\n"
        f"Também entre em contato com *{nome_terapeuta}*: {contato}\n\n"
        f"Sua saúde e bem-estar são prioridade."
    )


def formatar_agendamento(contato: str) -> str:
    """
    Mensagem padrão quando o paciente pede para agendar consulta.

    Args:
        contato: Telefone ou link de agendamento do terapeuta.
    """
    return (
        f"Para agendar ou remarcar sua consulta, entre em contato "
        f"diretamente com o consultório:\n\n"
        f"Contato: {contato}\n\n"
        f"Ficaremos felizes em encontrar o melhor horário para você!"
    )


def formatar_fora_escopo() -> str:
    """
    Mensagem quando a pergunta do paciente foge completamente
    do escopo da base de conhecimento do terapeuta.
    """
    return (
        "Desculpe, não encontrei informações sobre esse assunto nos "
        "materiais disponibilizados pelo(a) seu/sua terapeuta.\n\n"
        "Posso ajudar com dúvidas relacionadas aos protocolos e "
        "materiais que foram compartilhados com você. "
        "Para outras questões, entre em contato diretamente com "
        "seu/sua terapeuta."
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

        # 3. Mensagem de áudio — não suportado por enquanto
        elif "audioMessage" in message:
            logger.info("Áudio recebido de %s — não suportado", numero)
            texto = "[AUDIO_NAO_SUPORTADO]"

        # 4. Mensagem de imagem com legenda
        elif "imageMessage" in message:
            texto = message["imageMessage"].get("caption", "[IMAGEM_RECEBIDA]")
            if not texto:
                texto = "[IMAGEM_RECEBIDA]"
            logger.info("Imagem recebida de %s", numero)

        # 5. Outros tipos não suportados
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
    Mensagem padrão quando o paciente envia áudio.
    O sistema ainda não processa áudio.
    """
    return (
        "Desculpe, ainda não consigo processar mensagens de áudio. "
        "Poderia enviar sua dúvida por texto? "
        "Assim consigo ajudar melhor!"
    )
