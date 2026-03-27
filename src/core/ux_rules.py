"""
Regras de experiencia do usuario (UX) para o agente WhatsApp.

O agente DEVE parecer humano. Ninguem pode perceber que e um bot.
Este modulo pos-processa TODA resposta antes de enviar ao usuario,
garantindo tom conversacional, sem marcadores, sem formatacao de bot.

Regras do Lucas (dono do projeto):
1. Maximo 1 emoticon por mensagem, e so quando natural
2. Sem marcadores (-, *, numeros com ponto) — conversa fluida
3. Conversa humanizada — ninguem pode perceber que e um bot
4. Personalizada com o perfil da pessoa
5. Conduzir conversa de forma natural
"""

import re
import random
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# REGRAS DE HUMANIZACAO — INJETADAS NO SYSTEM PROMPT
# =============================================================================

REGRAS_HUMANIZACAO = """
## REGRAS DE COMUNICACAO — HUMANIZACAO OBRIGATORIA

Voce esta conversando pelo WhatsApp. A pessoa do outro lado NAO pode perceber que esta falando com uma IA.
Escreva como se estivesse conversando pessoalmente, de forma natural e fluida.

OBRIGATORIO:
- Use paragrafos curtos, como mensagens de WhatsApp reais. Maximo 2-3 linhas por paragrafo.
- NUNCA use listas com marcadores (-, *, numeros com ponto). Explique tudo de forma corrida, em texto fluido.
- Use no maximo 1 emoji por mensagem, e SOMENTE quando soar natural. Na duvida, nao use.
- Varie suas aberturas. NUNCA comece com "Ola! Como posso ajudar?" ou qualquer saudacao generica de bot.
- Faca perguntas de acompanhamento naturais, como faria numa conversa real.
- Use o nome da pessoa quando souber.
- NAO use markdown. Sem negrito (**), sem italico (*), sem cabecalhos (##), sem sublinhado.
- Limite cada mensagem a no maximo 3 paragrafos curtos.
- NAO use linguagem formal demais. Fale como um profissional que conversa de igual pra igual.
- Evite frases que denunciem que voce e uma IA, como "como assistente", "fui programado", "minha funcao e".
- NAO repita padroes de abertura. Se ja disse "Que bom que voce trouxe isso", use outra forma na proxima.
- Quando for explicar algo que teria multiplos pontos, integre tudo num texto corrido natural.
"""


# =============================================================================
# SAUDACOES PROIBIDAS (soam como bot)
# =============================================================================

_SAUDACOES_BOT = [
    "olá! como posso ajudar",
    "olá! como posso te ajudar",
    "ola! como posso ajudar",
    "ola! como posso te ajudar",
    "olá, como posso ajudar",
    "ola, como posso ajudar",
    "olá! em que posso ajudar",
    "ola! em que posso ajudar",
    "olá! estou aqui para ajudar",
    "ola! estou aqui para ajudar",
    "como posso ajudá-lo",
    "como posso ajuda-lo",
    "como posso ajudá-la",
    "como posso ajuda-la",
    "como posso ser útil",
    "como posso ser util",
    "em que posso ser útil",
    "em que posso ser util",
    "claro! ",
    "claro, ",
    "com certeza! ",
    "com certeza, ",
    "ótimo! ",
    "ótimo, ",
    "otimo! ",
    "otimo, ",
    "excelente! ",
    "excelente, ",
    "entendido! ",
    "entendido, ",
    "perfeito! ",
    "perfeito, ",
    "absolutamente! ",
    "absolutamente, ",
    "certamente! ",
    "certamente, ",
]

# Aberturas variadas para substituir saudacoes genericas
_ABERTURAS_ALTERNATIVAS = [
    "Fala, {nome}.",
    "E ai, {nome}.",
    "Opa, {nome}.",
    "{nome}, to aqui.",
    "Beleza, {nome}?",
    "Que bom que voce apareceu, {nome}.",
    "{nome}, me conta.",
    "Pode falar, {nome}.",
    "To por aqui, {nome}.",
    "{nome}, diz ai.",
]


# =============================================================================
# FUNCAO PRINCIPAL: HUMANIZAR RESPOSTA
# =============================================================================

