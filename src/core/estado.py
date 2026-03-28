"""
Máquina de estados do chat — controle de acesso e moderação de conteúdo.

Ciclo de vida de cada número:
  (nova mensagem) → PENDENTE_CODIGO → (código válido) → ATIVO → (3 violações) → BLOQUEADO

Responsabilidades:
1. Criar/buscar o estado de um número no banco (thread-safe via upsert)
2. Validar códigos de liberação (tabela codigos_liberacao + código de teste)
3. Registrar nomes de usuários após o desbloqueio
4. Detectar profanidade / mensagens impróprias
5. Registrar violações e bloquear na 3ª
"""

import logging
import re
import requests
from datetime import datetime, timezone
from typing import Optional

from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Código de teste universal (case-insensitive, sem espaços extras)
CODIGO_TESTE = "eu quero testar"

# Número máximo de violações antes do bloqueio automático
MAX_VIOLACOES = 3


# =============================================================================
# LISTA DE PALAVRAS PROIBIDAS
# Regex com word-boundary para evitar falsos positivos.
# Conservadora: palavras com duplo sentido clínico (como "sexo") são excluídas.
# =============================================================================

_PALAVRAS_PROIBIDAS: list[str] = [
    # Palavrões diretos (PT-BR)
    r"\bporra\b", r"\bcaralho\b", r"\bcaramba\b",
    r"\bfoda\b", r"\bfoder\b", r"\bfodido\b",
    r"\bmerda\b", r"\bbosta\b", r"\bdroga\b",
    r"\bputa\s+que\b", r"\bputa\s+merda\b",
    r"\bfilha\s+da\s+puta\b", r"\bfilho\s+da\s+puta\b",
    r"\bfilhaputa\b", r"\bfilhodaputa\b",
    r"\bpqp\b", r"\bfdp\b", r"\bvsf\b", r"\bvtc\b",
    r"\bcuzao\b", r"\bcuzão\b",
    r"\bdesgraca\b", r"\bdesgraça\b",

    # Insultos pessoais
    r"\bidiota\b", r"\bimbecil\b", r"\bcretino\b",
    r"\bestupido\b", r"\bestúpido\b",
    r"\bburro\b", r"\btrouxa\b", r"\bcorno\b",
    r"\bviado\b", r"\bviadagem\b",

    # Ameaças
    r"vou\s+te\s+matar", r"vou\s+acabar\s+com\s+você",
    r"vou\s+acabar\s+com\s+voce",
    r"sei\s+onde\s+você\s+mora", r"sei\s+onde\s+voce\s+mora",

    # Conteúdo explicitamente sexual/ofensivo
    r"\bporno\b", r"\bpornografia\b",
    r"\bnuda\b", r"\bnudo\b",

    # Spam / nonsense repetitivo (10+ caracteres idênticos seguidos)
    r"(.)\1{9,}",
]

_REGEX_PROFANIDADE = re.compile(
    "|".join(_PALAVRAS_PROIBIDAS),
    flags=re.IGNORECASE | re.UNICODE,
)

# Detectar mensagem de keyboard mashing (80%+ de chars não-alfabéticos com 8+ chars)
_REGEX_NONSENSE = re.compile(r"^[^a-záàâãéèêíìîóòôõúùûçA-Z\s]{8,}$", re.UNICODE)


# =============================================================================
# TEXTOS DAS MENSAGENS
# Tom: acolhedor, direto, identidade do Alquimista Interior
# =============================================================================

# --- Onboarding: primeira mensagem ever (pedido de código) ---
# NOTA: Este assistente é posicionado como ferramenta especializada do consultório
# (não como IA de propósito geral) — conformidade com política Meta jan/2026.
MSGS_ONBOARDING: list[str] = [
    "Olá! Seja bem-vindo(a) ao Alquimista Interior — o assistente especializado da Escola de Alquimia do Joel Aleixo 🙏",
    (
        "Aqui você encontra apoio em três frentes específicas do método alquímico:\n\n"
        "• Dúvidas e pesquisas sobre os ensinamentos da escola\n"
        "• Discussão e análise de casos clínicos com base nos materiais do Joel\n"
        "• Produção de conteúdo (posts, materiais, roteiros)\n\n"
        "Este assistente não substitui atendimento clínico. Para consultas terapêuticas, agende com o Joel."
    ),
    (
        "Para iniciar, confirme seu acesso com o código de liberação "
        "enviado após a compra. 🔑\n\n"
        "É só digitar o código aqui."
    ),
]

