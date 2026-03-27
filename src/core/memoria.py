"""
Motor de Memória do Usuário — Terapeutas Agent.

Cada usuário (número de WhatsApp) tem memória persistente que cresce a cada sessão:

1. PERFIL ACUMULADO
   - Temas mais discutidos, estilo de comunicação, modo principal de uso
   - Cresce a cada interação — quanto mais o usuário usa, mais afinado fica

2. RESUMOS DE SESSÕES
   - Cada sessão (bloco separado por > 3h de inatividade) é resumida pelo Haiku
   - Os últimos 3 resumos são injetados no system prompt como "memória de longo prazo"
   - O agente retoma naturalmente: "Da última vez você estava analisando..."

3. DETECÇÃO DE MUDANÇA DE ASSUNTO
   - Detecta quando a mensagem nova é completamente diferente do que estava sendo discutido
   - Envia confirmação antes de mudar: "Quer parar o caso X e partir pra outro assunto?"
   - Evita conversas confusas onde o agente mistura dois contextos diferentes

4. CONTINUIDADE ENTRE DIAS
   - Na saudação após um gap longo, o agente menciona o que foi discutido antes
   - Tom natural: não robótico, não "lembro que você disse...", mas contextual

Tabelas:
    perfil_usuario   — perfil por (terapeuta_id, numero_telefone)
    resumos_sessao   — resumos de sessões, indexados por usuário e data
    chat_estado      — adicionados: ultima_mensagem_em, aguardando_confirmacao_topico,
                       mensagem_pendente_topico, topico_anterior
"""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Inatividade > N horas = nova sessão
SESSION_GAP_HORAS = 3

# Quantos resumos de sessões anteriores injetar no prompt
MAX_RESUMOS_NO_PROMPT = 3

# Quantas mensagens usar ao gerar o resumo da sessão
MAX_MSGS_PARA_RESUMO = 30

# Limiar de dissimilaridade para acionar detecção de mudança de tópico (0.0–1.0)
# 1.0 = completamente diferente. Abaixo disso = mesmo tópico.
LIMIAR_MUDANCA_TOPICO = 0.82

# Quantidade mínima de trocas na conversa antes de ativar detecção de mudança
MIN_TROCAS_PARA_DETECTAR = 3

# Palavras que confirmam mudança de assunto
_PALAVRAS_SIM = {
    "sim", "s", "pode", "vai", "claro", "ok", "muda", "mude",
    "bora", "quero", "confirmo", "confirmado", "muda sim",
    "pode mudar", "muda aí", "pode ir", "vamos",
}

# Palavras que negam mudança (quer continuar o tópico anterior)
_PALAVRAS_NAO = {
    "não", "nao", "n", "continua", "continuar", "volta", "voltar",
    "mantém", "mantem", "não muda", "nao muda", "fica", "segue",
    "segue nisso", "continua nisso", "aqui mesmo",
}

# Stop words para análise de tópico (excluídas do cálculo de similaridade)
_STOP_WORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "e", "ou", "que", "se", "com", "por", "para", "pra", "pro",
    "me", "te", "lhe", "lhes", "nos", "vos",
    "eu", "tu", "ele", "ela", "nós", "vós", "eles", "elas",
    "isso", "isto", "aquilo", "esse", "essa", "este", "esta",
    "meu", "minha", "seu", "sua", "nosso", "nossa",
    "é", "são", "foi", "era", "eram", "ser", "ter", "tem", "tinha",
    "não", "sim", "também", "já", "ainda", "mais", "muito", "pouco",
    "bem", "aqui", "ali", "então", "quando", "como", "onde", "qual",
    "mas", "porém", "porque", "pois", "que", "quê",
    "tudo", "nada", "algo", "alguém", "ninguém",
}


# =============================================================================
# DETECÇÃO DE MUDANÇA DE ASSUNTO (heurística, zero latência)
# =============================================================================