def humanizar_resposta(texto: str) -> str:
    """
    Pos-processa TODA resposta do agente antes de enviar pelo WhatsApp.

    Aplica as regras de humanizacao do Lucas:
    1. Remove bullet points e marcadores
    2. Transforma listas em paragrafos fluidos
    3. Limita emoticons a no maximo 1 por mensagem
    4. Remove formatacao markdown
    5. Quebra textos longos em no maximo 3 paragrafos
    6. Remove saudacoes genericas de bot

    Args:
        texto: Resposta original gerada pela IA.

    Returns:
        Texto humanizado, pronto para enviar no WhatsApp.
    """
    if not texto or not texto.strip():
        return texto

    resultado = texto.strip()

    # 1. Remover formatacao markdown
    resultado = _remover_markdown(resultado)

    # 2. Transformar listas com marcadores em texto fluido
    resultado = _converter_listas_em_texto(resultado)

    # 3. Limitar emoticons a no maximo 1 por mensagem
    resultado = _limitar_emoticons(resultado)

    # 4. Remover saudacoes genericas de bot
    resultado = _remover_saudacao_bot(resultado)

    # 5. Remover frases de encerramento de bot (case insensitive)
    _padroes_bot_final = [
        r"[Pp]osso continuar se quiser\.?",
        r"[Qq]uer que eu continue\??",
        r"[Dd]eseja que eu aprofunde\??",
        r"[Pp]osso aprofundar se quiser\.?",
        r"[Pp]osso detalhar mais se quiser\.?",
        r"[Mm]e avise se quiser saber mais\.?",
        r"[Pp]osso seguir se quiser\.?",
        r"[Ss]e quiser que eu continue.*$",
        r"[Ee]spero que (isso|esta resposta|este conteudo|esse conteudo) (tenha ajudado|seja util|te ajude).*$",
        r"[Ff]ico à disposição.*$",
        r"[Ff]ico a disposicao.*$",
        r"[Qq]ualquer dúvida.*$",
        r"[Qq]ualquer duvida.*$",
        r"[Ss]e tiver (alguma )?dúvida.*$",
        r"[Ss]e tiver (alguma )?duvida.*$",
        r"[Ee]stou aqui para (qualquer|mais).*$",
        r"[Hh]ope this helps.*$",
        r"[Ll]et me know.*$",
        r"[Ee]spero ter ajudado.*$",
        r"[Aa]lguma outra (dúvida|duvida|pergunta|questao|questão)\??$",
        r"[Pp]osso te ajudar com (mais )?algo\??$",
        r"[Hh]á mais algo.*$",
        r"[Tt]em mais alguma.*$",
    ]
    for padrao in _padroes_bot_final:
        resultado = re.sub(padrao, "", resultado).strip()

    # 6. Remover referencias a materiais (agente deve falar com autoridade)
    _refs_materiais = [
        "o material aponta",
        "segundo os materiais",
        "os materiais indicam",
        "de acordo com os materiais",
        "o que os materiais dizem",
        "conforme os materiais",
        "nos materiais da escola",
        "a apostila diz",
        "a apostila indica",
        "o material diz",
        "segundo o material",
        "de acordo com o material",
        "conforme o material",
        "nos materiais",
    ]
    resultado_lower = resultado.lower()
    for ref in _refs_materiais:
        # Remove case-insensitive, preservando o texto ao redor
        resultado = re.sub(re.escape(ref), "", resultado, flags=re.IGNORECASE).strip()
    # Limpar virgulas ou pontos duplicados que ficaram apos remocao
    resultado = re.sub(r'\s*,\s*,', ',', resultado)
    resultado = re.sub(r'\.\s*\.', '.', resultado)
    resultado = re.sub(r'^\s*[,;]\s*', '', resultado, flags=re.MULTILINE)

    # 7. Remover referencias de fonte (quebra humanizacao) — regex agressivo
    # Remove qualquer linha que contenha referencias de fonte em qualquer formato
    resultado = re.sub(r'\[Fonte:.*?\]', '', resultado).strip()
    resultado = re.sub(r'_\[Fonte:.*?\]_', '', resultado).strip()
    resultado = re.sub(r'\[Material:.*?\]', '', resultado).strip()
    # Remove linhas com "Fonte", "Fontes", "Fontes:" em qualquer formato (case insensitive)
    resultado = re.sub(r'^.*[Ff]ontes?\s*:.*$', '', resultado, flags=re.MULTILINE).strip()
    # Remove linhas com "YouTube -" (referencia de video)
    resultado = re.sub(r'^.*YouTube\s*-.*$', '', resultado, flags=re.MULTILINE).strip()
    # Remove linhas com "[Material:" ou "(Material:"
    resultado = re.sub(r'^.*[\[\(]Material:.*$', '', resultado, flags=re.MULTILINE).strip()
    # Remove referencias tipo "Material: nome.pdf" em qualquer posicao
    resultado = re.sub(r'Material:\s*[^\]\)]*\.pdf', '', resultado, flags=re.IGNORECASE).strip()
    # Remove "Nivel X" isolado no final de linhas (residuo de referencia)
    resultado = re.sub(r',?\s*Nivel\s+\d+\s*[\]\)]', '', resultado).strip()
    # Remove linhas que ficaram vazias ou so com pontuacao apos limpeza
    resultado = re.sub(r'^\s*[,.\-;:]+\s*$', '', resultado, flags=re.MULTILINE).strip()

    # 8. Limitar paragrafos (mais generoso pra framework clinico)
    resultado = _limitar_paragrafos(resultado, max_paragrafos=15)

    # 9. Limpar espacos extras
    resultado = _limpar_espacos(resultado)

    return resultado.strip()