# --- Código inválido (tentativas 1-4) ---
MSG_CODIGO_INVALIDO = (
    "Esse código não é válido. 🔑\n\n"
    "Verifique o código enviado após a compra e coloque o código novamente:"
)

# --- Código inválido (5ª tentativa em diante) ---
MSG_CODIGO_INVALIDO_FINAL = (
    "Você atingiu o limite de tentativas. ❌\n\n"
    "Por favor, entre em contato com o administrador para regularizar seu acesso."
)

# --- Acesso suspenso por assinatura ---
MSG_ASSINATURA_EXPIRADA = (
    "Seu acesso expirou. 📅\n\n"
    "Renove sua assinatura para continuar utilizando o Alquimista Interior. "
    "Fale com o suporte."
)

MSG_PAGAMENTO_FALHOU = (
    "Seu acesso foi suspenso por falha no pagamento. 💳\n\n"
    "Regularize o pagamento para reativar. Fale com o suporte."
)

MSG_ASSINATURA_CANCELADA = (
    "Sua assinatura foi cancelada. \n\n"
    "Para reativar o acesso, entre em contato com o suporte."
)

# --- Código válido: acesso liberado ---
MSGS_ACESSO_LIBERADO: list[str] = [
    "Código confirmado! Acesso liberado ✨",
    (
        "A partir de agora você tem acesso completo à base de conhecimento "
        "do método alquímico do Joel Aleixo.\n\n"
        "Pode perguntar sobre o método, trazer casos clínicos ou pedir ajuda para produção de conteúdo — "
        "por texto ou áudio, como preferir."
    ),
    "Antes de começar, como posso te chamar?",
]

# --- Confirmação de nome ---
def gerar_msg_confirmar_nome(nome: str) -> str:
    nome_fmt = nome.strip().split()[0].capitalize()
    return f"Perfeito, *{nome_fmt}*! Me confirma se você escreveu seu nome certo por gentileza."

MSG_PEDIR_NOME_NOVAMENTE = "Tudo bem! Como você prefere ser chamado(a)?"
MSG_NOME_NAO_IDENTIFICADO = "Qual é o seu nome? Como posso te chamar?"

# --- Nome registrado: iniciar conversa ---
def gerar_msg_boas_vindas_nome(nome: str) -> str:
    import random
    nome_fmt = nome.strip().split()[0].capitalize()

    variacoes = [
        f"{nome_fmt}, prazer! Pode mandar o que tiver. Caso clínico, dúvida conceitual, ou quer criar conteúdo pra redes? Tô aqui pra caminhar junto contigo.",
        f"Prazer, {nome_fmt}. Pode trazer o que você precisar: análise de caso, pesquisa no método do Joel, ou produção de conteúdo. O que você traz hoje?",
        f"{nome_fmt}! Bom ter você aqui. Caso clínico, dúvida sobre o método, criação de post... me conta o que está na sua cabeça.",
    ]
    return random.choice(variacoes)

# --- Usuário já ativo diz "oi" de novo ---
def gerar_saudacao_ativo(nome: Optional[str], tem_historico_recente: bool = False) -> list[str]:
    """
    Retorna saudação natural para usuário já ativo.

    Se tem_historico_recente=True, a conversa já está em andamento —
    não pergunta "no que posso ajudar?" nem lista as 3 frentes de novo.
    Responde apenas com uma saudação curta e aguarda o terapeuta continuar.

    Se tem_historico_recente=False (padrão), menciona as 3 frentes
    de forma natural para orientar o terapeuta no início da sessão.
    """
    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""

    if tem_historico_recente:
        # Conversa já em andamento — saudação dinâmica com as 3 frentes
        variacoes_com_opcoes = [
            (
                f"{'Boa, ' + nome_fmt + '!' if nome_fmt else 'Boa!'} E agora, quer trazer mais algum caso, entender algo do método ou criar conteúdo?",
            ),
            (
                f"{'Que bom, ' + nome_fmt + '.' if nome_fmt else 'Que bom.'} Tem mais algum caso pra trabalhar, uma dúvida sobre o método, ou quer criar conteúdo agora?",
            ),
            (
                f"{'Fala, ' + nome_fmt + '!' if nome_fmt else 'Fala!'} Mais algum caso clínico, pesquisa no método do Joel, ou produção de conteúdo?",
            ),
            (
                f"{'Opa, ' + nome_fmt + '.' if nome_fmt else 'Opa.'} O que você traz agora — mais um caso, algo sobre o método, ou quer criar conteúdo?",
            ),
        ]
        return [random.choice(variacoes_com_opcoes)[0]]

    # Início de sessão nova — apresenta as 3 frentes
    variacoes = [
        (
            f"{'Fala, ' + nome_fmt + '!' if nome_fmt else 'Fala!'} Pode trazer o que tiver.",
            "É um caso pra analisar, quer entender algum conceito do método, ou ajuda na produção de conteúdo?"
        ),
        (
            f"{'Opa, ' + nome_fmt + '.' if nome_fmt else 'Opa.'} Que bom te ver aqui.",
            "Tem um caso, uma dúvida do método, ou precisa de conteúdo para as redes?"
        ),
        (
            f"{'E aí, ' + nome_fmt + '!' if nome_fmt else 'E aí!'} Tô por aqui.",
            "Pode ser caso clínico, pesquisa nos materiais do Joel, ou criação de post. O que você traz?"
        ),
        (
            f"{'Oi, ' + nome_fmt + '.' if nome_fmt else 'Oi.'} Que bom.",
            "Caso clínico, dúvida no método, ou produção de conteúdo, o que está na cabeça hoje?"
        ),
    ]

    escolha = random.choice(variacoes)
    return list(escolha)

