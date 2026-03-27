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

# --- Código inválido ---
MSG_CODIGO_INVALIDO = (
    "Infelizmente esse código não é válido ou já está em uso.\n\n"
    "Por gentileza, fale com o suporte para regularizar seu acesso."
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
        "Pode perguntar sobre o método, trazer casos ou pedir conteúdo."
    ),
    "Antes de começar, como posso te chamar?",
]

# --- Nome registrado: iniciar conversa ---
def gerar_msg_boas_vindas_nome(nome: str) -> str:
    import random
    nome_fmt = nome.strip().split()[0].capitalize()

    variacoes = [
        f"{nome_fmt}, prazer! Pode mandar o que tiver. Caso clínico, dúvida conceitual, ou quer criar conteúdo pra redes? Tô aqui pra caminhar junto contigo.",
        f"Prazer, {nome_fmt}. Pode trazer o que você precisar — análise de caso, pesquisa no método do Joel, ou produção de conteúdo. O que você traz hoje?",
        f"{nome_fmt}! Bom ter você aqui. Caso clínico, dúvida sobre o método, criação de post... me conta o que está na sua cabeça.",
    ]
    return random.choice(variacoes)

# --- Usuário já ativo diz "oi" de novo ---
def gerar_saudacao_ativo(nome: Optional[str]) -> list[str]:
    """
    Retorna saudação natural para usuário já ativo.
    Menciona as 3 frentes sem bullet points nem cara de IA.
    Varia o texto para não repetir sempre o mesmo padrão.
    """
    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""

    variacoes = [
        (
            f"{'Fala, ' + nome_fmt + '!' if nome_fmt else 'Fala!'} Pode trazer o que tiver.",
            "Caso clínico pra analisar, dúvida sobre o método, ou quer criar um conteúdo? Tô aqui."
        ),
        (
            f"{'Opa, ' + nome_fmt + '.' if nome_fmt else 'Opa.'} Que bom te ver aqui.",
            "Me conta o que você traz hoje — um caso, uma dúvida do método, ou precisa de conteúdo pra redes?"
        ),
        (
            f"{'E aí, ' + nome_fmt + '!' if nome_fmt else 'E aí!'} Tô por aqui.",
            "Pode ser caso clínico, pesquisa nos materiais do Joel, ou criação de post. O que você precisa?"
        ),
        (
            f"{'Oi, ' + nome_fmt + '.' if nome_fmt else 'Oi.'} Que bom.",
            "Tem um caso pra analisar, uma dúvida sobre o método, ou quer aprofundar algum conceito específico?"
        ),
    ]

    escolha = random.choice(variacoes)
    return list(escolha)

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
        """True quando ATIVO mas ainda não coletamos o nome."""
        return self.is_ativo and not self.nome_usuario


# =============================================================================
# FUNÇÕES PRINCIPAIS
# =============================================================================

def obter_ou_criar_estado(
    terapeuta_id: str,
    numero_telefone: str,
) -> tuple[EstadoChat, bool]:
    """
    Busca o estado do número no banco. Se não existir, cria com PENDENTE_CODIGO.

    Returns:
        (EstadoChat, is_new) — is_new=True indica que acabou de ser criado
        e o bot deve enviar a sequência de boas-vindas.
    """
    supabase = get_supabase()

    # Tenta inserir — se já existe, ignora (ON CONFLICT DO NOTHING)
    insert_result = (
        supabase.table("chat_estado")
        .upsert(
            {
                "terapeuta_id": terapeuta_id,
                "numero_telefone": numero_telefone,
                "estado": "PENDENTE_CODIGO",
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="terapeuta_id,numero_telefone",
            ignore_duplicates=True,
        )
        .execute()
    )

    # is_new = True se o upsert retornou dados (linha foi criada agora)
    is_new = bool(insert_result.data)

    # Busca o estado atual (recém-criado ou pré-existente)
    busca = (
        supabase.table("chat_estado")
        .select("*")
        .eq("terapeuta_id", terapeuta_id)
        .eq("numero_telefone", numero_telefone)
        .limit(1)
        .execute()
    )

    if not busca.data:
        raise RuntimeError(
            f"Falha crítica: não foi possível criar estado para {numero_telefone}"
        )

    estado = EstadoChat(busca.data[0])
    logger.info(
        f"Estado={estado.estado} | is_new={is_new} | "
        f"numero={numero_telefone} | terapeuta={terapeuta_id}"
    )
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

            # 4. Para código de uso único: verificar se já foi usado por outro
            if not row.get("reutilizavel") and row.get("usado") and numero_ativo != numero_telefone:
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
    """Muda o estado do número para ATIVO após código válido."""
    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "estado": "ATIVO",
        "codigo_usado": codigo_usado.strip().lower()[:200],
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
    palavras = texto.strip().split()
    nome = " ".join(palavras[:3])[:60]

    supabase = get_supabase()
    supabase.table("chat_estado").update({
        "nome_usuario": nome,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }).eq("terapeuta_id", terapeuta_id).eq(
        "numero_telefone", numero_telefone
    ).execute()

    logger.info(f"Nome registrado: '{nome}' para {numero_telefone}")
    return nome


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