# =============================================================================
# FUNCOES AUXILIARES DE POS-PROCESSAMENTO
# =============================================================================

def _remover_markdown(texto: str) -> str:
    """Remove formatacao markdown (negrito, italico, headers)."""
    # Remove headers (## Titulo, ### Titulo, etc)
    resultado = re.sub(r'^#{1,6}\s+', '', texto, flags=re.MULTILINE)

    # Remove negrito (**texto** ou __texto__)
    resultado = re.sub(r'\*\*(.+?)\*\*', r'\1', resultado)
    resultado = re.sub(r'__(.+?)__', r'\1', resultado)

    # Remove italico (*texto* ou _texto_)
    # Cuidado para nao remover asteriscos de listas (tratados separadamente)
    resultado = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', resultado)
    resultado = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', resultado)

    # Remove codigo inline (`texto`)
    resultado = re.sub(r'`(.+?)`', r'\1', resultado)

    # Remove blocos de codigo (```texto```)
    resultado = re.sub(r'```[\s\S]*?```', '', resultado)

    # Remove links markdown [texto](url) -> texto
    resultado = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', resultado)

    return resultado


def _converter_listas_em_texto(texto: str) -> str:
    """
    Converte listas com marcadores em texto fluido.
    Transforma:
      - item 1
      - item 2
      - item 3
    Em: "item 1, item 2 e item 3"
    Ou em paragrafos corridos quando os itens sao mais longos.
    """
    linhas = texto.split('\n')
    resultado = []
    itens_lista = []

    for linha in linhas:
        # Detecta linhas que sao itens de lista
        match_lista = re.match(r'^\s*[-*•]\s+(.+)$', linha)
        match_numero = re.match(r'^\s*\d+[\.\)]\s+(.+)$', linha)

        if match_lista:
            itens_lista.append(match_lista.group(1).strip())
        elif match_numero:
            itens_lista.append(match_numero.group(1).strip())
        else:
            # Se tinhamos itens de lista acumulados, converte em texto
            if itens_lista:
                texto_fluido = _itens_para_texto(itens_lista)
                resultado.append(texto_fluido)
                itens_lista = []
            resultado.append(linha)

    # Converte itens restantes no final
    if itens_lista:
        texto_fluido = _itens_para_texto(itens_lista)
        resultado.append(texto_fluido)

    return '\n'.join(resultado)


def _itens_para_texto(itens: list[str]) -> str:
    """
    Converte uma lista de itens em texto corrido.
    Se os itens sao curtos, junta com virgulas.
    Se sao longos, junta com pontos finais em paragrafo.
    """
    if not itens:
        return ""

    if len(itens) == 1:
        return itens[0]

    # Se os itens sao curtos (media < 50 chars), junta com virgulas
    media_tamanho = sum(len(i) for i in itens) / len(itens)

    if media_tamanho < 50:
        # Junta com virgulas e "e" no ultimo
        if len(itens) == 2:
            return f"{itens[0]} e {itens[1]}"
        return ", ".join(itens[:-1]) + f" e {itens[-1]}"
    else:
        # Itens longos: junta como frases separadas por ponto
        partes = []
        for item in itens:
            item = item.strip()
            if item and not item.endswith(('.', '!', '?')):
                item += '.'
            partes.append(item)
        return " ".join(partes)


def _limitar_emoticons(texto: str) -> str:
    """
    Limita emoticons/emojis a no maximo 1 por mensagem.
    Mantem o primeiro emoji encontrado e remove os demais.
    """
    # Padrao para detectar emojis Unicode
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # simbolos e pictografias
        "\U0001F680-\U0001F6FF"  # transporte e mapas
        "\U0001F1E0-\U0001F1FF"  # bandeiras
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # outros
        "\U0001F900-\U0001F9FF"  # suplementares
        "\U0001FA00-\U0001FA6F"  # xadrez e outros
        "\U0001FA70-\U0001FAFF"  # simbolos extras
        "\U00002600-\U000026FF"  # misc simbolos
        "\U0000FE00-\U0000FE0F"  # variacao seletores
        "\U0000200D"             # ZWJ
        "\U00002B50"             # estrela
        "\U00002764"             # coracao
        "\U0000203C-\U00003299"  # CJK e outros
        "]+",
        flags=re.UNICODE,
    )

    emojis_encontrados = list(emoji_pattern.finditer(texto))

    if len(emojis_encontrados) <= 1:
        return texto

    # Mantem o primeiro, remove os demais
    primeiro = True
    resultado = texto
    for match in reversed(emojis_encontrados):
        if primeiro:
            primeiro = False
            continue
        resultado = resultado[:match.start()] + resultado[match.end():]

    return resultado