# --- Sinal de confusão (mensagem muito curta ou ambígua em conversa ativa) ---
def gerar_resposta_confusao(nome: Optional[str]) -> str:
    """
    Resposta curta para sinais de confusão (ex: 'uê', 'hm', '?', 'né?', 'pois é').
    Não repete a pergunta sobre caso/dúvida/conteúdo — apenas convida a continuar
    de onde a conversa estava.
    """
    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""

    variacoes = [
        f"{'Pode continuar, ' + nome_fmt + '.' if nome_fmt else 'Pode continuar.'} Fico à disposição.",
        f"{'Pode falar, ' + nome_fmt + '.' if nome_fmt else 'Pode falar.'} Estou aqui.",
        "Tô aqui. Pode mandar.",
        "Me conta mais. Estou de olho no que você trouxe.",
    ]
    return random.choice(variacoes)


# --- Falha na transcrição de áudio ---
def gerar_msg_audio_incompreensivel(nome: Optional[str]) -> str:
    """
    Mensagem quando a transcrição de áudio retornou conteúdo vazio ou incompreensível.
    Sugere alternativas específicas sem frustrar o terapeuta.
    """
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""
    saudacao = f"{nome_fmt}, o" if nome_fmt else "O"
    return (
        f"{saudacao} áudio não ficou claro na transcrição. "
        "Pode tentar de novo num ambiente mais silencioso, "
        "ou se preferir, me manda por texto mesmo — às vezes é mais rápido."
    )


# --- Moderação: aviso 1 ---
MSG_AVISO_1 = (
    "Por favor, mantenha o respeito para que eu possa te ajudar melhor. "
    "Estou aqui para te apoiar 🙏"
)

# --- Moderação: aviso 2 ---
MSG_AVISO_2 = (
    "Esta é a segunda vez que recebo uma mensagem inadequada. "
    "Mais uma e o acesso será suspenso. "
    "Vamos manter o espaço respeitoso?"
)

# --- Bloqueio imediato (3ª violação) ---
def gerar_msg_bloqueio(contato_admin: str) -> str:
    return (
        f"Acesso suspenso por mensagens inadequadas reiteradas.\n\n"
        f"Para reativar, entre em contato com o administrador: {contato_admin}"
    )

# --- Usuário já bloqueado tenta enviar mensagem ---
def gerar_msg_ja_bloqueado(contato_admin: str, motivo_bloqueio: str = "") -> str:
    """Retorna mensagem adequada ao motivo do bloqueio."""
    if motivo_bloqueio == "ASSINATURA_EXPIRADA":
        return MSG_ASSINATURA_EXPIRADA
    elif motivo_bloqueio == "PAGAMENTO_FALHOU":
        return MSG_PAGAMENTO_FALHOU
    elif motivo_bloqueio == "CANCELADO":
        return MSG_ASSINATURA_CANCELADA
    return (
        f"Chat suspenso. "
        f"Fale com o administrador para reativar: {contato_admin}"
    )


# =============================================================================
# CLASSE: ESTADO DO CHAT
# =============================================================================

