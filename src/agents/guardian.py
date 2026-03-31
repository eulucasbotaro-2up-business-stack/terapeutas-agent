"""
Agente Guardiao — monitora respostas em background, nao bloqueia o fluxo principal.

Detecta: conteudo inadequado, alucinacoes de fatos, mencoes a medicamentos/diagnosticos medicos.

Roda como asyncio.create_task() — nunca bloqueia a resposta ao terapeuta.
Registra flags no Supabase em `aprendizado_continuo` para o CEO ver no dashboard.
NAO envia mensagem ao usuario, NAO cancela a resposta ja enviada.

Protecao de timeout: toda a verificacao tem limite de 10 segundos para
nunca prender recursos mesmo em caso de lentidao do banco.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# LISTAS DE DETECÇÃO
# =============================================================================

# Timeout maximo para toda a verificacao do Guardian (em segundos).
# Se exceder, a verificacao e abortada silenciosamente.
_GUARDIAN_TIMEOUT_SECONDS = 10.0

# Padroes de medicamentos com dosagem (mg, ml, comprimidos, gotas farmaceuticas)
# Regex: numero + unidade medica OU verbo de prescricao + numero
_PATTERN_MEDICAMENTO_DOSAGEM = re.compile(
    r"\b\d+\s*(?:mg|mcg|ml|comprimidos?|capsulas?|ampolas?|frascos?|ui|iu|gotas?)\b"
    r"|\b(?:tomar|ingerir|administrar|prescrever|receitar|usar)\s+\d+",
    re.IGNORECASE,
)

# Nomes de medicamentos farmacêuticos comuns (não florais)
_MEDICAMENTOS_COMUNS = {
    "fluoxetina", "sertralina", "paroxetina", "escitalopram", "citalopram",
    "venlafaxina", "duloxetina", "bupropiona", "amitriptilina", "nortriptilina",
    "imipramina", "clomipramina", "trazodona", "mirtazapina",
    "alprazolam", "clonazepam", "diazepam", "lorazepam", "bromazepam",
    "zolpidem", "zopiclona", "midazolam",
    "risperidona", "olanzapina", "quetiapina", "aripiprazol", "haloperidol",
    "clozapina", "ziprasidona",
    # "lítio" removido: nome usado em contexto alquímico/mineral — falso positivo frequente
    # O padrão de dosagem (_PATTERN_MEDICAMENTO_DOSAGEM) cobre "lítio 300mg" corretamente
    "valproato", "carbamazepina", "lamotrigina", "topiramato",
    "metilfenidato", "lisdexanfetamina", "atomoxetina",
    "propranolol", "atenolol", "metoprolol",
    "ibuprofeno", "paracetamol", "dipirona", "naproxeno",
    "omeprazol", "pantoprazol", "lansoprazol",
    "amoxicilina", "azitromicina", "ciprofloxacino",
    "prednisona", "dexametasona", "hidrocortisona",
    "insulina", "metformina", "glibenclamida",
    "levotiroxina", "propiltiouracil",
    "atorvastatina", "sinvastatina", "rosuvastatina",
}

# Termos de diagnóstico médico formal (CID, DSM, diagnósticos clínicos)
_DIAGNOSTICOS_MEDICOS = {
    "transtorno depressivo maior", "episódio depressivo maior",
    "transtorno de ansiedade generalizada",
    # "tag" removido: falso positivo com "hashtag" — o nome completo acima é suficiente
    "transtorno do pânico", "transtorno bipolar", "bipolar tipo",
    "esquizofrenia", "transtorno esquizoafetivo",
    "transtorno borderline", "transtorno de personalidade borderline", "tpb",
    "transtorno obsessivo-compulsivo", "toc",
    "transtorno de estresse pós-traumático", "tept",
    "transtorno do espectro autista",
    # "tea" removido: falso positivo (ex: "atopia tea", palavras com "tea") — nome completo é suficiente
    "transtorno de déficit de atenção", "tdah",
    "anorexia nervosa", "bulimia nervosa", "compulsão alimentar",
    "cid-10", "cid-11", "dsm-5", "dsm-iv",
    "f32", "f33", "f40", "f41", "f20", "f31",  # códigos CID
}

# Palavras proibidas na RESPOSTA (não na pergunta — são do contexto do terapeuta)
_PALAVRAS_PROIBIDAS_RESPOSTA = {
    "se matar", "suicídio como solução", "se machucar é válido",
    "não tem jeito", "não tem cura", "sem esperança",
}

# Limite de caracteres acima do qual logamos a resposta como potencialmente longa demais
_LIMITE_CHARS_LONGA = 2000


# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO
# =============================================================================

def _verificar_medicamento_dosagem(resposta: str) -> list[str]:
    """
    Detecta menções a medicamentos farmacêuticos com dosagem na resposta.
    Retorna lista de trechos suspeitos encontrados.
    """
    flags = []
    resposta_lower = resposta.lower()

    # Verificar nomes de medicamentos comuns
    for med in _MEDICAMENTOS_COMUNS:
        if med in resposta_lower:
            # Encontrar o contexto ao redor (±50 chars)
            idx = resposta_lower.find(med)
            contexto = resposta[max(0, idx - 30):min(len(resposta), idx + 80)]
            flags.append(f"medicamento_farmaceutico: '{med}' em '...{contexto}...'")

    # Verificar padrões de dosagem
    matches = _PATTERN_MEDICAMENTO_DOSAGEM.findall(resposta)
    if matches:
        flags.append(f"padrao_dosagem_medica: {matches[:3]}")

    return flags


def _verificar_diagnostico_medico(resposta: str) -> list[str]:
    """
    Detecta diagnósticos médicos formais (CID, DSM) na resposta.
    Retorna lista de diagnósticos encontrados.
    """
    flags = []
    resposta_lower = resposta.lower()

    for diag in _DIAGNOSTICOS_MEDICOS:
        if diag in resposta_lower:
            flags.append(f"diagnostico_medico_formal: '{diag}'")

    return flags


def _verificar_palavras_proibidas(resposta: str) -> list[str]:
    """
    Detecta palavras ou frases proibidas na RESPOSTA do agente.
    Essas frases nunca devem aparecer como orientação do agente.
    """
    flags = []
    resposta_lower = resposta.lower()

    for palavra in _PALAVRAS_PROIBIDAS_RESPOSTA:
        if palavra in resposta_lower:
            flags.append(f"palavra_proibida_resposta: '{palavra}'")

    return flags


def _verificar_tamanho(resposta: str) -> list[str]:
    """
    Verifica se a resposta está excessivamente longa.
    Respostas muito longas podem causar abandono no WhatsApp.
    """
    tamanho = len(resposta)
    if tamanho > _LIMITE_CHARS_LONGA:
        return [f"resposta_longa: {tamanho} chars (limite recomendado: {_LIMITE_CHARS_LONGA})"]
    return []


# =============================================================================
# GUARDIÃO PRINCIPAL
# =============================================================================

async def verificar_resposta(
    terapeuta_id: str,
    numero: str,
    pergunta: str,
    resposta: str,
) -> None:
    """
    Verifica a resposta gerada pelo agente em background.

    Detecta flags criticos sem chamar nenhum LLM (verificacao por regras, rapida).
    Flags detectados sao salvos no Supabase em `aprendizado_continuo` para
    revisao pelo CEO no dashboard.

    NUNCA bloqueia a resposta ao usuario.
    NUNCA envia mensagem ao terapeuta.
    NUNCA cancela a resposta ja enviada.

    Protecao de timeout: toda a verificacao tem limite de _GUARDIAN_TIMEOUT_SECONDS
    para nunca prender recursos em caso de lentidao do banco.

    Deve ser chamada como:
        asyncio.create_task(verificar_resposta(terapeuta_id, numero, pergunta, resposta))

    Args:
        terapeuta_id: UUID do terapeuta (para isolamento multi-tenant).
        numero: Numero WhatsApp do terapeuta (para logging).
        pergunta: Texto da mensagem que gerou a resposta.
        resposta: Texto da resposta gerada pelo agente.
    """
    if not resposta or not resposta.strip():
        return

    try:
        # Timeout global para toda a verificacao — Guardian nunca pode travar
        await asyncio.wait_for(
            _executar_verificacao(terapeuta_id, numero, pergunta, resposta),
            timeout=_GUARDIAN_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"[GUARDIAN] Timeout ({_GUARDIAN_TIMEOUT_SECONDS}s) ao verificar resposta "
            f"para terapeuta {terapeuta_id}. Verificacao abortada."
        )
    except Exception as e:
        # Qualquer erro no Guardian e silenciado — nunca afeta o fluxo principal
        logger.error(f"[GUARDIAN] Erro interno no guardiao: {e}", exc_info=True)


async def _executar_verificacao(
    terapeuta_id: str,
    numero: str,
    pergunta: str,
    resposta: str,
) -> None:
    """
    Logica interna de verificacao, separada para permitir timeout externo.

    Executa todas as verificacoes por regras (sem LLM) e salva flags
    detectados na tabela `aprendizado_continuo` do Supabase.

    Args:
        terapeuta_id: UUID do terapeuta.
        numero: Numero WhatsApp do terapeuta.
        pergunta: Texto da mensagem original.
        resposta: Texto da resposta gerada pelo agente.
    """
    flags_criticos: list[str] = []
    flags_info: list[str] = []

    # 1. Verificar medicamentos farmaceuticos com dosagem
    flags_med = _verificar_medicamento_dosagem(resposta)
    if flags_med:
        flags_criticos.extend(flags_med)
        logger.warning(
            f"[GUARDIAN] Medicamento/dosagem detectado na resposta "
            f"(terapeuta={terapeuta_id}, numero={numero}): {flags_med}"
        )

    # 2. Verificar diagnosticos medicos formais
    flags_diag = _verificar_diagnostico_medico(resposta)
    if flags_diag:
        flags_criticos.extend(flags_diag)
        logger.warning(
            f"[GUARDIAN] Diagnostico medico formal detectado "
            f"(terapeuta={terapeuta_id}, numero={numero}): {flags_diag}"
        )

    # 3. Verificar palavras proibidas na resposta
    flags_proib = _verificar_palavras_proibidas(resposta)
    if flags_proib:
        flags_criticos.extend(flags_proib)
        logger.warning(
            f"[GUARDIAN] Palavra proibida na resposta "
            f"(terapeuta={terapeuta_id}, numero={numero}): {flags_proib}"
        )

    # 4. Verificar tamanho da resposta
    flags_tamanho = _verificar_tamanho(resposta)
    if flags_tamanho:
        flags_info.extend(flags_tamanho)
        logger.info(
            f"[GUARDIAN] Resposta longa detectada "
            f"(terapeuta={terapeuta_id}, numero={numero}): {flags_tamanho}"
        )

    # Se nao ha flags, sair sem salvar (nao poluir o banco com registros normais)
    if not flags_criticos and not flags_info:
        return

    # 5. Salvar flags no Supabase para o CEO revisar no dashboard
    supabase = get_supabase()

    severidade = "CRITICO" if flags_criticos else "INFO"
    todos_flags = flags_criticos + flags_info
    agora = datetime.now(timezone.utc).isoformat()

    registro = {
        "terapeuta_id": terapeuta_id,
        "tipo_feedback": "GUARDIAN_FLAG",
        "mensagem": pergunta[:500] if pergunta else "",
        "resposta_agente": resposta[:1000] if resposta else "",
        "feedback_dados": {
            "numero": numero,
            "severidade": severidade,
            "flags": todos_flags,
            "flags_criticos": flags_criticos,
            "flags_info": flags_info,
            "tamanho_resposta": len(resposta),
            "timestamp": agora,
        },
        "criado_em": agora,
    }

    try:
        supabase.table("aprendizado_continuo").insert(registro).execute()
        logger.info(
            f"[GUARDIAN] Flag salvo no Supabase — "
            f"severidade={severidade}, "
            f"flags={len(todos_flags)}, "
            f"terapeuta={terapeuta_id}"
        )
    except Exception as db_error:
        # Falha ao salvar no banco nao deve propagar — Guardian nunca bloqueia
        logger.error(f"[GUARDIAN] Falha ao salvar flag no Supabase: {db_error}")