def _extrair_palavras_chave(texto: str) -> set[str]:
    """Extrai tokens relevantes sem stop words."""
    tokens = re.findall(r"\b[a-záàâãéèêíìîóòôõúùûç]{3,}\b", texto.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


def calcular_similaridade_topico(msgs_anteriores: list[str], nova_msg: str) -> float:
    """
    Coeficiente de Jaccard entre palavras-chave das últimas mensagens e a nova.

    Returns:
        0.0 = completamente diferente | 1.0 = idêntico
    """
    if not msgs_anteriores:
        return 1.0

    kw_historico: set[str] = set()
    for msg in msgs_anteriores[-4:]:
        kw_historico.update(_extrair_palavras_chave(msg))

    kw_nova = _extrair_palavras_chave(nova_msg)

    # Mensagem muito curta: não bloquear (provavelmente resposta sim/não)
    if not kw_historico or len(kw_nova) < 3:
        return 1.0

    intersecao = kw_historico & kw_nova
    uniao = kw_historico | kw_nova

    return len(intersecao) / len(uniao) if uniao else 1.0


def _resumo_topico(msgs_usuario: list[str]) -> str:
    """Extrai 2-3 palavras mais frequentes para nomear o tópico anterior."""
    todas: list[str] = []
    for msg in msgs_usuario[-4:]:
        todas.extend(_extrair_palavras_chave(msg))

    if not todas:
        return "assunto anterior"

    freq = Counter(todas)
    top = [p for p, _ in freq.most_common(3)]
    return " / ".join(top)


def detectar_mudanca_assunto(
    historico: list[dict],
    nova_mensagem: str,
) -> tuple[bool, str]:
    """
    Detecta se a nova mensagem representa uma mudança abrupta de tópico.

    Ativa somente quando:
    - Há pelo menos MIN_TROCAS_PARA_DETECTAR trocas no histórico
    - A mensagem nova tem pelo menos 15 caracteres (não é um "ok"/"sim")
    - A similaridade Jaccard está abaixo de LIMIAR_MUDANCA_TOPICO

    Returns:
        (mudou_assunto: bool, topico_anterior: str)
    """
    # Não ativa em conversas muito curtas
    if len(historico) < MIN_TROCAS_PARA_DETECTAR * 2:
        return False, ""

    # Não ativa para mensagens muito curtas (respostas simples)
    if len(nova_mensagem.strip()) < 15:
        return False, ""

    msgs_usuario = [
        m["content"] for m in historico
        if m.get("role") in ("terapeuta", "user")
    ]

    if len(msgs_usuario) < 2:
        return False, ""

    similaridade = calcular_similaridade_topico(msgs_usuario, nova_mensagem)

    if similaridade < (1.0 - LIMIAR_MUDANCA_TOPICO):  # similaridade baixa = assuntos diferentes
        topico = _resumo_topico(msgs_usuario)
        logger.info(
            f"Mudança de assunto detectada | similaridade={similaridade:.2f} | "
            f"tópico anterior: '{topico}'"
        )
        return True, topico

    return False, ""


def eh_confirmacao(texto: str) -> bool:
    """Verifica se o texto é uma confirmação de mudança de assunto (sim)."""
    norm = texto.strip().lower()
    return norm in _PALAVRAS_SIM or any(p in norm for p in _PALAVRAS_SIM if len(p) > 3)


def eh_negacao(texto: str) -> bool:
    """Verifica se o texto é uma negação de mudança de assunto (não)."""
    norm = texto.strip().lower()
    return norm in _PALAVRAS_NAO or any(p in norm for p in _PALAVRAS_NAO if len(p) > 3)


def gerar_msg_confirma_mudanca(topico_anterior: str, nome: Optional[str] = None) -> str:
    """Gera mensagem de confirmação natural sobre mudança de assunto."""
    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""
    prefixo = f"{nome_fmt}, " if nome_fmt else ""

    variacoes = [
        (
            f"{prefixo}percebi que a gente estava em *{topico_anterior}*. "
            f"Quer encerrar por aí e partir pro novo assunto?"
        ),
        (
            f"Antes de mudar — a gente ainda estava no *{topico_anterior}*. "
            f"Pode parar aqui e seguir pro que você trouxe agora?"
        ),
        (
            f"{prefixo}o assunto mudou um pouco. Encerramos o *{topico_anterior}* "
            f"ou quer retomar depois? Responde sim pra mudar ou não pra continuar."
        ),
    ]
    return random.choice(variacoes)


def gerar_msg_retomada_topico(topico: str, nome: Optional[str] = None) -> str:
    """Mensagem quando usuário decide CONTINUAR o tópico anterior."""
    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""
    prefixo = f"{nome_fmt}, " if nome_fmt else ""

    variacoes = [
        f"{prefixo}voltando ao *{topico}* — me conta como você quer continuar.",
        f"Beleza, seguimos com *{topico}*. O que você queria aprofundar?",
        f"{prefixo}certo, continuamos com *{topico}*. Me traz o que precisa.",
    ]
    return random.choice(variacoes)


# =============================================================================
# SESSÕES: DETECÇÃO, RESUMO E PERSISTÊNCIA
# =============================================================================

async def verificar_nova_sessao(
    terapeuta_id: str,
    numero_telefone: str,
) -> bool:
    """
    Verifica se o gap desde a última mensagem é maior que SESSION_GAP_HORAS.

    Returns:
        True = nova sessão (ou usuário novo).
    """
    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("chat_estado")
            .select("ultima_mensagem_em")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", numero_telefone)
            .limit(1)
            .execute()
        )

        if not resultado.data:
            return True

        ultima_msg_raw = resultado.data[0].get("ultima_mensagem_em")
        if not ultima_msg_raw:
            return True

        ultima_dt = datetime.fromisoformat(ultima_msg_raw)
        if ultima_dt.tzinfo is None:
            ultima_dt = ultima_dt.replace(tzinfo=timezone.utc)

        gap = datetime.now(timezone.utc) - ultima_dt
        return gap > timedelta(hours=SESSION_GAP_HORAS)

    except Exception as e:
        logger.error(f"Erro ao verificar nova sessão: {e}")
        return False