class EstadoChat:
    """Encapsula uma linha da tabela chat_estado."""

    def __init__(self, row: dict):
        self.id: str = row["id"]
        self.terapeuta_id: str = row["terapeuta_id"]
        self.numero_telefone: str = row["numero_telefone"]
        self.estado: str = row["estado"]
        self.nome_usuario: Optional[str] = row.get("nome_usuario")
        self.codigo_usado: Optional[str] = row.get("codigo_usado")
        self.violacoes_conteudo: int = row.get("violacoes_conteudo", 0)
        self.motivo_bloqueio: Optional[str] = row.get("motivo_bloqueio")
        self.criado_em: str = row.get("criado_em", "")
        self.atualizado_em: str = row.get("atualizado_em", "")

        # --- Campos de memória e sessão (schema_memoria.sql) ---
        self.ultima_mensagem_em: Optional[str] = row.get("ultima_mensagem_em")
        self.sessao_atual_inicio: Optional[str] = row.get("sessao_atual_inicio")
        # Confirmação de nome
        self.aguardando_confirmacao_nome: bool = bool(
            row.get("aguardando_confirmacao_nome", False)
        )
        self.nome_sugerido: Optional[str] = row.get("nome_sugerido")
        # Confirmação de mudança de tópico
        self.aguardando_confirmacao_topico: bool = bool(
            row.get("aguardando_confirmacao_topico", False)
        )
        self.mensagem_pendente_topico: Optional[str] = row.get("mensagem_pendente_topico")
        self.topico_anterior: Optional[str] = row.get("topico_anterior")

    @property
    def is_pendente(self) -> bool:
        return self.estado == "PENDENTE_CODIGO"

    @property
    def is_ativo(self) -> bool:
        return self.estado == "ATIVO"

    @property
    def is_bloqueado(self) -> bool:
        return self.estado == "BLOQUEADO"

    @property
    def aguardando_nome(self) -> bool:
        """True quando ATIVO, sem nome confirmado e sem confirmação de nome pendente."""
        return self.is_ativo and not self.nome_usuario and not self.aguardando_confirmacao_nome


# =============================================================================
# FUNÇÕES PRINCIPAIS
# =============================================================================

def obter_ou_criar_estado(
    terapeuta_id: str,
    numero_telefone: str,
) -> tuple["EstadoChat", bool]:
    """
    Busca o estado do número no banco. Se não existir, cria com PENDENTE_CODIGO.
    Returns: (EstadoChat, is_new)
    """
    from src.core.config import get_settings
    settings = get_settings()

    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    base_url = settings.SUPABASE_URL.rstrip("/") + "/rest/v1"

    # 1. Try to SELECT existing state
    resp = requests.get(
        f"{base_url}/chat_estado",
        headers=headers,
        params={
            "terapeuta_id": f"eq.{terapeuta_id}",
            "numero_telefone": f"eq.{numero_telefone}",
            "limit": "1",
        },
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()

    if rows:
        estado = EstadoChat(rows[0])
        logger.info(f"Estado encontrado: {estado.estado} | numero={numero_telefone}")
        return estado, False

    # 2. Não existe estado: criar sempre como PENDENTE_CODIGO.
    # O auto-recovery via tabela `conversas` foi removido intencionalmente:
    # ele permitia bypass total do fluxo de código quando chat_estado era
    # perdido/zerado mas conversas ainda tinha registros CODIGO_VALIDO.
    # Comportamento correto: se o estado foi perdido, o usuário recomeça do zero.
    is_new = True

    # 3. INSERT new state
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "terapeuta_id": terapeuta_id,
        "numero_telefone": numero_telefone,
        "estado": "PENDENTE_CODIGO",
        "atualizado_em": now_iso,
    }
    resp3 = requests.post(
        f"{base_url}/chat_estado",
        headers={**headers, "Prefer": "return=representation,resolution=ignore-duplicates"},
        json=payload,
        timeout=10,
    )

    # 4. SELECT after insert (handles race conditions)
    resp4 = requests.get(
        f"{base_url}/chat_estado",
        headers=headers,
        params={
            "terapeuta_id": f"eq.{terapeuta_id}",
            "numero_telefone": f"eq.{numero_telefone}",
            "limit": "1",
        },
        timeout=10,
    )
    resp4.raise_for_status()
    rows4 = resp4.json()

    if not rows4:
        raise RuntimeError(f"Falha crítica: não foi possível criar estado para {numero_telefone}")

    estado = EstadoChat(rows4[0])
    logger.info(f"Estado criado: {estado.estado} | is_new={is_new} | numero={numero_telefone}")
    return estado, is_new