def _remover_saudacao_bot(texto: str) -> str:
    """Remove saudacoes genericas que soam como bot."""
    texto_lower = texto.lower().strip()

    for saudacao in _SAUDACOES_BOT:
        if texto_lower.startswith(saudacao):
            # Remove a saudacao do inicio
            # Encontra onde termina (pode ter ! ou ? ou . depois)
            idx = len(saudacao)
            while idx < len(texto) and texto[idx] in ' !?.,:;\n':
                idx += 1
            texto = texto[idx:].strip()
            break

    return texto


def _limitar_paragrafos(texto: str, max_paragrafos: int = 3) -> str:
    """
    Limita o texto a no maximo N paragrafos.
    Paragrafos alem do limite sao descartados, e uma frase de
    continuidade e adicionada se havia mais conteudo.
    """
    # Divide em paragrafos (separados por linha em branco)
    paragrafos = [p.strip() for p in re.split(r'\n\s*\n', texto) if p.strip()]

    if len(paragrafos) <= max_paragrafos:
        return '\n\n'.join(paragrafos)

    # Pega os primeiros N paragrafos
    # NOTA: não adiciona frase de continuação — seria detectada como saudação de bot
    # e removida pelo pós-processamento em humanizar_resposta(). Truncar silenciosamente
    # é mais seguro; diagnósticos longos têm max_paragrafos=15 e raramente são cortados.
    cortado = '\n\n'.join(paragrafos[:max_paragrafos])

    return cortado


def _limpar_espacos(texto: str) -> str:
    """Remove espacos e quebras de linha excessivas."""
    # Remove multiplas quebras de linha (mais de 2)
    resultado = re.sub(r'\n{3,}', '\n\n', texto)
    # Remove espacos multiplos
    resultado = re.sub(r'[ \t]{2,}', ' ', resultado)
    # Remove espacos no inicio/final de cada linha
    linhas = [linha.strip() for linha in resultado.split('\n')]
    return '\n'.join(linhas)


# =============================================================================
# PERSONALIZACAO DE TOM
# =============================================================================

def personalizar_tom(resposta: str, contexto_terapeuta: dict) -> str:
    """
    Adapta o tom da resposta baseado no perfil do terapeuta.

    Args:
        resposta: Texto da resposta ja humanizada.
        contexto_terapeuta: Dicionario com dados do terapeuta:
            - nome_terapeuta (str): Nome do profissional
            - tom_voz (str): Tom de voz configurado (ex: "direto e profundo")
            - especialidade (str): Area de atuacao

    Returns:
        Resposta com tom adaptado ao perfil do terapeuta.
    """
    if not resposta or not contexto_terapeuta:
        return resposta

    nome = contexto_terapeuta.get("nome_terapeuta", "")
    tom = contexto_terapeuta.get("tom_voz", "")

    resultado = resposta

    # Se o terapeuta tem um tom especifico configurado, adapta sutilezas
    if tom:
        tom_lower = tom.lower()

        # Tom mais formal: evita girias
        if "formal" in tom_lower:
            resultado = resultado.replace("E ai", "Bom te ver")
            resultado = resultado.replace("Fala,", "Boa,")
            resultado = resultado.replace("Opa,", "Que bom,")
            resultado = resultado.replace("diz ai", "me conta")

        # Tom mais acolhedor: adiciona frases de acolhimento
        if "acolhedor" in tom_lower or "caloroso" in tom_lower:
            # Nao modifica muito, apenas garante que nao esta seco demais
            pass

        # Tom direto: remove frases de transicao desnecessarias
        if "direto" in tom_lower:
            resultado = resultado.replace("Bom, vou te explicar. ", "")
            resultado = resultado.replace("Entao, veja bem, ", "")
            resultado = resultado.replace("Vou te contar uma coisa, ", "")

    return resultado


def gerar_abertura_variada(nome: str = "") -> str:
    """
    Gera uma abertura variada para mensagens, evitando repeticoes.

    Args:
        nome: Nome da pessoa para personalizar (opcional).

    Returns:
        Frase de abertura humanizada.
    """
    abertura = random.choice(_ABERTURAS_ALTERNATIVAS)

    if nome:
        return abertura.format(nome=nome)
    else:
        # Remove o placeholder de nome e ajusta
        return abertura.format(nome="").replace("  ", " ").replace(", .", ".").strip()