async def atualizar_timestamp_mensagem(
    terapeuta_id: str,
    numero_telefone: str,
) -> None:
    """
    Atualiza ultima_mensagem_em em chat_estado.
    Chamado no início de cada processamento de mensagem ATIVA.
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("chat_estado").update({
            "ultima_mensagem_em": agora,
            "atualizado_em": agora,
        }).eq("terapeuta_id", terapeuta_id).eq(
            "numero_telefone", numero_telefone
        ).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar timestamp: {e}")


async def salvar_confirmacao_topico(
    terapeuta_id: str,
    numero_telefone: str,
    mensagem_pendente: str,
    topico_anterior: str,
) -> None:
    """Salva o estado de aguardando confirmação de mudança de tópico."""
    supabase = get_supabase()
    try:
        supabase.table("chat_estado").update({
            "aguardando_confirmacao_topico": True,
            "mensagem_pendente_topico": mensagem_pendente[:1000],
            "topico_anterior": topico_anterior[:200],
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("terapeuta_id", terapeuta_id).eq(
            "numero_telefone", numero_telefone
        ).execute()
    except Exception as e:
        logger.error(f"Erro ao salvar confirmação de tópico: {e}")


async def limpar_confirmacao_topico(
    terapeuta_id: str,
    numero_telefone: str,
) -> None:
    """Limpa o estado de confirmação de tópico após resolução."""
    supabase = get_supabase()
    try:
        supabase.table("chat_estado").update({
            "aguardando_confirmacao_topico": False,
            "mensagem_pendente_topico": None,
            "topico_anterior": None,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("terapeuta_id", terapeuta_id).eq(
            "numero_telefone", numero_telefone
        ).execute()
    except Exception as e:
        logger.error(f"Erro ao limpar confirmação de tópico: {e}")


async def gerar_resumo_sessao(
    historico_msgs: list[dict],
    numero_telefone: str,
) -> Optional[str]:
    """
    Usa Claude Haiku para gerar um resumo compacto da sessão.

    Args:
        historico_msgs: Mensagens da sessão a resumir.
        numero_telefone: Usado apenas para logging.

    Returns:
        Texto do resumo (≤ 300 chars) ou None se falhou/insuficiente.
    """
    if len(historico_msgs) < 4:
        return None

    linhas = []
    for msg in historico_msgs[-MAX_MSGS_PARA_RESUMO:]:
        role_label = "Usuário" if msg.get("role") in ("terapeuta", "user") else "Agente"
        conteudo = msg.get("content", "")[:250].replace("\n", " ")
        linhas.append(f"{role_label}: {conteudo}")

    historico_texto = "\n".join(linhas)

    prompt = (
        "Resuma esta conversa em 2-4 linhas corridas. Destaque:\n"
        "- O que foi discutido (caso clínico, pesquisa, conteúdo criado)\n"
        "- Pontos principais e qualquer questão em aberto\n"
        "Seja objetivo. Não use bullets. Terceira pessoa.\n\n"
        f"CONVERSA:\n{historico_texto}\n\nRESUMO:"
    )

    settings = get_settings()
    try:
        import anthropic as _anthropic
        client = _anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        resumo = resp.content[0].text.strip()
        logger.info(f"Resumo gerado para {numero_telefone}: {len(resumo)} chars")
        return resumo
    except Exception as e:
        logger.error(f"Erro ao gerar resumo de sessão: {e}")
        return None


async def salvar_resumo_sessao(
    terapeuta_id: str,
    numero_telefone: str,
    resumo: str,
    total_mensagens: int,
) -> None:
    """Persiste o resumo da sessão no banco."""
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("resumos_sessao").insert({
            "terapeuta_id": terapeuta_id,
            "numero_telefone": numero_telefone,
            "sessao_inicio": agora,
            "sessao_fim": agora,
            "resumo": resumo,
            "total_mensagens": total_mensagens,
        }).execute()
        logger.info(f"Resumo de sessão salvo para {numero_telefone}")
    except Exception as e:
        logger.error(f"Erro ao salvar resumo: {e}")


async def processar_fim_sessao_em_background(
    terapeuta_id: str,
    numero_telefone: str,
    historico_msgs: list[dict],
) -> None:
    """
    Chamado em background quando detectamos nova sessão.
    Gera e salva o resumo da sessão anterior.
    Incrementa total_sessoes no perfil.
    """
    try:
        resumo = await gerar_resumo_sessao(historico_msgs, numero_telefone)
        if resumo:
            await salvar_resumo_sessao(
                terapeuta_id=terapeuta_id,
                numero_telefone=numero_telefone,
                resumo=resumo,
                total_mensagens=len(historico_msgs),
            )

        # Incrementar sessões no perfil
        supabase = get_supabase()
        agora = datetime.now(timezone.utc).isoformat()

        existente = (
            supabase.table("perfil_usuario")
            .select("total_sessoes")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", numero_telefone)
            .limit(1)
            .execute()
        )

        if existente.data:
            total = existente.data[0].get("total_sessoes", 0) + 1
            supabase.table("perfil_usuario").update({
                "total_sessoes": total,
                "atualizado_em": agora,
            }).eq("terapeuta_id", terapeuta_id).eq(
                "numero_telefone", numero_telefone
            ).execute()

    except Exception as e:
        logger.error(f"Erro no processamento de fim de sessão: {e}", exc_info=True)


# =============================================================================
# PERFIL DO USUÁRIO: CARGA E ATUALIZAÇÃO
# =============================================================================

async def carregar_perfil_usuario(
    terapeuta_id: str,
    numero_telefone: str,
) -> dict:
    """
    Carrega o perfil acumulado do usuário.

    Returns:
        Dict com: nome, total_sessoes, total_mensagens, temas_principais,
        preferencias, ultima_sessao_em, tem_dados.
    """
    supabase = get_supabase()

    perfil: dict = {
        "nome": None,
        "total_sessoes": 0,
        "total_mensagens": 0,
        "temas_principais": [],
        "preferencias": {},
        "ultima_sessao_em": None,
        "tem_dados": False,
    }

    try:
        resultado = (
            supabase.table("perfil_usuario")
            .select("*")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", numero_telefone)
            .limit(1)
            .execute()
        )

        if resultado.data:
            row = resultado.data[0]
            perfil.update({
                "nome": row.get("nome"),
                "total_sessoes": row.get("total_sessoes", 0),
                "total_mensagens": row.get("total_mensagens", 0),
                "temas_principais": row.get("temas_principais") or [],
                "preferencias": row.get("preferencias") or {},
                "ultima_sessao_em": row.get("ultima_sessao_em"),
                "tem_dados": True,
            })

    except Exception as e:
        logger.error(f"Erro ao carregar perfil do usuário: {e}")

    return perfil


async def carregar_resumos_anteriores(
    terapeuta_id: str,
    numero_telefone: str,
    limite: int = MAX_RESUMOS_NO_PROMPT,
) -> list[dict]:
    """
    Carrega os resumos das sessões mais recentes (ordem cronológica).

    Returns:
        Lista de dicts: sessao_inicio, resumo, total_mensagens.
    """
    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("resumos_sessao")
            .select("sessao_inicio, resumo, total_mensagens")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", numero_telefone)
            .order("sessao_inicio", desc=True)
            .limit(limite)
            .execute()
        )

        return list(reversed(resultado.data or []))

    except Exception as e:
        logger.error(f"Erro ao carregar resumos de sessões: {e}")
        return []


async def carregar_memoria_completa(
    terapeuta_id: str,
    numero_telefone: str,
) -> dict:
    """
    Carrega toda a memória do usuário em paralelo: perfil + resumos + flag de nova sessão.

    Returns:
        {
            "perfil": dict,
            "resumos_sessoes": list[dict],
            "is_nova_sessao": bool,
        }
    """
    perfil, resumos, is_nova_sessao = await asyncio.gather(
        carregar_perfil_usuario(terapeuta_id, numero_telefone),
        carregar_resumos_anteriores(terapeuta_id, numero_telefone),
        verificar_nova_sessao(terapeuta_id, numero_telefone),
    )

    return {
        "perfil": perfil,
        "resumos_sessoes": resumos,
        "is_nova_sessao": is_nova_sessao,
    }


async def atualizar_perfil_apos_interacao(
    terapeuta_id: str,
    numero_telefone: str,
    nome_usuario: Optional[str],
    mensagem: str,
    modo: str,
) -> None:
    """
    Atualiza o perfil do usuário após cada interação.
    Incrementa frequência de temas detectados, total de mensagens, modo principal.
    Roda em background — nunca bloqueia a resposta.
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    # Detectar temas na mensagem usando a lista do aprendizado
    try:
        from src.rag.aprendizado import _detectar_temas
        temas_novos = _detectar_temas(mensagem.lower())
    except Exception:
        temas_novos = []

    try:
        existente = (
            supabase.table("perfil_usuario")
            .select("*")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", numero_telefone)
            .limit(1)
            .execute()
        )

        if existente.data:
            row = existente.data[0]
            total_msgs = row.get("total_mensagens", 0) + 1

            # Atualizar temas
            temas_atuais: list[dict] = row.get("temas_principais") or []
            temas_dict: dict[str, int] = {
                t["tema"]: t["frequencia"]
                for t in temas_atuais
                if isinstance(t, dict)
            }
            for tema in temas_novos:
                temas_dict[tema] = temas_dict.get(tema, 0) + 1

            temas_sorted = sorted(
                [{"tema": k, "frequencia": v} for k, v in temas_dict.items()],
                key=lambda x: x["frequencia"],
                reverse=True,
            )[:10]

            # Atualizar preferências: contar modos
            prefs: dict = row.get("preferencias") or {}
            modos_count: dict[str, int] = prefs.get("modos_count", {})
            modos_count[modo] = modos_count.get(modo, 0) + 1
            modo_principal = max(modos_count, key=lambda k: modos_count[k])
            prefs["modos_count"] = modos_count
            prefs["modo_principal"] = modo_principal

            supabase.table("perfil_usuario").update({
                "nome": nome_usuario or row.get("nome"),
                "total_mensagens": total_msgs,
                "temas_principais": temas_sorted,
                "preferencias": prefs,
                "ultima_sessao_em": agora,
                "atualizado_em": agora,
            }).eq("terapeuta_id", terapeuta_id).eq(
                "numero_telefone", numero_telefone
            ).execute()

        else:
            # Criar perfil novo
            temas_init = [{"tema": t, "frequencia": 1} for t in temas_novos]
            prefs_init = {
                "modos_count": {modo: 1},
                "modo_principal": modo,
            }
            supabase.table("perfil_usuario").insert({
                "terapeuta_id": terapeuta_id,
                "numero_telefone": numero_telefone,
                "nome": nome_usuario,
                "total_sessoes": 1,
                "total_mensagens": 1,
                "temas_principais": temas_init,
                "preferencias": prefs_init,
                "ultima_sessao_em": agora,
            }).execute()

        logger.debug(f"Perfil atualizado para {numero_telefone}")

    except Exception as e:
        logger.error(f"Erro ao atualizar perfil: {e}", exc_info=True)