def validar_codigo(
    terapeuta_id: str,
    numero_telefone: str,
    codigo_digitado: str,
) -> bool:
    """
    Valida o código digitado contra o código de teste e a tabela codigos_liberacao.

    Regras:
    1. Código de teste "eu quero testar" sempre válido (case-insensitive).
    2. Códigos da tabela: status_assinatura IN ('disponivel', 'ativo').
    3. data_expiracao: deve ser nula (sem prazo) ou no futuro.
    4. numero_ativo: deve ser nulo (código não está em uso) OU o mesmo número atual.
       → Se numero_ativo é diferente: código já está sendo usado por outro número.
    5. Para reutilizavel=False: usado deve ser False OU número é o mesmo.

    Returns:
        True se o código é válido e o acesso deve ser liberado.
    """
    from datetime import datetime, timezone
    codigo_norm = codigo_digitado.strip().lower()[:200]

    # Código de teste universal (sem expiração, sem restrição de usuário)
    if codigo_norm == CODIGO_TESTE:
        logger.info(f"Código de TESTE aceito para {numero_telefone}")
        return True

    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("codigos_liberacao")
            .select("id, codigo, reutilizavel, usado, numero_ativo, data_expiracao, status_assinatura")
            .eq("terapeuta_id", terapeuta_id)
            .eq("ativo", True)
            .execute()
        )

        agora = datetime.now(timezone.utc)

        for row in (resultado.data or []):
            if row["codigo"].strip().lower() != codigo_norm:
                continue

            # 1. Verificar status da assinatura
            status = row.get("status_assinatura", "disponivel")
            if status not in ("disponivel", "ativo"):
                logger.warning(
                    f"Código '{codigo_norm[:10]}' rejeitado: "
                    f"status_assinatura={status}"
                )
                return False

            # 2. Verificar expiração
            data_expiracao = row.get("data_expiracao")
            if data_expiracao:
                try:
                    expiracao = datetime.fromisoformat(data_expiracao)
                    if expiracao < agora:
                        logger.warning(
                            f"Código '{codigo_norm[:10]}' expirado em "
                            f"{expiracao.strftime('%d/%m/%Y')}"
                        )
                        return False
                except (ValueError, TypeError):
                    pass  # data inválida: deixar passar

            # 3. Verificar 1 código = 1 usuário
            numero_ativo = row.get("numero_ativo")
            if numero_ativo and numero_ativo != numero_telefone:
                logger.warning(
                    f"Código '{codigo_norm[:10]}' já está em uso "
                    f"por outro número"
                )
                return False

            # 4. Para código de uso único: verificar se já foi usado por OUTRO número.
            #    Se numero_ativo é None (código nunca ativado), não bloquear.
            #    O campo usado=True com numero_ativo=None pode ocorrer em race condition
            #    durante ativar_acesso_com_codigo — deve ser tratado como válido.
            if (
                not row.get("reutilizavel")
                and row.get("usado")
                and numero_ativo is not None
                and numero_ativo != numero_telefone
            ):
                logger.warning(
                    f"Código '{codigo_norm[:10]}' de uso único já foi utilizado"
                )
                return False

            # Código válido: se reutilizavel=False, marcar como usado
            if not row.get("reutilizavel") and not row.get("usado"):
                supabase.table("codigos_liberacao").update({
                    "usado": True,
                    "usado_por": numero_telefone,
                    "usado_em": agora.isoformat(),
                }).eq("id", row["id"]).execute()

            logger.info(
                f"Código '{codigo_norm[:10]}' válido para {numero_telefone}"
            )
            return True

        logger.info(f"Código '{codigo_norm[:10]}' não encontrado para terapeuta={terapeuta_id}")
        return False

    except Exception as e:
        logger.error(f"Erro ao validar código: {e}", exc_info=True)
        return False


def liberar_acesso(
    terapeuta_id: str,
    numero_telefone: str,
    codigo_usado: str,
) -> None:
    """
    Muda o estado do número para ATIVO após código válido.
    Limpa nome_usuario para garantir que o passo de coleta de nome
    sempre aconteça após cada nova validação de código.
    """
    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "estado": "ATIVO",
        "codigo_usado": codigo_usado.strip().lower()[:200],
        "nome_usuario": None,  # Sempre re-coleta o nome após nova validação
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()
    logger.info(f"Acesso LIBERADO para {numero_telefone} (terapeuta={terapeuta_id})")