# =============================================================================
# FORMATAÇÃO PARA O PROMPT
# =============================================================================

def formatar_memoria_para_prompt(
    memoria: dict,
    nome_usuario: Optional[str] = None,
) -> str:
    """
    Formata a memória do usuário para injeção no system prompt.

    Gera um bloco "MEMÓRIA DO USUÁRIO" que o Claude usa para:
    - Lembrar o contexto de sessões anteriores
    - Personalizar o tom e o nível de profundidade
    - Retomar casos em andamento naturalmente

    Args:
        memoria: Retornado por carregar_memoria_completa()
        nome_usuario: Nome do chat_estado (sobrescreve perfil se presente)

    Returns:
        String pronta para o system prompt.
    """
    perfil = memoria.get("perfil", {})
    resumos = memoria.get("resumos_sessoes", [])

    nome = nome_usuario or perfil.get("nome")
    total_sessoes = perfil.get("total_sessoes", 0)
    total_msgs = perfil.get("total_mensagens", 0)
    temas = perfil.get("temas_principais", [])
    prefs = perfil.get("preferencias", {})

    # Sem dados ainda
    if not perfil.get("tem_dados") and not resumos:
        return (
            "MEMÓRIA DO USUÁRIO:\n"
            "- Primeira interação. Não há histórico. "
            "Seja acolhedor e estabeleça rapport naturalmente."
        )

    partes = ["MEMÓRIA DO USUÁRIO:"]

    if nome:
        partes.append(f"- Nome: {nome}")

    if total_sessoes > 0 or total_msgs > 0:
        partes.append(
            f"- Histórico: {total_sessoes} sessão(ões), {total_msgs} mensagem(ns) no total"
        )

    if temas:
        temas_txt = ", ".join(
            f"{t['tema']} ({t['frequencia']}x)"
            for t in temas[:5]
            if isinstance(t, dict)
        )
        partes.append(f"- Temas recorrentes: {temas_txt}")

    modo_principal = prefs.get("modo_principal")
    if modo_principal:
        partes.append(f"- Modo de uso mais frequente: {modo_principal}")

    if resumos:
        partes.append("\nSESSÕES ANTERIORES (do mais antigo ao mais recente):")
        for resumo in resumos[-MAX_RESUMOS_NO_PROMPT:]:
            data_raw = resumo.get("sessao_inicio", "")
            try:
                dt = datetime.fromisoformat(data_raw)
                data_fmt = dt.strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                data_fmt = "data não disponível"

            total_m = resumo.get("total_mensagens", 0)
            texto_resumo = resumo.get("resumo", "")[:500]
            partes.append(f"[{data_fmt} — {total_m} msgs] {texto_resumo}")

    partes.append(
        "\nDIRETRIZ: Use este contexto para dar continuidade natural à conversa. "
        "NÃO diga 'lembro que você disse' ou 'como mencionei antes'. "
        "Retome o contexto de forma orgânica, como um colega que estava junto na última conversa. "
        "Se o usuário trouxer algo que já apareceu antes, aprofunde sem precisar reexplicar o básico."
    )

    return "\n".join(partes)


def gerar_msg_retomada_sessao(
    resumos: list[dict],
    nome: Optional[str] = None,
) -> Optional[str]:
    """
    Gera mensagem natural de retomada quando detectamos nova sessão
    e a primeira mensagem do usuário é uma saudação.

    Returns:
        Texto da mensagem de retomada, ou None se não há histórico suficiente.
    """
    if not resumos:
        return None

    ultimo = resumos[-1]
    resumo_texto = (ultimo.get("resumo") or "").strip()

    if len(resumo_texto) < 30:
        return None

    import random
    nome_fmt = nome.strip().split()[0].capitalize() if nome else ""
    prefixo = f"{nome_fmt}! " if nome_fmt else ""

    # Truncar resumo para não ficar longo demais na mensagem
    resumo_curto = resumo_texto[:150].rstrip()
    if len(resumo_texto) > 150:
        resumo_curto += "..."

    variacoes = [
        (
            f"{prefixo}Na última sessão a gente viu: {resumo_curto}\n\n"
            f"Quer continuar de onde parou ou tem algo novo hoje?"
        ),
        (
            f"Bem-vindo(a) de volta{', ' + nome_fmt if nome_fmt else ''}. "
            f"Da última vez: {resumo_curto}\n\n"
            f"Seguimos nisso ou você traz algo diferente?"
        ),
        (
            f"{prefixo}Última sessão: {resumo_curto}\n\n"
            f"Me conta o que você traz hoje."
        ),
    ]
    return random.choice(variacoes)