def registrar_nome_usuario(
    terapeuta_id: str,
    numero_telefone: str,
    texto: str,
) -> str:
    """
    Extrai e salva o nome do usuário a partir do texto enviado.
    Pega no máximo as 3 primeiras palavras (nomes raramente têm mais).

    Returns:
        O nome que foi salvo.
    """
    # Filtrar apenas palavras com ao menos 1 caractere alfabético (evita nomes como "123" ou "!!!")
    palavras_validas = [p for p in texto.strip().split() if any(c.isalpha() for c in p)]
    nome = " ".join(palavras_validas[:3])[:60] if palavras_validas else "Usuário"

    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "nome_usuario": nome,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()

    logger.info(f"Nome registrado: '{nome}' para {numero_telefone}")
    return nome


def salvar_nome_sugerido(
    terapeuta_id: str,
    numero_telefone: str,
    nome_sugerido: str,
) -> None:
    """
    Salva um nome sugerido (extraído pelo LLM) e sinaliza que estamos aguardando confirmação.
    Não grava em nome_usuario ainda — só em nome_sugerido.
    """
    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "nome_sugerido": nome_sugerido,
        "aguardando_confirmacao_nome": True,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()
    logger.info(f"Nome sugerido salvo: '{nome_sugerido}' para {numero_telefone}")


def confirmar_nome_sugerido(
    terapeuta_id: str,
    numero_telefone: str,
    nome_sugerido: str,
) -> str:
    """
    Confirma o nome sugerido: salva em nome_usuario e limpa os campos de sugestão.
    Returns o nome formatado (primeira palavra, capitalizado).
    """
    nome_fmt = nome_sugerido.strip().split()[0].capitalize()
    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "nome_usuario": nome_fmt,
        "nome_sugerido": None,
        "aguardando_confirmacao_nome": False,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()
    logger.info(f"Nome confirmado: '{nome_fmt}' para {numero_telefone}")
    return nome_fmt


def rejeitar_nome_sugerido(
    terapeuta_id: str,
    numero_telefone: str,
) -> None:
    """
    Usuário rejeitou o nome sugerido. Limpa sugestão e volta a pedir o nome.
    """
    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "nome_sugerido": None,
        "aguardando_confirmacao_nome": False,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()
    logger.info(f"Nome sugerido rejeitado para {numero_telefone}")


def detectar_profanidade(texto: str) -> bool:
    """
    Detecta palavrões, insultos, ameaças ou mensagens nonsense.

    Conservador: prefere falsos negativos a falsos positivos.
    Palavras com contexto clínico legítimo (ex: "sexo") são excluídas da lista.

    Returns:
        True se conteúdo impróprio for detectado.
    """
    if not texto or not texto.strip():
        return False

    # Palavras proibidas
    if _REGEX_PROFANIDADE.search(texto):
        return True

    # Keyboard mashing (ex: "asdfghjkl", "zxcvbnm")
    if _REGEX_NONSENSE.match(texto.strip()):
        return True

    return False


def registrar_violacao(
    terapeuta_id: str,
    numero_telefone: str,
) -> int:
    """
    Incrementa o contador de violações.
    Se atingir MAX_VIOLACOES (3), bloqueia automaticamente.

    Returns:
        Número total de violações após o incremento.
    """
    supabase = get_supabase()

    busca = (
        supabase.table("chat_estado")
        .select("violacoes_conteudo")
        .eq("terapeuta_id", terapeuta_id)
        .eq("numero_telefone", numero_telefone)
        .limit(1)
        .execute()
    )

    if not busca.data:
        logger.error(f"Estado não encontrado para {numero_telefone} ao registrar violação")
        return 0

    novas_violacoes = busca.data[0]["violacoes_conteudo"] + 1
    update: dict = {
        "violacoes_conteudo": novas_violacoes,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }

    if novas_violacoes >= MAX_VIOLACOES:
        update["estado"] = "BLOQUEADO"
        logger.warning(
            f"Número BLOQUEADO ({novas_violacoes} violações): "
            f"{numero_telefone} (terapeuta={terapeuta_id})"
        )

    supabase.table("chat_estado").update(update).eq(
        "terapeuta_id", terapeuta_id
    ).eq("numero_telefone", numero_telefone).execute()

    return novas_violacoes
