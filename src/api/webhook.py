"""
Rota de webhook para receber mensagens do WhatsApp via Evolution API e Meta Cloud API.
Processa a mensagem com RAG e responde automaticamente ao paciente.
"""

import asyncio
import base64
import io
import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.core.prompts import (
    detectar_modo,
    ModoOperacao,
    MENSAGEM_FORA_ESCOPO,
)
from src.agents.router import rotear_mensagem
from src.agents.specialists import (
    get_prompt_agente_caso_clinico,
    get_prompt_agente_metodo,
    get_prompt_agente_conteudo,
    # get_prompt_agente_saudacao não é usado aqui:
    # SAUDACAO usa gerar_saudacao_ativo() diretamente — sem LLM/RAG por design
)
from src.agents.guardian import verificar_resposta
from src.core.estado import (
    obter_ou_criar_estado,
    validar_codigo,
    liberar_acesso,
    registrar_nome_usuario,
    salvar_nome_sugerido,
    confirmar_nome_sugerido,
    rejeitar_nome_sugerido,
    detectar_profanidade,
    registrar_violacao,
    atualizar_onboarding,
    limpar_onboarding,
    gerar_msg_bloqueio,
    gerar_msg_ja_bloqueado,
    gerar_saudacao_ativo,
    gerar_resposta_confusao,
    gerar_msg_boas_vindas_nome,
    gerar_msg_confirmar_nome,
    MSG_PEDIR_NOME_NOVAMENTE,
    MSG_NOME_NAO_IDENTIFICADO,
    MSGS_ONBOARDING,
    MSG_CODIGO_INVALIDO,
    MSG_CODIGO_INVALIDO_FINAL,
    MSGS_ACESSO_LIBERADO,
    MSG_AVISO_1,
    MSG_AVISO_2,
)
from src.core.assinatura import ativar_acesso_com_codigo
from src.core.rate_limiter import aguardar_antes_de_enviar
from src.core.memoria import (
    carregar_memoria_completa,
    atualizar_timestamp_mensagem,
    atualizar_perfil_apos_interacao,
    processar_fim_sessao_em_background,
    formatar_memoria_para_prompt,
    gerar_msg_retomada_sessao,
    limpar_confirmacao_topico,
)
from src.rag.retriever import buscar_contexto
from src.rag.generator import gerar_resposta, classificar_intencao
from src.rag.astrologia import calcular_mapa_natal, extrair_dados_nascimento, extrair_dados_nascimento_llm, gerar_mapa_completo
from src.agents.capabilities import (
    KEYWORDS_PEDIDO_MAPA, KEYWORDS_REFAZER_MAPA,
    NUMERO_SUPORTE,
    MSG_ERRO_GENERICO, MSG_ERRO_MAPA_IMAGEM, MSG_ERRO_MAPA_CALCULO, MSG_ERRO_MENSAGEM,
)
from src.rag.aprendizado import (
    analisar_conversa,
    carregar_contexto_terapeuta,
    formatar_contexto_personalizado,
)
from src.whatsapp.evolution import EvolutionClient
from src.whatsapp.meta_cloud import MetaCloudClient
from src.core.ux_rules import humanizar_resposta
from src.core.diagnostico_auto import processar_diagnostico_auto
from src.whatsapp.messages import (
    extrair_numero_mensagem,
    eh_mensagem_valida,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook WhatsApp"])

# WARNING: In-memory dedup — resets on deploy. Duplicates may occur post-deploy.
# TODO: Move to Redis/database for production scale.
# Armazena (message_id -> timestamp). Limpeza automática após 5 minutos.
_PROCESSED_MESSAGE_IDS: "OrderedDict[str, float]" = OrderedDict()
_DEDUP_TTL_SECONDS = 300
_DEDUP_MAX_SIZE = 1000
_DEDUP_LOCK: asyncio.Lock | None = None  # Inicializado lazy para evitar problema com event loop


def _get_dedup_lock() -> asyncio.Lock:
    global _DEDUP_LOCK
    if _DEDUP_LOCK is None:
        _DEDUP_LOCK = asyncio.Lock()
    return _DEDUP_LOCK

# Contador de falhas consecutivas de geração de mapa por número de paciente.
# Após _MAPA_MAX_TENTATIVAS falhas, envia mensagem de suporte e para de tentar.
# NOTA: Intencionalmente in-memory — reset entre deploys é aceitável pois apenas
# controla retries de curto prazo. No pior caso, o paciente recebe mais uma
# tentativa de geração de mapa após o restart.
_MAPA_FALHAS: dict[str, int] = {}
_MAPA_MAX_TENTATIVAS = 3

# Cache de paciente ativo por número do remetente (terapeuta falando sobre paciente X)
# Formato: {(terapeuta_id, numero_remetente): {"paciente_id": str, "paciente_nome": str, "timestamp": float}}
_PACIENTE_ATIVO_CACHE: dict[tuple[str, str], dict] = {}
_PACIENTE_ATIVO_TTL = 1800  # 30 minutos sem mencionar = limpa vínculo


async def _ja_processado(message_id: str) -> bool:
    """Retorna True se o message_id já foi processado recentemente.
    Thread-safe: usa asyncio.Lock para evitar race conditions no OrderedDict."""
    if not message_id:
        return False
    agora = time.monotonic()
    async with _get_dedup_lock():
        # Limpar entradas expiradas (FIFO — as mais antigas estão no início)
        while _PROCESSED_MESSAGE_IDS:
            oldest_id, oldest_ts = next(iter(_PROCESSED_MESSAGE_IDS.items()))
            if agora - oldest_ts > _DEDUP_TTL_SECONDS:
                _PROCESSED_MESSAGE_IDS.popitem(last=False)
            else:
                break
        # Limitar tamanho máximo
        while len(_PROCESSED_MESSAGE_IDS) >= _DEDUP_MAX_SIZE:
            _PROCESSED_MESSAGE_IDS.popitem(last=False)
        if message_id in _PROCESSED_MESSAGE_IDS:
            return True
        _PROCESSED_MESSAGE_IDS[message_id] = agora
    return False


# =============================================
# FUNÇÕES AUXILIARES
# =============================================

def _buscar_terapeuta_por_instancia(instance_name: str) -> dict | None:
    """
    Busca o terapeuta associado à instância da Evolution API.
    Cada terapeuta tem uma instância própria no Evolution.
    """
    supabase = get_supabase()

    resultado = (
        supabase.table("terapeutas")
        .select("*")
        .eq("evolution_instance", instance_name)
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if resultado.data and len(resultado.data) > 0:
        return resultado.data[0]

    return None


def _buscar_historico_conversa(
    terapeuta_id: str,
    paciente_numero: str,
    limite: int = 10,
) -> list[dict]:
    """
    Busca as ultimas mensagens da conversa entre terapeuta e paciente.
    Essencial para MODO CONSULTA multi-turno (anamnese requer varios turnos).

    Args:
        terapeuta_id: UUID do terapeuta.
        paciente_numero: Numero do WhatsApp do paciente/terapeuta.
        limite: Numero maximo de mensagens a buscar (ultimas N).

    Returns:
        Lista de dicts com role e content, ordenada cronologicamente.
    """
    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("conversas")
            .select("mensagem_paciente, resposta_agente, criado_em")
            .eq("terapeuta_id", terapeuta_id)
            .eq("paciente_numero", paciente_numero)
            .order("criado_em", desc=True)
            .limit(limite)
            .execute()
        )

        if not resultado.data:
            return []

        # Converter para formato de historico (mais antigo primeiro)
        historico = []
        for registro in reversed(resultado.data):
            if registro.get("mensagem_paciente"):
                historico.append({
                    "role": "terapeuta",
                    "content": registro["mensagem_paciente"],
                })
            if registro.get("resposta_agente"):
                historico.append({
                    "role": "agente",
                    "content": registro["resposta_agente"],
                })

        logger.info(
            f"Historico recuperado: {len(historico)} mensagens "
            f"(terapeuta={terapeuta_id}, paciente={paciente_numero})"
        )
        return historico

    except Exception as e:
        logger.error(f"Erro ao buscar historico: {e}")
        return []


def _salvar_conversa_sync(
    terapeuta_id: str,
    paciente_numero: str,
    mensagem_paciente: str,
    resposta_agente: str,
    intencao: str,
    paciente_vinculado_id: str | None = None,
) -> None:
    """Versão síncrona pura — não chamar diretamente em contexto async."""
    supabase = get_supabase()
    row = {
        "id": str(uuid4()),
        "terapeuta_id": terapeuta_id,
        "paciente_numero": paciente_numero,
        "mensagem_paciente": mensagem_paciente,
        "resposta_agente": resposta_agente,
        "intencao": intencao,
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }
    if paciente_vinculado_id:
        row["paciente_vinculado_id"] = paciente_vinculado_id
    supabase.table("conversas").insert(row).execute()


async def _salvar_conversa(
    terapeuta_id: str,
    paciente_numero: str,
    mensagem_paciente: str,
    resposta_agente: str,
    intencao: str,
    paciente_vinculado_id: str | None = None,
) -> None:
    """
    Salva o registro da conversa na tabela 'conversas' para historico.
    Usa asyncio.to_thread para não bloquear o event loop com IO síncrono do Supabase.
    """
    try:
        await asyncio.to_thread(
            _salvar_conversa_sync,
            terapeuta_id, paciente_numero, mensagem_paciente, resposta_agente, intencao,
            paciente_vinculado_id,
        )
        logger.info(
            f"Conversa salva — terapeuta={terapeuta_id}, paciente={paciente_numero}"
            + (f", vinculado={paciente_vinculado_id}" if paciente_vinculado_id else "")
        )
    except Exception as e:
        # Nao queremos que falha ao salvar conversa impeca a resposta
        logger.error(f"Erro ao salvar conversa: {e}")


def _detectar_paciente_vinculado_sync(
    terapeuta_id: str,
    numero_remetente: str,
    mensagem: str,
    resposta: str,
    modo: str,
) -> str | None:
    """
    Detecta se a conversa se refere a um paciente específico e retorna o paciente_id.
    Usa Haiku para classificar menções a pacientes na mensagem e resposta.
    Mantém cache do paciente ativo por sessão de conversa.

    Retorna None se:
    - A mensagem não é sobre um paciente específico (ex: conteúdo para rede social)
    - O terapeuta mudou de assunto para algo genérico
    """
    import anthropic as _anthropic

    agora = time.monotonic()
    cache_key = (terapeuta_id, numero_remetente)

    # Limpar cache expirado
    if cache_key in _PACIENTE_ATIVO_CACHE:
        if agora - _PACIENTE_ATIVO_CACHE[cache_key]["timestamp"] > _PACIENTE_ATIVO_TTL:
            del _PACIENTE_ATIVO_CACHE[cache_key]

    # Buscar lista de pacientes do terapeuta para dar contexto ao LLM
    supabase = get_supabase()
    pac_res = supabase.table("pacientes").select("id, nome, numero_telefone").eq(
        "terapeuta_id", terapeuta_id
    ).eq("status", "ativo").execute()
    pacientes = pac_res.data or []

    if not pacientes:
        return None

    # Montar lista de pacientes para o prompt
    lista_pac = "\n".join(
        f"- ID: {p['id']} | Nome: {p['nome']} | Tel: {p['numero_telefone']}"
        for p in pacientes
    )

    # Contexto do paciente ativo no cache
    pac_ativo_info = ""
    if cache_key in _PACIENTE_ATIVO_CACHE:
        pac_ativo_info = (
            f"\nPACIENTE ATIVO NA CONVERSA ATUAL: {_PACIENTE_ATIVO_CACHE[cache_key]['paciente_nome']} "
            f"(ID: {_PACIENTE_ATIVO_CACHE[cache_key]['paciente_id']})"
        )

    prompt = f"""Analise esta troca de mensagens entre um terapeuta e sua IA assistente.
Determine se a conversa se refere a um paciente específico da lista abaixo.

PACIENTES CADASTRADOS:
{lista_pac}
{pac_ativo_info}

MENSAGEM DO TERAPEUTA: {mensagem[:500]}
RESPOSTA DA IA: {resposta[:500]}
MODO DA CONVERSA: {modo}

REGRAS:
1. Se o terapeuta menciona um paciente pelo nome ou está claramente discutindo o caso de um paciente, responda com o ID do paciente.
2. Se já havia um paciente ativo e a conversa CONTINUA sobre o mesmo tema clínico (sem mudança de assunto), mantenha o mesmo paciente.
3. Se o terapeuta mudou de assunto (pediu conteúdo para rede social, fez pergunta genérica sobre método, pediu algo não relacionado a um paciente específico), responda NENHUM.
4. Se não é possível identificar qual paciente está sendo discutido, responda NENHUM.

Responda APENAS com o ID do paciente (UUID) ou a palavra NENHUM. Nada mais."""

    try:
        settings = get_settings()
        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        resultado = response.content[0].text.strip()

        if resultado == "NENHUM" or len(resultado) < 10:
            # Sem paciente vinculado — limpar cache se existir
            if cache_key in _PACIENTE_ATIVO_CACHE:
                del _PACIENTE_ATIVO_CACHE[cache_key]
            return None

        # Validar que o ID retornado é de um paciente real
        pac_ids = {p["id"] for p in pacientes}
        if resultado in pac_ids:
            # Atualizar cache
            nome_pac = next((p["nome"] for p in pacientes if p["id"] == resultado), "")
            _PACIENTE_ATIVO_CACHE[cache_key] = {
                "paciente_id": resultado,
                "paciente_nome": nome_pac,
                "timestamp": agora,
            }
            # Evitar crescimento ilimitado do cache
            if len(_PACIENTE_ATIVO_CACHE) > 500:
                keys_to_remove = list(_PACIENTE_ATIVO_CACHE.keys())[:100]
                for k in keys_to_remove:
                    del _PACIENTE_ATIVO_CACHE[k]
            logger.info(f"Paciente vinculado detectado: {nome_pac} ({resultado})")
            return resultado

        logger.warning(f"Haiku retornou ID inválido: {resultado}")
        return None

    except Exception as e:
        logger.warning(f"Falha na detecção de paciente vinculado: {e}")
        return None


async def _detectar_paciente_vinculado(
    terapeuta_id: str,
    numero_remetente: str,
    mensagem: str,
    resposta: str,
    modo: str,
) -> str | None:
    """Wrapper async para detecção de paciente vinculado."""
    try:
        return await asyncio.to_thread(
            _detectar_paciente_vinculado_sync,
            terapeuta_id, numero_remetente, mensagem, resposta, modo,
        )
    except Exception as e:
        logger.warning(f"Erro async na detecção de paciente: {e}")
        return None


# =============================================
# PROCESSAMENTO EM BACKGROUND
# =============================================

async def _enviar_sequencia_evolution(
    msgs: list[str],
    evolution: "EvolutionClient",
    instance: str,
    numero: str,
    delay: float = 4.0,
) -> None:
    """
    Envia uma lista de mensagens com rate limiting (Evolution API).
    Delay padrão: 4s entre mensagens para o terapeuta conseguir ler cada bloco.
    """
    for i, msg in enumerate(msgs):
        await aguardar_antes_de_enviar(numero, sequencial=True)
        if i == 0 and len(msgs) > 1:
            await asyncio.sleep(1.5)  # pausa breve antes da 1ª mensagem de uma sequência
        elif i > 0:
            await asyncio.sleep(delay)
        await evolution.enviar_mensagem(instance=instance, numero=numero, texto=msg)



# Mapa completo de MIME types de áudio/vídeo → extensão para Whisper
# Whisper aceita: flac, m4a, mp3, mp4, mpeg, mpga, oga, ogg, wav, webm
_AUDIO_EXT_MAP: dict[str, str] = {
    "audio/ogg": "ogg",           # WhatsApp padrão (OGG/OPUS)
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/mp4a-latm": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/webm": "webm",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/aac": "aac",
    "audio/amr": "amr",
    "audio/3gpp": "3gp",
    "audio/flac": "flac",
    "video/mp4": "mp4",
    "video/3gpp": "3gp",
    "video/webm": "webm",
    "video/mpeg": "mpeg",
    "video/quicktime": "mp4",
}

_MAX_AUDIO_BYTES = 24 * 1024 * 1024  # 24MB (Whisper limit is 25MB)


def _extrair_audio_bytes(b64_data: str) -> bytes | None:
    """
    Decodifica base64 de mídia, removendo prefixo data-URI se presente.
    Evolution API às vezes retorna: 'data:audio/ogg;base64,AAAA...'
    Em vez de somente 'AAAA...'
    """
    import base64 as _b64
    if not b64_data:
        return None
    # Remover prefixo data-URI (data:audio/ogg;base64,...)
    if "base64," in b64_data:
        b64_data = b64_data.split("base64,", 1)[1]
    # Remover espaços/quebras de linha (alguns SDKs formatam o base64)
    b64_data = b64_data.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return _b64.b64decode(b64_data, validate=False)
    except Exception as e:
        logger.error(f"Falha ao decodificar base64: {e} | primeiros 50 chars: {b64_data[:50]}")
        return None


def _criar_acesso_portal_sync(email: str, senha: str, nome: str, telefone: str) -> str:
    """Cria terapeuta + portal_auth. Retorna terapeuta_id. Sync — chamar via to_thread."""
    import bcrypt
    from src.core.supabase_client import get_supabase
    from uuid import uuid4
    sb = get_supabase()
    existing = sb.table("terapeutas").select("id").eq("email", email).limit(1).execute()
    if existing.data:
        t_id = existing.data[0]["id"]
        sb.table("terapeutas").update({"nome": nome, "telefone": telefone}).eq("id", t_id).execute()
    else:
        t_id = str(uuid4())
        sb.table("terapeutas").insert({"id": t_id, "nome": nome, "email": email, "telefone": telefone, "especialidade": "Alquimia Terapêutica"}).execute()
    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    existing_auth = sb.table("portal_auth").select("id").eq("terapeuta_id", t_id).limit(1).execute()
    if existing_auth.data:
        sb.table("portal_auth").update({"senha_hash": senha_hash}).eq("terapeuta_id", t_id).execute()
    else:
        sb.table("portal_auth").insert({"terapeuta_id": t_id, "senha_hash": senha_hash}).execute()
    return t_id


def _extrair_texto_para_codigo(texto: str) -> str:
    """
    Remove prefixos de mídia transcrita do texto antes de validar como código.
    Se o usuário enviou o código por áudio, o texto vem como:
    '[Mensagem de áudio] eu quero testar'
    Precisamos extrair só 'eu quero testar' para a validação funcionar.
    """
    _prefixos_midia = [
        "[Mensagem de áudio] ",
        "[Imagem recebida] ",
        "[PDF recebido]\n",
        "[PDF recebido] ",
    ]
    for prefixo in _prefixos_midia:
        if texto.startswith(prefixo):
            return texto[len(prefixo):]
    return texto


def _contar_tentativas_codigo(terapeuta_id: str, numero_paciente: str) -> int:
    """Conta quantas tentativas inválidas de código este número já fez."""
    try:
        sb = get_supabase()
        res = sb.table("conversas").select("id", count="exact").eq(
            "terapeuta_id", terapeuta_id
        ).eq(
            "paciente_numero", numero_paciente
        ).eq(
            "intencao", "CODIGO_INVALIDO"
        ).execute()
        return res.count or 0
    except Exception:
        return 0


async def _extrair_nome_com_llm(texto: str, settings) -> str:
    """
    Usa Claude Haiku para extrair o nome próprio de uma mensagem conversacional.
    Ex: "Oi, bom dia! Meu nome é Fulana de Tal" → "Fulana de Tal"
    Ex: "Lucas" → "Lucas"
    Retorna string vazia se não encontrar nome claro.
    """
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = (
        "Extraia apenas o nome próprio da pessoa nesta mensagem.\n"
        "Responda SOMENTE com o nome (pode ser primeiro nome + sobrenome).\n"
        "Se a mensagem não contiver um nome, responda com: SEM_NOME\n\n"
        f"Mensagem: {texto}\n\n"
        "Nome:"
    )
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[{"role": "user", "content": prompt}],
        )
        nome = resp.content[0].text.strip()
        if nome.upper() == "SEM_NOME" or not nome or len(nome) > 60:
            return ""
        # Garantir que é texto com letras (não lixo)
        if not any(c.isalpha() for c in nome):
            return ""
        return nome
    except Exception as e:
        logger.warning(f"LLM name extraction falhou: {e}")
        return ""


def _normalizar_mime(raw_mime: str, fallback: str = "audio/ogg") -> str:
    """Normaliza MIME type removendo parâmetros extras (;codecs=opus etc.)"""
    if not raw_mime:
        return fallback
    base = raw_mime.split(";")[0].strip().lower()
    return base if base else fallback


# Alucinações conhecidas do Whisper para silêncio/ruído de fundo.
# Whisper tende a gerar estas frases quando o áudio é muito curto, silencioso
# ou contém apenas ruído de fundo sem fala real.
_WHISPER_ALUCINACOES = {
    "Obrigado.",
    "Obrigado",
    "Obrigada.",
    "Obrigada",
    "Legendas por",
    "Transcrição por",
    "Inscreva-se no canal",
    "Inscreva-se",
    "Se inscreva no canal",
    "Curta e se inscreva",
    "...",
    "…",
    ".",
    ",",
    "- -",
    "♪",
    "♫",
    "[Música]",
    "[música]",
    "[Aplausos]",
    "[aplausos]",
    "[Silêncio]",
    "[silêncio]",
    "[Inaudível]",
    "[inaudível]",
}


def _eh_transcricao_valida(texto: str) -> bool:
    """
    Valida se a transcrição do Whisper é utilizável.

    Retorna False nos casos:
    - Texto vazio ou apenas espaços
    - Menos de 3 palavras (provável ruído ou áudio muito curto)
    - Apenas pontuação ou caractere único
    - Texto é uma alucinação conhecida do Whisper para silêncio/ruído

    Retorna True se a transcrição parece conteúdo real.
    """
    if not texto or not texto.strip():
        return False

    texto_limpo = texto.strip()

    # Apenas pontuação ou caractere único
    if len(texto_limpo) <= 1:
        return False

    # Somente pontuação/símbolos (sem nenhuma letra ou dígito)
    if not any(c.isalnum() for c in texto_limpo):
        return False

    # Alucinação conhecida (comparação exata e também prefixo para capturar variantes)
    if texto_limpo in _WHISPER_ALUCINACOES:
        return False
    for alucinacao in _WHISPER_ALUCINACOES:
        if len(alucinacao) > 4 and texto_limpo.startswith(alucinacao):
            return False

    # Menos de 3 palavras — muito curto para ser fala real
    palavras = texto_limpo.split()
    if len(palavras) < 3:
        return False

    return True


async def _whisper_transcrever(
    audio_bytes: bytes,
    mime_type: str,
    settings: object,
) -> str:
    """
    Chama OpenAI Whisper com retry automático e validação de qualidade.

    Tentativa 1: idioma forçado 'pt' (mais preciso para português).
                 Se o resultado for inválido (< 3 palavras, alucinação conhecida),
                 descarta e passa para tentativa 2 sem forçar idioma.
    Tentativa 2: detecção automática de idioma (fallback para áudios ambíguos).

    Retorna texto transcrito validado ou string vazia se ambas falharem.
    """
    from openai import AsyncOpenAI
    oai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)  # type: ignore[attr-defined]

    base_ct = _normalizar_mime(mime_type)
    ext = _AUDIO_EXT_MAP.get(base_ct, "ogg")
    filename = f"audio.{ext}"

    logger.info(
        f"Whisper: mime={base_ct}, ext={ext}, "
        f"tamanho={len(audio_bytes)//1024}KB"
    )

    for tentativa, lingua in enumerate(["pt", None], start=1):
        try:
            kwargs: dict = dict(
                model="whisper-1",
                file=(filename, io.BytesIO(audio_bytes), base_ct),
                response_format="text",
                prompt="Transcreva o áudio em português com pontuação correta.",
            )
            if lingua:
                kwargs["language"] = lingua
            transcript = await oai.audio.transcriptions.create(**kwargs)
            texto = (transcript if isinstance(transcript, str) else transcript.text).strip()

            if not texto:
                logger.info(f"Whisper tentativa {tentativa}: transcrição vazia, tentando próxima...")
                continue

            if not _eh_transcricao_valida(texto):
                logger.warning(
                    f"Whisper tentativa {tentativa} (lingua={lingua}): "
                    f"transcrição inválida/alucinação descartada: '{texto[:80]}'"
                )
                continue

            logger.info(
                f"Whisper OK (tentativa={tentativa}, lingua={lingua}): "
                f"'{texto[:100]}'"
            )
            return texto

        except Exception as e:
            logger.warning(f"Whisper tentativa {tentativa} falhou ({type(e).__name__}): {e}")

    return ""


async def _transcrever_audio_evolution(
    evolution: "EvolutionClient",
    instance_name: str,
    numero_paciente: str,
    payload: dict,
    msg_type: str = "audio",
) -> str:
    """
    Baixa e transcreve áudio/vídeo via Evolution API + OpenAI Whisper.

    Fluxo:
    1. Chama /message/download-media/{instance} com o objeto data do webhook
    2. Extrai base64 (remove prefixo data-URI se presente)
    3. Valida tamanho mínimo (< 1KB) e máximo (> 24MB)
    4. Transcreve com Whisper (pt → auto, com retry + validação de qualidade)
    5. Retorna texto prefixado com [Mensagem de áudio] ou marcador de erro

    NOTA: Não envia mensagem intermediária "Transcrevendo..." — resposta direta
    após transcrição proporciona melhor UX (sem mensagens fantasmas).
    """
    settings = get_settings()

    # 1. Baixar mídia via Evolution API
    mensagem_data = payload.get("data", {})
    logger.info(
        f"Evolution baixar_midia: instance={instance_name}, "
        f"messageType={mensagem_data.get('messageType', '?')}"
    )
    try:
        midia = await evolution.baixar_midia(instance_name, mensagem_data)
    except Exception as e:
        logger.error(f"Evolution baixar_midia falhou ({type(e).__name__}): {e}")
        return "[AUDIO_DOWNLOAD_FALHOU]"

    # Log do que a Evolution API retornou (sem o base64 para não poluir)
    logger.info(
        f"Evolution baixar_midia resposta: "
        f"keys={list(midia.keys())}, "
        f"mimeType={midia.get('mimeType', '?')}, "
        f"mediaType={midia.get('mediaType', '?')}, "
        f"base64_len={len(midia.get('base64', ''))}"
    )

    # 2. Extrair e decodificar base64 (com remoção de data-URI prefix)
    b64_data = midia.get("base64", "")
    if not b64_data:
        logger.warning("Evolution baixar_midia: base64 vazio ou ausente")
        return "[AUDIO_SEM_CONTEUDO]"

    audio_bytes = _extrair_audio_bytes(b64_data)
    if not audio_bytes:
        logger.error("Falha ao decodificar base64 do áudio Evolution")
        return "[AUDIO_SEM_CONTEUDO]"

    # 3. Validar tamanho mínimo (< 1KB → provavelmente não é áudio real)
    if len(audio_bytes) < 1024:
        logger.warning(
            f"Áudio muito pequeno: {len(audio_bytes)} bytes "
            f"(< 1KB) para {numero_paciente} — descartando"
        )
        return "[AUDIO_SEM_CONTEUDO]"

    # 3b. Validar tamanho máximo (Whisper aceita até 25MB)
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        logger.warning(
            f"Áudio muito grande: {len(audio_bytes)/1024/1024:.1f}MB "
            f"(limite {_MAX_AUDIO_BYTES//1024//1024}MB)"
        )
        return "[MIDIA_MUITO_GRANDE]"

    # 4. Determinar MIME type (prioridade: mimeType do response > fileName > fallback ogg)
    mime_raw = midia.get("mimeType", "") or midia.get("mimetype", "")
    if not mime_raw:
        # Tentar inferir pelo nome do arquivo
        filename_resp = midia.get("fileName", "") or midia.get("filename", "")
        if filename_resp.endswith(".mp3"):
            mime_raw = "audio/mpeg"
        elif filename_resp.endswith(".mp4"):
            mime_raw = "audio/mp4"
        elif filename_resp.endswith((".opus", ".ogg")):
            mime_raw = "audio/ogg"
        else:
            mime_raw = "audio/ogg"  # WhatsApp padrão
    mime_type = _normalizar_mime(mime_raw, "audio/ogg")

    # 5. Transcrever com Whisper (com validação de qualidade interna)
    texto_transcrito = await _whisper_transcrever(audio_bytes, mime_type, settings)

    if texto_transcrito:
        return f"[Mensagem de áudio] {texto_transcrito}"

    logger.warning(
        f"Whisper: sem resultado válido após todas as tentativas para {numero_paciente} "
        f"({len(audio_bytes)//1024}KB, mime={mime_type})"
    )
    # Marcador específico: áudio recebido mas transcrição falhou completamente
    return "[AUDIO_TRANSCRICAO_FALHOU]"


async def _processar_imagem_evolution(
    evolution: "EvolutionClient",
    instance_name: str,
    numero_paciente: str,
    payload: dict,
) -> str:
    """
    Baixa imagem via Evolution API e descreve com Claude Vision.
    Suporta mapas de cliente, fotos de materiais, capturas de tela.
    """
    settings = get_settings()

    try:
        await evolution.enviar_mensagem(
            instance=instance_name,
            numero=numero_paciente,
            texto="Processando sua imagem...",
        )
    except Exception:
        pass

    mensagem_data = payload.get("data", {})
    try:
        midia = await evolution.baixar_midia(instance_name, mensagem_data)
    except Exception as e:
        logger.error(f"Evolution baixar_midia (imagem) falhou: {e}")
        return "[IMAGEM_DOWNLOAD_FALHOU]"

    b64_data = midia.get("base64", "")
    if not b64_data:
        return "[IMAGEM_SEM_CONTEUDO]"

    image_bytes = _extrair_audio_bytes(b64_data)
    if not image_bytes:
        logger.error("Falha ao decodificar base64 da imagem Evolution")
        return "[IMAGEM_SEM_CONTEUDO]"

    if len(image_bytes) > 20 * 1024 * 1024:
        return "[MIDIA_MUITO_GRANDE]"

    # Determinar MIME type
    mime_raw = midia.get("mimeType", "") or midia.get("mimetype", "")
    if not mime_raw:
        fname = midia.get("fileName", "") or midia.get("filename", "")
        if fname.lower().endswith(".png"):
            mime_raw = "image/png"
        elif fname.lower().endswith((".webp",)):
            mime_raw = "image/webp"
        elif fname.lower().endswith(".gif"):
            mime_raw = "image/gif"
        else:
            mime_raw = "image/jpeg"
    mime_type = _normalizar_mime(mime_raw, "image/jpeg")
    if mime_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime_type = "image/jpeg"

    try:
        import anthropic as _ant
        client_claude = _ant.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        img_b64 = base64.b64encode(image_bytes).decode()
        resp = await client_claude.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime_type, "data": img_b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Descreva esta imagem de forma completa e objetiva em português. "
                            "Se houver texto, transcreva-o integralmente. "
                            "Se for um mapa mental, genograma, diagrama ou estrutura visual "
                            "(mapa do cliente), descreva todos os elementos, "
                            "conexões e relacionamentos presentes. "
                            "Responda apenas com a descrição, sem introduções."
                        ),
                    },
                ],
            }],
        )
        descricao = resp.content[0].text.strip() if resp.content else ""
        if descricao:
            logger.info(
                f"Claude Vision Evolution ({len(image_bytes)//1024}KB): '{descricao[:100]}'"
            )
            return f"[Imagem recebida] {descricao}"
        return "[IMAGEM_SEM_CONTEUDO]"
    except Exception as e:
        logger.error(f"Claude Vision falhou para imagem Evolution: {e}", exc_info=True)
        return "[IMAGEM_FALHOU]"


async def _processar_pdf_evolution(
    evolution: "EvolutionClient",
    instance_name: str,
    numero_paciente: str,
    payload: dict,
) -> str:
    """
    Baixa PDF via Evolution API e extrai texto com PyMuPDF.
    Suporta protocolos, guias, materiais de terapia.
    """
    try:
        await evolution.enviar_mensagem(
            instance=instance_name,
            numero=numero_paciente,
            texto="Processando seu PDF...",
        )
    except Exception:
        pass

    mensagem_data = payload.get("data", {})
    try:
        midia = await evolution.baixar_midia(instance_name, mensagem_data)
    except Exception as e:
        logger.error(f"Evolution baixar_midia (PDF) falhou: {e}")
        return "[PDF_DOWNLOAD_FALHOU]"

    b64_data = midia.get("base64", "")
    if not b64_data:
        return "[PDF_SEM_CONTEUDO]"

    pdf_bytes = _extrair_audio_bytes(b64_data)
    if not pdf_bytes:
        logger.error("Falha ao decodificar base64 do PDF Evolution")
        return "[PDF_SEM_CONTEUDO]"

    if len(pdf_bytes) > 50 * 1024 * 1024:
        return "[MIDIA_MUITO_GRANDE]"

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        partes = [page.get_text() for page in doc]
        doc.close()
        texto_pdf = "\n".join(partes).strip()
    except Exception as e:
        logger.warning(f"PyMuPDF falhou ao extrair PDF Evolution: {e}")
        return "[PDF_FALHOU]"

    if texto_pdf:
        texto_pdf = texto_pdf[:4000]
        logger.info(
            f"PyMuPDF Evolution: {len(texto_pdf)} chars "
            f"({len(pdf_bytes)//1024}KB)"
        )
        return f"[PDF recebido]\n{texto_pdf}"

    logger.warning("PDF Evolution sem texto extraível (possivelmente escaneado)")
    return "[PDF_SEM_TEXTO]"


async def _processar_mensagem(payload: dict) -> None:
    """
    Processa a mensagem recebida via Evolution API em background.

    Fluxo com máquina de estados:
      1. Extrair dados → 2. Deduplicar → 3. Resolver mídia →
      4. Buscar terapeuta → 5. Verificar estado (PENDENTE/ATIVO/BLOQUEADO) →
      6. Se ATIVO: checar profanidade → 7. RAG pipeline → 8. Responder
    """
    try:
        settings = get_settings()

        # 1. Extrair número e texto
        numero_paciente, texto_mensagem = extrair_numero_mensagem(payload)
        instance_name = payload.get("instance", "")

        logger.info(
            f"[PROC_DIAG] numero={numero_paciente}, instance={instance_name}, "
            f"texto='{texto_mensagem[:80]}'"
        )

        if not texto_mensagem or not texto_mensagem.strip():
            logger.info(f"[PROC_DIAG] Mensagem sem texto — ignorando (numero={numero_paciente})")
            return

        # 2. Deduplicação: Evolution API pode enviar webhooks duplicados
        message_id = payload.get("data", {}).get("key", {}).get("id", "")
        if message_id and await _ja_processado(message_id):
            logger.info(f"Evolution: mensagem duplicada ignorada (id={message_id})")
            return

        evolution = EvolutionClient()

        # 3. Resolver mídia — cada tipo tem seu pipeline de processamento
        # Marcadores de erro que geram aviso para o usuário e encerram o fluxo
        _s = NUMERO_SUPORTE  # atalho local para as f-strings abaixo
        _avisos_evolution = {
            "[AUDIO_DOWNLOAD_FALHOU]":    f"Pedimos desculpas! Não consegui baixar o áudio — o erro foi registrado para o administrador. Pode reenviar? Se o problema persistir, abra um chamado: *{_s}*",
            "[AUDIO_SEM_CONTEUDO]":       "Não consegui entender o áudio. Pode reenviar em voz mais alta ou escrever o que disse?",
            "[AUDIO_TRANSCRICAO_FALHOU]": "Recebi o áudio, mas não consegui transcrever com clareza. Pode falar mais devagar e em voz mais alta, ou escrever o que queria dizer?",
            "[IMAGEM_DOWNLOAD_FALHOU]":   f"Pedimos desculpas! Não consegui baixar a imagem — o erro foi registrado. Pode reenviar? Se persistir: *{_s}*",
            "[IMAGEM_SEM_CONTEUDO]":      "Não consegui processar a imagem. Pode tentar outra?",
            "[IMAGEM_FALHOU]":            f"Pedimos desculpas! Tive problema ao processar a imagem — erro registrado. Pode reenviar ou descrever como texto? Se persistir: *{_s}*",
            "[PDF_DOWNLOAD_FALHOU]":      f"Pedimos desculpas! Não consegui baixar o PDF — erro registrado. Pode reenviar? Se persistir: *{_s}*",
            "[PDF_SEM_CONTEUDO]":         f"Pedimos desculpas! Não consegui extrair o texto do PDF — erro registrado. Pode reenviar? Se persistir: *{_s}*",
            "[PDF_SEM_TEXTO]":            "O PDF parece ser uma imagem escaneada. Pode enviar uma versão com texto selecionável?",
            "[PDF_FALHOU]":               f"Pedimos desculpas! Tive problema ao processar o PDF — erro registrado. Pode reenviar? Se persistir: *{_s}*",
            "[MIDIA_MUITO_GRANDE]":       "O arquivo é muito grande para processar. Pode enviar uma versão menor ou escrever como texto?",
            "[VIDEO_EVOLUTION_PENDENTE]": "Recebi seu vídeo, mas por enquanto só consigo processar o áudio. Se quiser, pode enviar só o áudio.",
            "[DOCUMENTO_RECEBIDO]":       "Recebi seu documento, mas só consigo processar PDFs e imagens. Pode reenviar nesse formato?",
        }

        # Áudio e vídeo → Whisper
        if texto_mensagem in ("[AUDIO_EVOLUTION_PENDENTE]", "[VIDEO_EVOLUTION_PENDENTE]"):
            msg_type = "audio" if texto_mensagem == "[AUDIO_EVOLUTION_PENDENTE]" else "video"
            texto_mensagem = await _transcrever_audio_evolution(
                evolution, instance_name, numero_paciente, payload, msg_type
            )

        # Imagem → Claude Vision (mapa do cliente, fotos de materiais)
        elif texto_mensagem == "[IMAGEM_EVOLUTION_PENDENTE]":
            texto_mensagem = await _processar_imagem_evolution(
                evolution, instance_name, numero_paciente, payload
            )

        # PDF → PyMuPDF (protocolos, guias, materiais)
        elif texto_mensagem == "[DOCUMENTO_PDF_EVOLUTION_PENDENTE]":
            texto_mensagem = await _processar_pdf_evolution(
                evolution, instance_name, numero_paciente, payload
            )

        if texto_mensagem in _avisos_evolution:
            logger.info(f"Evolution: marcador de mídia {texto_mensagem} para {numero_paciente}")
            try:
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente,
                    texto=_avisos_evolution[texto_mensagem],
                )
            except Exception as e:
                logger.warning(f"Falha ao enviar aviso de mídia: {e}")
            return

        if texto_mensagem.startswith("[") and texto_mensagem.endswith("]"):
            logger.info(f"Tipo não suportado: {texto_mensagem} — ignorando")
            return

        # 3. Buscar terapeuta
        terapeuta = _buscar_terapeuta_por_instancia(instance_name)
        if not terapeuta:
            logger.warning(f"Nenhum terapeuta para instância '{instance_name}'")
            return

        terapeuta_id = terapeuta["id"]
        nome_terapeuta = terapeuta.get("nome", "Terapeuta")
        contato_terapeuta = terapeuta.get("telefone", "")
        config_terapeuta = {
            "nome_terapeuta": nome_terapeuta,
            "especialidade": terapeuta.get("especialidade", "Terapia Holística"),
            "tom_voz": terapeuta.get("tom_de_voz", "profissional e acolhedor"),
            "contato": contato_terapeuta,
        }

        # 4. Máquina de estados — controle de acesso
        # obter_ou_criar_estado usa requests síncrono → rodar em thread para não bloquear event loop
        estado, is_new = await asyncio.to_thread(obter_ou_criar_estado, terapeuta_id, numero_paciente)

        # ── BLOQUEADO ──────────────────────────────────────────────────────────
        if estado.is_bloqueado:
            await evolution.enviar_mensagem(
                instance=instance_name, numero=numero_paciente,
                texto=gerar_msg_ja_bloqueado(settings.CONTATO_ADMIN, estado.motivo_bloqueio or ""),
            )
            return

        # ── PENDENTE_CODIGO ────────────────────────────────────────────────────
        if estado.is_pendente:
            if is_new:
                # Primeira mensagem ever: salvar ANTES de enviar (garante rastreabilidade)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id,
                    paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem,
                    resposta_agente=" | ".join(MSGS_ONBOARDING),
                    intencao="ONBOARDING",
                )
                await _enviar_sequencia_evolution(
                    MSGS_ONBOARDING, evolution, instance_name, numero_paciente,
                )
            else:
                # Já recebeu boas-vindas: tentar validar como código
                # Strip prefixos de mídia (caso o usuário mande o código por áudio)
                texto_codigo = _extrair_texto_para_codigo(texto_mensagem)
                # validar_codigo usa Supabase sync → to_thread para não bloquear event loop
                codigo_valido = await asyncio.to_thread(validar_codigo, terapeuta_id, numero_paciente, texto_codigo)
                if codigo_valido:
                    await asyncio.to_thread(liberar_acesso, terapeuta_id, numero_paciente, texto_codigo)
                    # Ativar assinatura: define data_expiracao com base nos meses comprados
                    await asyncio.to_thread(ativar_acesso_com_codigo, terapeuta_id, texto_codigo, numero_paciente)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=" | ".join(MSGS_ACESSO_LIBERADO),
                        intencao="CODIGO_VALIDO",
                    )
                    await _enviar_sequencia_evolution(
                        MSGS_ACESSO_LIBERADO, evolution, instance_name, numero_paciente,
                    )
                else:
                    # Contar tentativas ANTERIORES (já salvas) para escolher mensagem
                    tentativas = await asyncio.to_thread(
                        _contar_tentativas_codigo, terapeuta_id, numero_paciente
                    )
                    msg_invalido = MSG_CODIGO_INVALIDO_FINAL if tentativas >= 4 else MSG_CODIGO_INVALIDO
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=msg_invalido,
                        intencao="CODIGO_INVALIDO",
                    )
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente,
                        texto=msg_invalido,
                    )
            return

        # ── ATIVO ──────────────────────────────────────────────────────────────

        # 5a. Aguardando confirmação do nome sugerido
        if estado.aguardando_confirmacao_nome:
            texto_limpo = _extrair_texto_para_codigo(texto_mensagem).lower().strip()
            # Detectar sinais de correção antes de checar confirmação:
            # "meu nome é X", "na verdade", "ops" indicam que o usuário está corrigindo,
            # não confirmando — mesmo que a mensagem contenha palavras como "certo".
            _sinais_correcao = any(s in texto_limpo for s in ["meu nome é", "na verdade", "ops", "é o certo", "é certo", "errei"])
            # "certo" e "correto" foram removidos pois aparecem em correções ("X é o certo")
            confirmou = not _sinais_correcao and any(p in texto_limpo for p in ["sim", "pode", "yes", "ok", "isso", "é isso", "tá", "ta"])
            rejeitou = any(p in texto_limpo for p in ["não", "nao", "no", "errado", "errada", "outro", "outra"])
            nome_sugerido = estado.nome_sugerido or ""

            if confirmou:
                # Confirmar nome e iniciar onboarding de cadastro (sem boas-vindas genérica)
                nome = await asyncio.to_thread(confirmar_nome_sugerido, terapeuta_id, numero_paciente, nome_sugerido)
                await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                msg_cadastro = f"Perfeito {nome}, agora vamos criar o acesso da sua plataforma, onde você vai poder acompanhar seus pacientes, diagnósticos e todo o histórico do atendimento."
                await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_cadastro)
                await asyncio.sleep(1.5)
                msg_email = "Qual o e-mail para cadastrar na plataforma?"
                await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_email)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=msg_cadastro, intencao="NOME_CONFIRMADO",
                )
            elif rejeitou:
                # Usuário rejeitou — pedir de novo
                await asyncio.to_thread(rejeitar_nome_sugerido, terapeuta_id, numero_paciente)
                await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=MSG_PEDIR_NOME_NOVAMENTE)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=MSG_PEDIR_NOME_NOVAMENTE, intencao="NOME_REJEITADO",
                )
            else:
                # Usuário enviou um novo nome (correção).
                # Tentar regex primeiro ("meu nome é X") antes de chamar o LLM.
                import re as _re
                texto_nome = _extrair_texto_para_codigo(texto_mensagem)
                _match_nome = _re.search(
                    r"(?:meu nome é|me chamo|pode me chamar de)\s+([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+){0,2})",
                    texto_nome,
                    _re.IGNORECASE,
                )
                novo_nome = _match_nome.group(1).strip() if _match_nome else None
                if not novo_nome:
                    novo_nome = await _extrair_nome_com_llm(texto_nome, settings)
                if novo_nome:
                    await asyncio.to_thread(salvar_nome_sugerido, terapeuta_id, numero_paciente, novo_nome)
                    msg_confirmar = gerar_msg_confirmar_nome(novo_nome)
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_confirmar)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_confirmar, intencao="NOME_NOVO_SUGERIDO",
                    )
                else:
                    await asyncio.to_thread(rejeitar_nome_sugerido, terapeuta_id, numero_paciente)
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=MSG_NOME_NAO_IDENTIFICADO)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=MSG_NOME_NAO_IDENTIFICADO, intencao="NOME_NAO_IDENTIFICADO",
                    )
            return

        # 5a2. Onboarding de cadastro (email → senha → criar acesso portal)
        if estado.aguardando_onboarding:
            texto_limpo = _extrair_texto_para_codigo(texto_mensagem).strip()
            step = estado.onboarding_step

            if step == "email":
                # Validar formato de email
                import re as _re_email
                email_match = _re_email.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', texto_limpo)
                if email_match:
                    email = email_match.group(0).lower()
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_email", email=email)
                    msg = f"O e-mail *{email}* está correto?\n\nResponda *sim* ou *não*."
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg)
                else:
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto="Não identifiquei um e-mail válido. Por favor, digite seu e-mail completo (exemplo: nome@email.com)")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente=texto_mensagem, resposta_agente="[ONBOARDING_EMAIL]", intencao="ONBOARDING")
                return

            elif step == "confirmar_email":
                confirmou = any(p in texto_limpo.lower() for p in ["sim", "yes", "ok", "isso", "correto", "certo", "pode", "tá", "ta"])
                if confirmou:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "senha", email=estado.onboarding_email)
                    msg = "Agora escolha uma senha de acesso para a plataforma.\n\nMínimo 6 caracteres."
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg)
                else:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto="Sem problema! Digite o e-mail correto:")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente=texto_mensagem, resposta_agente="[ONBOARDING_CONFIRMA_EMAIL]", intencao="ONBOARDING")
                return

            elif step == "senha":
                senha = texto_limpo
                if len(senha) < 6:
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto="A senha precisa ter pelo menos 6 caracteres. Tente novamente:")
                else:
                    masked = senha[0] + "*" * (len(senha) - 2) + senha[-1] if len(senha) > 2 else "***"
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_senha", email=estado.onboarding_email, senha_temp=senha)
                    msg = f"Sua senha: *{masked}*\n\nEstá correta? Responda *sim* ou *não*."
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg)
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_SENHA]", intencao="ONBOARDING")
                return

            elif step == "confirmar_senha":
                confirmou = any(p in texto_limpo.lower() for p in ["sim", "yes", "ok", "isso", "correto", "certo", "pode", "tá", "ta"])
                if confirmou:
                    # CRIAR ACESSO NO PORTAL
                    email = estado.onboarding_email
                    senha = estado.onboarding_senha_temp
                    nome = estado.nome_usuario

                    if not email or not senha:
                        logger.error(f"[ONBOARDING] email ou senha None — estado corrompido para {numero_paciente}")
                        await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                        msg_retry = "Houve um problema. Vamos recomeçar — qual seu e-mail?"
                        await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_retry)
                        await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_ESTADO_CORROMPIDO]", intencao="ONBOARDING")
                        return

                    try:
                        t_id = await asyncio.to_thread(_criar_acesso_portal_sync, email, senha, nome, numero_paciente)
                        await asyncio.to_thread(limpar_onboarding, terapeuta_id, numero_paciente)

                        msg1 = f"Tudo pronto, {nome}! Seu acesso ao portal foi criado com sucesso."
                        await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg1)
                        await asyncio.sleep(1.5)

                        msg2 = (
                            f"Acesse sua plataforma:\n\n"
                            f"\U0001f517 https://portal-vercel-ten.vercel.app\n"
                            f"\U0001f4e7 Login: {email}\n"
                            f"\U0001f511 Senha: a que você acabou de criar\n\n"
                            f"Lá você acompanha pacientes, diagnósticos, mapas natais e todo o histórico."
                        )
                        await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg2)
                        await asyncio.sleep(1.5)

                        msg3 = "Acesse e explore a plataforma. Quando quiser, é só me chamar aqui pelo WhatsApp que vamos trabalhar juntos nos seus casos clínicos."
                        await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg3)

                        logger.info(f"[ONBOARDING] Acesso portal criado para {nome} ({email}) — terapeuta_id={t_id}")

                    except Exception as e:
                        logger.error(f"[ONBOARDING] Erro ao criar acesso: {e}", exc_info=True)
                        # Don't clear onboarding — let user retry
                        await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_senha", email=email, senha_temp=senha)
                        msg_erro = "Houve um problema ao criar seu acesso. Tente novamente — sua senha está correta? (sim/não)"
                        await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_erro)
                else:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "senha", email=estado.onboarding_email)
                    await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto="Sem problema! Digite a senha novamente:")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_CRIAR_ACESSO]", intencao="ONBOARDING")
                return

            else:
                logger.error(f"[ONBOARDING] Step desconhecido: {step} para {numero_paciente} — limpando")
                await asyncio.to_thread(limpar_onboarding, terapeuta_id, numero_paciente)

            return  # Sempre retorna se estava em onboarding — impede fall-through

        # 5b. Coletar nome se ainda não temos
        if estado.aguardando_nome:
            import re as _re_nome
            texto_nome = _extrair_texto_para_codigo(texto_mensagem)

            # Fallback 1: regex "meu nome é X", "me chamo X", "sou o X"
            _match_nome_re = _re_nome.search(
                r"(?:meu nome [eé]|me chamo|sou (?:o |a )?|pode me chamar de)\s*([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+){0,2})",
                texto_nome, _re_nome.IGNORECASE,
            )
            nome_extraido = _match_nome_re.group(1).strip() if _match_nome_re else None

            # Fallback 2: texto curto com apenas letras (1-3 palavras) = provavelmente um nome
            if not nome_extraido:
                palavras = [p for p in texto_nome.strip().split() if any(c.isalpha() for c in p)]
                if 1 <= len(palavras) <= 3 and all(p.replace("-","").replace("'","").isalpha() for p in palavras):
                    nome_extraido = " ".join(p.capitalize() for p in palavras)

            # Fallback 3: LLM extraction
            if not nome_extraido:
                nome_extraido = await _extrair_nome_com_llm(texto_nome, settings)

            if nome_extraido:
                # Salvar sugestão e pedir confirmação
                await asyncio.to_thread(salvar_nome_sugerido, terapeuta_id, numero_paciente, nome_extraido)
                msg_confirmar = gerar_msg_confirmar_nome(nome_extraido)
                await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=msg_confirmar)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=msg_confirmar, intencao="NOME_SUGERIDO",
                )
            else:
                # Não identificou nome — pedir explicitamente
                await evolution.enviar_mensagem(instance=instance_name, numero=numero_paciente, texto=MSG_NOME_NAO_IDENTIFICADO)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=MSG_NOME_NAO_IDENTIFICADO, intencao="NOME_NAO_IDENTIFICADO",
                )
            return

        # 5c. Moderação: detectar profanidade ANTES do RAG
        if detectar_profanidade(texto_mensagem):
            violacoes = await asyncio.to_thread(registrar_violacao, terapeuta_id, numero_paciente)
            aviso = MSG_AVISO_1 if violacoes == 1 else (
                MSG_AVISO_2 if violacoes == 2 else gerar_msg_bloqueio(settings.CONTATO_ADMIN)
            )
            await evolution.enviar_mensagem(
                instance=instance_name, numero=numero_paciente, texto=aviso,
            )
            await _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=aviso,
                intencao=f"VIOLACAO_{violacoes}",
            )
            return

        # 6. Carregar memória e histórico (sequencial — Supabase client não é thread-safe)
        # _buscar_historico_conversa usa Supabase sync → to_thread evita bloquear event loop
        memoria = await carregar_memoria_completa(terapeuta_id, numero_paciente)
        historico = await asyncio.to_thread(_buscar_historico_conversa, terapeuta_id, numero_paciente, 20)

        # Formatar memória para injeção no prompt
        memoria_fmt = formatar_memoria_para_prompt(memoria, estado.nome_usuario)

        # 7. Processar mensagem normalmente (detecção de mudança de assunto removida —
        #    Jaccard similarity é incompatível com conversas clínicas onde cada turno
        #    introduz novos termos sobre o mesmo caso, gerando sempre falso positivo)
        if estado.aguardando_confirmacao_topico:
            # Limpar estado legado caso tenha ficado preso
            await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
        texto_para_processar = texto_mensagem

        # 8. Rotear mensagem: Haiku para ambíguo, keywords para óbvio
        # Strip prefixo de mídia antes de rotear — evita "[Mensagem de áudio] Oi..."
        # confundir o classificador e rotear áudios clínicos como SAUDACAO
        texto_para_rotear = _extrair_texto_para_codigo(texto_para_processar)
        _is_audio = texto_para_processar.startswith("[Mensagem de áudio]") or texto_mensagem.startswith("[Mensagem de áudio]")
        modo = await rotear_mensagem(
            texto_para_rotear,
            historico[-6:] if historico else [],
            estado.nome_usuario,
            is_audio=_is_audio,
        )
        logger.info(f"Modo roteado (Evolution): {modo.value}")
        # classificar_intencao só é chamado nos modos que usam RAG (economiza API)
        intencao = None

        resposta_texto: str | list[str] = ""
        # Inicializa nota de imagem para system prompt (pode ser preenchida no modo CONSULTA)
        _nota_imagem_sp = ""

        # 9. Saudação quando ATIVO
        if modo == ModoOperacao.SAUDACAO:
            # Mensagem muito curta com histórico = sinal de confusão (ex: "uê", "hm", "?")
            # → não repetir pergunta sobre caso/conteúdo; resposta simples de continuidade
            if len(texto_para_processar.strip()) <= 5 and historico:
                resposta_texto = gerar_resposta_confusao(estado.nome_usuario)
            # Se nova sessão E tem histórico: retomar o que foi discutido
            elif memoria.get("is_nova_sessao") and memoria.get("resumos_sessoes"):
                msg_retomada = gerar_msg_retomada_sessao(
                    memoria["resumos_sessoes"], estado.nome_usuario
                )
                if msg_retomada:
                    resposta_texto = msg_retomada
                    # Processar fim de sessão em background (gera resumo da anterior)
                    asyncio.create_task(
                        processar_fim_sessao_em_background(
                            terapeuta_id, numero_paciente, historico
                        )
                    )
                else:
                    resposta_texto = gerar_saudacao_ativo(estado.nome_usuario, tem_historico_recente=bool(historico))
            else:
                resposta_texto = gerar_saudacao_ativo(estado.nome_usuario, tem_historico_recente=bool(historico))
                if memoria.get("is_nova_sessao") and historico:
                    # Primeira vez com histórico mas sem resumo ainda: gerar em background
                    asyncio.create_task(
                        processar_fim_sessao_em_background(
                            terapeuta_id, numero_paciente, historico
                        )
                    )

        elif modo == ModoOperacao.EMERGENCIA:
            resposta_texto = (
                "Percebo que você pode estar lidando com uma situação delicada. "
                "Sua segurança é prioridade absoluta.\n\n"
                "Se estiver em crise, ligue agora:\n"
                "CVV (Centro de Valorização da Vida): 188\n"
                "SAMU: 192\n"
                "Chat: https://www.cvv.org.br\n\n"
                f"Entre em contato também com {nome_terapeuta}"
            )
            if contato_terapeuta:
                resposta_texto += f": {contato_terapeuta}"

        elif modo == ModoOperacao.FORA_ESCOPO:
            resposta_texto = MENSAGEM_FORA_ESCOPO

        elif modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            # Classificar intenção apenas no branch RAG (economiza chamada Haiku)
            intencao = await classificar_intencao(texto_para_processar)

            top_k_busca = 10 if modo == ModoOperacao.CONSULTA else 5
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id, top_k=top_k_busca,
            )
            try:
                ctx_aprendizado = await carregar_contexto_terapeuta(terapeuta_id)
                ctx_formatado = formatar_contexto_personalizado(ctx_aprendizado)
            except Exception as e:
                logger.warning(f"Contexto de aprendizado indisponível: {e}")
                ctx_formatado = None

            # Montar texto dos chunks para injetar no prompt do especialista
            chunks_texto = "\n\n".join(
                c.get("conteudo", "") for c in contexto_chunks if c.get("conteudo")
            )

            # --- Injeção de Mapa Natal (Swiss Ephemeris via Kerykeion) ---
            # Verifica se a mensagem atual ou o histórico recente contém dados de nascimento.
            # Em modo CONSULTA, calcula o mapa natal e prepende ao contexto para eliminar
            # alucinações de Ascendente e posições planetárias.
            if modo == ModoOperacao.CONSULTA:
                texto_busca_nascimento = texto_para_processar
                # Também escaneia as últimas 10 mensagens do histórico
                if historico:
                    msgs_historico = " ".join(
                        m.get("content", "") or m.get("conteudo", "") or m.get("mensagem", "") or ""
                        for m in historico[-10:]
                    )
                    texto_busca_nascimento = f"{texto_para_processar}\n{msgs_historico}"

                dados_nasc = await extrair_dados_nascimento_llm(texto_busca_nascimento)

                # Interceptor: "refazer mapa" — busca dados do histórico e regera
                if _eh_pedido_refazer_mapa(texto_para_processar):
                    dados_hist = await extrair_dados_nascimento_llm(
                        " ".join(
                            (m.get("content", "") or m.get("conteudo", "") or m.get("mensagem", "") or "")
                            for m in (historico or [])
                        )
                    )
                    if dados_hist and not dados_hist.get("falta_ano") and not dados_hist.get("falta_cidade"):
                        # Tem dados no histórico — injeta como se fossem novos para o path normal processar
                        # Se extrair_dados_nascimento não encontrou o nome, usa o nome do estado (onboarding)
                        if not dados_hist.get("nome") or dados_hist.get("nome") == "Paciente":
                            nome_estado = getattr(estado, "nome_usuario", None) or estado.get("nome_usuario") if isinstance(estado, dict) else getattr(estado, "nome_usuario", None)
                            if nome_estado:
                                dados_hist["nome"] = nome_estado
                        dados_nasc = dados_hist
                        logger.info(f"[Evolution] Refazer mapa: dados recuperados do histórico para {numero_paciente}")
                    else:
                        await evolution.enviar_mensagem(
                            instance=instance_name, numero=numero_paciente,
                            texto="Para refazer o mapa, preciso dos dados de nascimento novamente. Me manda nome, data, hora e cidade.",
                        )
                        return

                # Interceptor pré-LLM: pedido de mapa sem nenhum dado → responder direto
                if not dados_nasc and _eh_pedido_mapa_sem_dados(texto_para_processar, historico):
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente, texto=_MSG_PEDE_DADOS_MAPA,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=_MSG_PEDE_DADOS_MAPA,
                        intencao="MAPA_NATAL_PEDE_DADOS",
                    )
                    logger.info(f"[Evolution] Interceptado pedido de mapa sem dados — solicitando dados — {numero_paciente}")
                    return

                if dados_nasc and dados_nasc.get("falta_cidade"):
                    # Dados de nascimento detectados mas sem cidade — pedir ao terapeuta
                    nome_nasc = dados_nasc.get("nome", "Paciente")
                    msg_pede_cidade = (
                        f"Captei os dados: {dados_nasc.get('data', '')} às {dados_nasc.get('hora', '')}.\n\n"
                        f"Só falta a *cidade de nascimento*{' de ' + nome_nasc if nome_nasc != 'Paciente' else ''}. "
                        f"Qual a cidade?"
                    )
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente, texto=msg_pede_cidade,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_pede_cidade,
                        intencao="MAPA_NATAL_PEDE_CIDADE",
                    )
                    logger.info(f"[Evolution] Pedindo cidade de nascimento para mapa natal — {numero_paciente}")
                    return

                if dados_nasc and dados_nasc.get("falta_ano"):
                    # Dados de nascimento detectados mas sem o ano — pedir ao terapeuta
                    nome_nasc = dados_nasc.get("nome", "Paciente")
                    data_parcial = dados_nasc.get("data_parcial", "")
                    msg_pede_ano = (
                        f"Captei os dados de nascimento: {data_parcial}, "
                        f"{dados_nasc.get('hora', '')} em {dados_nasc.get('cidade', '')}.\n\n"
                        f"Para calcular o mapa natal preciso também do *ano de nascimento*. "
                        f"Qual o ano de nascimento{' de ' + nome_nasc if nome_nasc != 'Paciente' else ''}?"
                    )
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente, texto=msg_pede_ano,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_pede_ano,
                        intencao="MAPA_NATAL_PEDE_ANO",
                    )
                    logger.info(f"[Evolution] Pedindo ano de nascimento para mapa natal — {numero_paciente}")
                    return

                # Cache de mapas: consulta o banco antes de recalcular com Kerykeion.
                # Se o mapa já existe para esse paciente+data+hora, injeta o JSON salvo.
                # "refazer mapa" força nova geração e atualiza o cache.
                _eh_refazer = _eh_pedido_refazer_mapa(texto_para_processar)
                _mapa_json_cache = None
                # Inicializa variável de nota de imagem para system prompt (usada mais abaixo)
                _nota_imagem_sp = ""
                if dados_nasc and not dados_nasc.get("falta_ano") and not dados_nasc.get("falta_cidade") and not _eh_refazer:
                    _mapa_json_cache = await asyncio.to_thread(
                        _buscar_mapa_salvo, terapeuta_id, numero_paciente,
                        dados_nasc["data"], dados_nasc["hora"],
                    )
                    if _mapa_json_cache:
                        logger.info(
                            f"[Evolution] Mapa em cache para {numero_paciente} "
                            f"({dados_nasc['data']} {dados_nasc['hora']}) — injetando sem recalcular"
                        )
                        mapa_prefixo = (
                            "MAPA NATAL CALCULADO AUTOMATICAMENTE (Swiss Ephemeris — dado preciso, nao alucinado):\n"
                            f"{_mapa_json_cache}\n\n"
                        )
                        chunks_texto = mapa_prefixo + chunks_texto

                if not _mapa_json_cache and dados_nasc and not dados_nasc.get("falta_ano") and not dados_nasc.get("falta_cidade"):
                    # Pré-mensagem: avisa que está gerando (melhora UX)
                    nome_nasc_pre = dados_nasc.get("nome", "")
                    msg_gerando = (
                        f"Calculando o mapa alquímico de {nome_nasc_pre} agora."
                        if nome_nasc_pre else "Calculando o mapa alquímico agora."
                    )
                    msg_gerando += " A imagem chega em instantes — já faço a leitura na sequência."
                    try:
                        await evolution.enviar_mensagem(
                            instance=instance_name, numero=numero_paciente, texto=msg_gerando,
                        )
                    except Exception:
                        pass  # pré-mensagem não é crítica
                    imagem_enviada = False  # inicializa ANTES do try para o except conseguir verificar
                    _nota_imagem_sp = ""   # será sobrescrito dentro do try se tudo correr bem
                    try:
                        mapa_resultado, mapa_png_joel, mapa_png_trad = await asyncio.wait_for(
                            asyncio.to_thread(
                                gerar_mapa_completo,
                                dados_nasc.get("nome", "Paciente"),
                                dados_nasc["data"],
                                dados_nasc["hora"],
                                dados_nasc["cidade"],
                            ),
                            timeout=90.0,
                        )
                        # Envia as duas imagens antes da resposta textual
                        _caption_base = (
                            f"{dados_nasc.get('nome', 'Paciente')}\n"
                            f"{dados_nasc['data']} {dados_nasc['hora']} | {dados_nasc['cidade']}"
                        )
                        for _img_bytes, _img_caption in [
                            (mapa_png_trad, f"Mapa Natal — {_caption_base}"),
                            (mapa_png_joel, f"Mapa Alquimico — {_caption_base}"),
                        ]:
                            if not _img_bytes:
                                continue
                            for tentativa_img in range(1, 3):
                                try:
                                    resp_img = await evolution.enviar_imagem(
                                        instance=instance_name,
                                        numero=numero_paciente,
                                        imagem_bytes=_img_bytes,
                                        caption=_img_caption,
                                    )
                                    imagem_enviada = True
                                    _MAPA_FALHAS[numero_paciente] = 0
                                    logger.info(f"Imagem enviada para {numero_paciente} — Evolution tentativa {tentativa_img} | resp={resp_img}")
                                    break
                                except Exception as img_send_err:
                                    logger.warning(
                                        f"Envio da imagem falhou tentativa {tentativa_img}/2 (Evolution): {img_send_err}",
                                        exc_info=True,
                                    )
                                    if tentativa_img < 2:
                                        await asyncio.sleep(2)
                        if not mapa_png_joel and not mapa_png_trad:
                            logger.warning(f"Ambas as imagens são None para {numero_paciente} — imagens não geradas (Evolution)")

                        # Se imagem não chegou, avisa o usuário com instrução de retry
                        if not imagem_enviada:
                            msg_fallback = (
                                MSG_ERRO_MAPA_IMAGEM
                            )
                            try:
                                await evolution.enviar_mensagem(
                                    instance=instance_name, numero=numero_paciente, texto=msg_fallback,
                                )
                            except Exception:
                                pass

                        # Nota vai para o system prompt (não para chunks — evita LLM reproduzir o texto)
                        _nota_imagem_sp = (
                            "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                            "A imagem do mapa alquimico ja foi enviada como arquivo separado. "
                            "NAO mencione a imagem, NAO diga que foi enviada, NAO diga que houve instabilidade. "
                            "Va direto para a leitura alquimica completa — comece pela primeira linha."
                            if imagem_enviada else
                            "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                            "A imagem do mapa NAO foi enviada desta vez por instabilidade tecnica. "
                            "O terapeuta JA foi avisado sobre o problema via mensagem anterior. "
                            "ENTREGUE A LEITURA ALQUIMICA COMPLETA AGORA — nao peca permissao, nao pergunte se deve continuar, nao mencione a imagem. "
                            "Se o terapeuta pedir para reenviar a imagem, diga que ele deve digitar 'refazer mapa'."
                        )
                        mapa_prefixo = (
                            f"MAPA NATAL CALCULADO AUTOMATICAMENTE (Swiss Ephemeris — dado preciso, nao alucinado):\n"
                            f"{mapa_resultado}\n\n"
                        )
                        chunks_texto = mapa_prefixo + chunks_texto
                        # Salvar mapa no banco para cache futuro (background — não bloqueia resposta)
                        # Inclui imagens para upload ao Supabase Storage
                        asyncio.create_task(asyncio.to_thread(
                            _salvar_mapa,
                            terapeuta_id, numero_paciente,
                            dados_nasc.get("nome", ""), dados_nasc["data"],
                            dados_nasc["hora"], dados_nasc["cidade"],
                            mapa_resultado,
                            mapa_png_joel, mapa_png_trad,
                        ))
                        logger.info(
                            f"Mapa natal calculado para '{dados_nasc.get('nome')}' "
                            f"({dados_nasc['data']} {dados_nasc['hora']} em {dados_nasc['cidade']}) — Evolution"
                        )
                    except Exception as mapa_err:
                        logger.warning(
                            f"Cálculo de mapa natal falhou (Evolution) — {mapa_err}",
                            exc_info=True,
                        )
                        if imagem_enviada:
                            # Imagem já enviada — exceção ocorreu depois. Continua para gerar o texto.
                            if not _nota_imagem_sp:
                                _nota_imagem_sp = (
                                    "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                                    "A imagem do mapa alquimico ja foi enviada como arquivo separado. "
                                    "NAO mencione a imagem, NAO diga que foi enviada, NAO diga que houve instabilidade. "
                                    "Va direto para a leitura alquimica completa — comece pela primeira linha."
                                )
                            # chunks_texto pode não ter o mapa_prefixo, mas o LLM ainda gera a leitura
                        else:
                            # Imagem nunca enviada — falha real no cálculo
                            _MAPA_FALHAS[numero_paciente] = _MAPA_FALHAS.get(numero_paciente, 0) + 1
                            # Evitar crescimento ilimitado do dict de falhas
                            if len(_MAPA_FALHAS) > 200:
                                keys_to_remove = list(_MAPA_FALHAS.keys())[:100]
                                for k in keys_to_remove:
                                    del _MAPA_FALHAS[k]
                            tentativas_falha = _MAPA_FALHAS.get(numero_paciente, 0)
                            if tentativas_falha >= _MAPA_MAX_TENTATIVAS:
                                _MAPA_FALHAS[numero_paciente] = 0
                                msg_suporte = (
                                    f"Pedimos desculpas pelo transtorno! Após {_MAPA_MAX_TENTATIVAS} tentativas, "
                                    f"o mapa natal ainda não conseguiu ser gerado. "
                                    f"O erro foi registrado automaticamente.\n\n"
                                    f"Por favor, abra um chamado de suporte: *{NUMERO_SUPORTE}*"
                                )
                                try:
                                    await evolution.enviar_mensagem(
                                        instance=instance_name, numero=numero_paciente, texto=msg_suporte,
                                    )
                                except Exception:
                                    pass
                            # tentativas 1 e 2 sem imagem: silencioso — não chamar LLM
                            return

            # Selecionar prompt do agente especialista com fallback para None (usa genérico)
            try:
                if modo == ModoOperacao.CONSULTA:
                    system_prompt_especialista = get_prompt_agente_caso_clinico(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                elif modo == ModoOperacao.PESQUISA:
                    system_prompt_especialista = get_prompt_agente_metodo(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                elif modo == ModoOperacao.CRIACAO_CONTEUDO:
                    system_prompt_especialista = get_prompt_agente_conteudo(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                else:
                    system_prompt_especialista = None
            except Exception as e:
                logger.warning(f"Falha ao montar prompt especialista (Evolution): {e}. Usando genérico.")
                system_prompt_especialista = None

            # Injetar nota da imagem no system prompt (não nos chunks — evita LLM reproduzir o texto)
            if _nota_imagem_sp:
                system_prompt_especialista = (system_prompt_especialista or "") + _nota_imagem_sp

            try:
                resposta_texto = await gerar_resposta(
                    pergunta=texto_para_processar,
                    terapeuta_id=terapeuta_id,
                    contexto_chunks=contexto_chunks,
                    config_terapeuta=config_terapeuta,
                    historico_mensagens=historico if historico else None,
                    contexto_personalizado=ctx_formatado,
                    memoria_usuario=memoria_fmt,
                    modo_override=modo,
                    system_prompt_override=system_prompt_especialista,
                )
            except Exception as e:
                logger.error(f"Falha ao gerar resposta Claude (Evolution): {e}", exc_info=True)
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente,
                    texto=MSG_ERRO_MENSAGEM,
                )
                return
        else:
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id,
            )
            try:
                resposta_texto = await gerar_resposta(
                    pergunta=texto_para_processar,
                    terapeuta_id=terapeuta_id,
                    contexto_chunks=contexto_chunks,
                    config_terapeuta=config_terapeuta,
                    memoria_usuario=memoria_fmt,
                )
            except Exception as e:
                logger.error(f"Falha ao gerar resposta Claude (Evolution, fallback): {e}", exc_info=True)
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente,
                    texto=MSG_ERRO_MENSAGEM,
                )
                return

        # 10. Enviar resposta (com rate limiting anti-ban)
        if resposta_texto:
            if isinstance(resposta_texto, list):
                resposta_texto = [humanizar_resposta(seg) for seg in resposta_texto]
                await _enviar_sequencia_evolution(
                    resposta_texto, evolution, instance_name, numero_paciente,
                )
            elif "---SECAO---" in resposta_texto:
                # Resposta dividida em seções: cada seção vira uma mensagem separada
                secoes = [humanizar_resposta(s.strip()) for s in resposta_texto.split("---SECAO---") if s.strip()]
                await _enviar_sequencia_evolution(secoes, evolution, instance_name, numero_paciente)
            else:
                resposta_texto = humanizar_resposta(resposta_texto)
                await aguardar_antes_de_enviar(numero_paciente, sequencial=False)
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente, texto=resposta_texto,
                )
            logger.info(f"Resposta enviada para {numero_paciente}")

        # 11. Salvar conversa com detecção de paciente vinculado
        resposta_salvar = " | ".join(resposta_texto) if isinstance(resposta_texto, list) else resposta_texto
        _intencao_str = (
            f"{modo.value}|{intencao.value if hasattr(intencao, 'value') else str(intencao)}"
            if intencao is not None
            else modo.value
        )

        # Detectar paciente vinculado em background (não bloqueia envio)
        paciente_vinculado_id = None
        if modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            try:
                paciente_vinculado_id = await _detectar_paciente_vinculado(
                    terapeuta_id, numero_paciente, texto_mensagem, resposta_salvar or "", modo.value,
                )
            except Exception as e:
                logger.warning(f"Detecção de paciente vinculado falhou (Evolution): {e}")

        await _salvar_conversa(
            terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
            mensagem_paciente=texto_mensagem, resposta_agente=resposta_salvar,
            intencao=_intencao_str,
            paciente_vinculado_id=paciente_vinculado_id,
        )

        # 12. Background: timestamp + perfil + aprendizado + guardião
        asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
        asyncio.create_task(
            atualizar_perfil_apos_interacao(
                terapeuta_id, numero_paciente, estado.nome_usuario, texto_mensagem, modo.value
            )
        )
        # Guardião: monitora resposta em background, nunca bloqueia o usuário
        if resposta_salvar:
            asyncio.create_task(
                verificar_resposta(terapeuta_id, numero_paciente, texto_para_processar, resposta_salvar)
            )
        if modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            try:
                asyncio.create_task(
                    analisar_conversa(
                        terapeuta_id=terapeuta_id, mensagem=texto_mensagem,
                        resposta=resposta_salvar, modo=modo.value,
                    )
                )
            except Exception as e:
                logger.warning(f"Falha no aprendizado contínuo: {e}")
        # Extracao automatica de diagnostico (background, somente CONSULTA com paciente vinculado)
        if modo == ModoOperacao.CONSULTA and paciente_vinculado_id and resposta_salvar:
            asyncio.create_task(
                processar_diagnostico_auto(
                    resposta=resposta_salvar,
                    terapeuta_id=terapeuta_id,
                    paciente_id=paciente_vinculado_id,
                )
            )

    except Exception as e:
        logger.error(f"Erro ao processar mensagem Evolution: {e}", exc_info=True)


# =============================================================================
# HELPER — Detecção pré-LLM de pedido de mapa astral sem dados de nascimento
# =============================================================================

def _eh_pedido_mapa_sem_dados(texto: str, historico: list | None = None) -> bool:
    """
    Retorna True SOMENTE se a mensagem é um pedido NOVO de mapa astral/natal
    sem nenhum dado de nascimento fornecido E sem contexto prévio no histórico.

    Não dispara para:
    - Perguntas sobre capacidade ("consegue gerar?", "não pode?")
    - Follow-ups quando mapa já foi discutido no histórico
    - Mensagens com dados de nascimento
    """
    texto_lower = texto.lower().strip()

    # 1. Tem pedido de mapa?
    tem_pedido_mapa = any(kw in texto_lower for kw in KEYWORDS_PEDIDO_MAPA)
    if not tem_pedido_mapa:
        return False

    # 2. É uma pergunta sobre capacidade, não um pedido real → não interceptar
    indicadores_pergunta = [
        "consegue", "pode ", "não consegue", "não pode", "é possível",
        "consegues", "você consegue", "voce consegue", "dá pra", "da pra",
    ]
    if any(ind in texto_lower for ind in indicadores_pergunta):
        return False

    # 3. Já tem dados de nascimento na mensagem → não interceptar
    indicadores_dados = [
        "/", "nasceu", "nascida", "nascido", "às ", "as ", "horas", "hora",
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    if any(ind in texto_lower for ind in indicadores_dados):
        return False

    # 4. Histórico já tem contexto de mapa astral → é follow-up, não interceptar
    if historico:
        ctx_historico = " ".join(
            (m.get("content", "") or m.get("conteudo", "") or m.get("mensagem", "") or "")
            for m in historico[-6:]
        ).lower()
        indicadores_contexto_mapa = [
            "mapa natal", "mapa astral", "posições planetárias", "ascendente",
            "sol em ", "lua em ", "mercúrio em ", "casas (sistema",
        ]
        if any(ind in ctx_historico for ind in indicadores_contexto_mapa):
            return False

    return True


_MSG_PEDE_DADOS_MAPA = (
    "Perfeito, consigo calcular o mapa natal agora mesmo.\n\n"
    "Só preciso de quatro dados:\n\n"
    "Nome completo, data de nascimento (dia, mês e ano), hora exata de nascimento e cidade onde nasceu.\n\n"
    "Me manda isso que calculo na hora."
)


def _eh_pedido_refazer_mapa(texto: str) -> bool:
    """Retorna True se o usuário está pedindo para reenviar/refazer o mapa."""
    texto_lower = texto.lower().strip()
    return any(kw in texto_lower for kw in KEYWORDS_REFAZER_MAPA)


def _buscar_mapa_salvo(terapeuta_id: str, paciente_numero: str, data: str, hora: str) -> str | None:
    """
    Busca mapa_json salvo no banco para evitar recalcular com Kerykeion.
    Primeiro tenta buscar por (terapeuta_id, numero_telefone, tipo_mapa).
    Fallback para chave antiga (data+hora) para registros legados sem tipo_mapa.
    Retorna o mapa_json (texto) ou None se não existe.
    """
    try:
        sb = get_supabase()
        # Busca por tipo_mapa (regra nova — max 1 de cada tipo por paciente)
        res = (
            sb.table("mapas_astrais")
            .select("mapa_json, nome, tipo_mapa")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", paciente_numero)
            .eq("tipo_mapa", "Mapa Natal")
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["mapa_json"]
        # Fallback para registros legados sem tipo_mapa
        res = (
            sb.table("mapas_astrais")
            .select("mapa_json, nome")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", paciente_numero)
            .eq("data_nascimento", data)
            .eq("hora_nascimento", hora)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["mapa_json"]
    except Exception as e:
        logger.warning(f"Erro ao buscar mapa salvo: {e}")
    return None


def _paciente_ja_tem_mapas(terapeuta_id: str, paciente_numero: str) -> dict[str, bool]:
    """
    Verifica quais tipos de mapa o paciente já tem.
    Regra de negócio: máximo 2 mapas por paciente (1 Alquimico + 1 Natal).
    Retorna dict com {"Mapa Natal": bool, "Mapa Alquimico": bool}.
    """
    resultado = {"Mapa Natal": False, "Mapa Alquimico": False}
    try:
        sb = get_supabase()
        res = (
            sb.table("mapas_astrais")
            .select("tipo_mapa")
            .eq("terapeuta_id", terapeuta_id)
            .eq("numero_telefone", paciente_numero)
            .in_("tipo_mapa", ["Mapa Natal", "Mapa Alquimico"])
            .execute()
        )
        for row in (res.data or []):
            tipo = row.get("tipo_mapa")
            if tipo in resultado:
                resultado[tipo] = True
    except Exception as e:
        logger.warning(f"Erro ao verificar mapas existentes: {e}")
    return resultado


def _salvar_mapa(
    terapeuta_id: str,
    paciente_numero: str,
    nome: str,
    data: str,
    hora: str,
    cidade: str,
    mapa_json: str,
    imagem_joel_bytes: bytes | None = None,
    imagem_trad_bytes: bytes | None = None,
) -> None:
    """
    Salva ou atualiza mapas no banco.
    Regra de negócio: cada paciente pode ter no máximo 2 mapas (1 Alquímico + 1 Natal).
    Usa upsert por (terapeuta_id, numero_telefone, tipo_mapa) — se já existe mapa do
    mesmo tipo para o paciente, atualiza (imagem_url e mapa_json) em vez de criar duplicata.
    Nunca gera mais de 1 vez o mesmo tipo para o mesmo paciente.
    """
    try:
        sb = get_supabase()
        settings = get_settings()
        agora = datetime.now(timezone.utc).isoformat()

        # Registro base compartilhado entre os dois tipos
        registro_base = {
            "terapeuta_id": terapeuta_id,
            "numero_telefone": paciente_numero,
            "nome": nome or "Paciente",
            "data_nascimento": data,
            "hora_nascimento": hora,
            "cidade_nascimento": cidade,
            "mapa_json": mapa_json,
            "atualizado_em": agora,
        }

        # Lista de mapas a salvar: (tipo_mapa, imagem_bytes)
        mapas_para_salvar = []
        if imagem_joel_bytes:
            mapas_para_salvar.append(("Mapa Alquimico", imagem_joel_bytes))
        if imagem_trad_bytes:
            mapas_para_salvar.append(("Mapa Natal", imagem_trad_bytes))

        # Se nenhuma imagem, salva apenas o Mapa Natal (compatibilidade)
        if not mapas_para_salvar:
            mapas_para_salvar.append(("Mapa Natal", None))

        for tipo_mapa, imagem_bytes in mapas_para_salvar:
            registro = {**registro_base, "tipo_mapa": tipo_mapa}

            # Upload da imagem para Supabase Storage (bucket "mapas")
            if imagem_bytes:
                try:
                    mapa_id = str(uuid4())
                    storage_path = f"{terapeuta_id}/{mapa_id}.png"
                    sb.storage.from_("mapas").upload(
                        storage_path,
                        imagem_bytes,
                        {"content-type": "image/png"},
                    )
                    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/mapas/{storage_path}"
                    registro["imagem_url"] = public_url
                    logger.info(f"Imagem do {tipo_mapa} enviada para Storage: {storage_path}")
                except Exception as storage_err:
                    logger.warning(f"Erro ao enviar imagem do {tipo_mapa} para Storage: {storage_err}")

            # Upsert por (terapeuta_id, numero_telefone, tipo_mapa)
            # Se já existe mapa desse tipo para esse paciente, atualiza em vez de criar novo
            try:
                sb.table("mapas_astrais").upsert(
                    registro,
                    on_conflict="terapeuta_id,numero_telefone,tipo_mapa",
                ).execute()
                logger.info(f"{tipo_mapa} salvo/atualizado no banco para {paciente_numero}")
            except Exception as upsert_err:
                # Fallback: tenta com chave antiga para compatibilidade com registros legados
                logger.warning(f"Upsert por tipo_mapa falhou ({upsert_err}), tentando chave legada")
                try:
                    sb.table("mapas_astrais").upsert(
                        registro,
                        on_conflict="terapeuta_id,numero_telefone,data_nascimento,hora_nascimento",
                    ).execute()
                    logger.info(f"{tipo_mapa} salvo (chave legada) para {paciente_numero}")
                except Exception as fallback_err:
                    logger.warning(f"Fallback também falhou para {tipo_mapa}: {fallback_err}")

    except Exception as e:
        logger.warning(f"Erro ao salvar mapa no banco: {e}")


# =============================================
# ROTAS
# =============================================

@router.post("/whatsapp", summary="Recebe webhook da Evolution API")
async def receber_webhook_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Endpoint que recebe os webhooks da Evolution API quando uma mensagem
    chega no WhatsApp. Processa em background para responder rápido (200 OK).

    A Evolution API envia vários tipos de evento; nós processamos apenas
    'messages.upsert' (mensagens recebidas).
    """
    try:
        # Ler o payload raw (Evolution API envia JSON)
        body = await request.json()
    except Exception:
        logger.warning("Webhook recebeu payload inválido (não é JSON)")
        raise HTTPException(status_code=400, detail="Payload inválido — esperado JSON")

    # LOG DIAGNÓSTICO — captura tipo de mensagem para debug de áudio
    evento = body.get("event", "desconhecido")
    _data_diag = body.get("data", {})
    _msg_diag = _data_diag.get("message", {})
    _from_me_diag = _data_diag.get("key", {}).get("fromMe", "?")
    _msg_keys_diag = list(_msg_diag.keys()) if isinstance(_msg_diag, dict) else repr(_msg_diag)
    logger.info(
        f"[WEBHOOK_DIAG] evento={evento}, fromMe={_from_me_diag}, "
        f"message_keys={_msg_keys_diag}"
    )

    # Validar se é uma mensagem que deve ser processada
    if not eh_mensagem_valida(body):
        logger.info(f"[WEBHOOK_DIAG] Evento ignorado/inválido: {evento}")
        return {"status": "ignorado", "evento": evento}

    # Processar a mensagem em background (não travar o webhook)
    background_tasks.add_task(_processar_mensagem, body)

    instance_name = body.get("instance", "desconhecida")
    remote_jid = body.get("data", {}).get("key", {}).get("remoteJid", "")

    logger.info(
        f"Webhook recebido — instância={instance_name}, "
        f"remetente={remote_jid}"
    )

    # Responder 200 OK imediatamente para a Evolution API
    return {"status": "recebido", "instancia": instance_name}


# =============================================
# META WHATSAPP CLOUD API — FUNÇÕES AUXILIARES
# =============================================

def _buscar_terapeuta_por_phone_number_id(phone_number_id: str) -> dict | None:
    """
    Busca o terapeuta associado ao phone_number_id da Meta Cloud API.
    No MVP single-tenant retorna sempre o primeiro terapeuta ativo.
    """
    supabase = get_supabase()

    # MVP: usa o primeiro terapeuta ativo (single-tenant)
    resultado = (
        supabase.table("terapeutas")
        .select("*")
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if resultado.data and len(resultado.data) > 0:
        logger.info(
            f"Terapeuta ativo encontrado: {resultado.data[0].get('nome', 'N/A')} "
            f"(phone_number_id={phone_number_id})"
        )
        return resultado.data[0]

    return None


def _extrair_mensagem_meta(payload: dict) -> tuple[str, str, str, str, str, str]:
    """
    Extrai dados da mensagem do payload da Meta WhatsApp Cloud API.

    Returns:
        Tupla (phone_number_id, numero_remetente, texto_mensagem, message_id, msg_type, media_id)
    """
    try:
        entry = payload.get("entry", [])
        if not entry:
            return "", "", "", "", "", ""

        changes = entry[0].get("changes", [])
        if not changes:
            return "", "", "", "", "", ""

        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id", "")

        messages = value.get("messages", [])
        if not messages:
            return phone_number_id, "", "", "", "", ""

        msg = messages[0]
        numero_remetente = msg.get("from", "")
        message_id = msg.get("id", "")
        msg_type = msg.get("type", "")
        media_id = ""

        # Extrair texto de acordo com o tipo de mensagem
        texto = ""
        if msg_type == "text":
            texto = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            media_id = msg.get("image", {}).get("id", "")
            texto = msg.get("image", {}).get("caption", "")
            if not texto:
                texto = "[IMAGEM_PENDENTE]"
        elif msg_type == "audio":
            media_id = msg.get("audio", {}).get("id", "")
            texto = "[AUDIO_PENDENTE]"
        elif msg_type == "video":
            media_id = msg.get("video", {}).get("id", "")
            texto = "[VIDEO_PENDENTE]"
        elif msg_type == "document":
            media_id = msg.get("document", {}).get("id", "")
            filename = msg.get("document", {}).get("filename", "")
            mime_type = msg.get("document", {}).get("mime_type", "")
            caption = msg.get("document", {}).get("caption", "")
            if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
                texto = "[DOCUMENTO_PDF_PENDENTE]"
            else:
                texto = caption if caption else "[DOCUMENTO_RECEBIDO]"
                media_id = ""  # não baixar documentos não-PDF
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                texto = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                texto = interactive.get("list_reply", {}).get("title", "")
        else:
            texto = f"[TIPO_NAO_SUPORTADO:{msg_type}]"

        logger.info(
            "Mensagem Meta recebida de %s: '%s' (tipo=%s, id=%s, media_id=%s)",
            numero_remetente,
            texto[:50] + "..." if len(texto) > 50 else texto,
            msg_type,
            message_id,
            media_id[:20] if media_id else "",
        )

        return phone_number_id, numero_remetente, texto, message_id, msg_type, media_id

    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        logger.error("Erro ao extrair dados do payload Meta: %s", exc)
        return "", "", "", "", "", ""


# =============================================
# META CLOUD API — RESOLUÇÃO DE MÍDIA
# =============================================

async def _resolver_media_meta(
    msg_type: str,
    media_id: str,
    texto_atual: str,
    meta_client: "MetaCloudClient | None" = None,
    numero_paciente: str = "",
) -> str:
    """
    Baixa mídia da Meta Graph API e converte para texto:
    - audio/video  → transcrição via OpenAI Whisper (com retry automático)
    - image        → descrição via Claude vision
    - document PDF → extração de texto via PyMuPDF

    Parâmetros extras:
        meta_client: se fornecido, envia feedback "Transcrevendo..." durante o processamento
        numero_paciente: número para enviar o feedback

    Retorna o texto extraído ou um marcador de erro.
    """
    import httpx

    settings = get_settings()
    token = settings.META_WHATSAPP_TOKEN
    if not token or not media_id:
        return texto_atual

    try:
        # 1. Obter URL de download + baixar mídia (com retry + exponential backoff)
        # Meta URLs expiram rapidamente — backoff resolve race conditions e sobrecargas.
        # Backoff: 1s antes da tentativa 2, 2s antes da tentativa 3 (se adicionada).
        media_bytes = b""
        content_type = ""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            # Tentar obter URL de download (até 2 tentativas com backoff)
            media_url = ""
            for tentativa_url in range(2):
                if tentativa_url > 0:
                    backoff = tentativa_url  # 1s, 2s, ...
                    logger.info(f"Meta URL retry {tentativa_url}: aguardando {backoff}s (media_id={media_id})")
                    await asyncio.sleep(backoff)
                try:
                    r = await client.get(
                        f"https://graph.facebook.com/v22.0/{media_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except httpx.TimeoutException:
                    logger.warning(f"Timeout URL mídia Meta tentativa {tentativa_url+1} (media_id={media_id})")
                    if tentativa_url == 1:
                        return "[MIDIA_FALHOU]"
                    continue
                if r.status_code == 401:
                    logger.error(f"Token Meta expirado (media_id={media_id}). Verifique META_WHATSAPP_TOKEN.")
                    return "[MIDIA_TOKEN_INVALIDO]"
                r.raise_for_status()
                media_url = r.json().get("url", "")
                if media_url:
                    break
                logger.warning(f"URL de mídia vazia tentativa {tentativa_url+1} (media_id={media_id})")

            if not media_url:
                logger.warning(f"URL de mídia não encontrada após retries para media_id={media_id}")
                return texto_atual

            # 2. Baixar o arquivo de mídia (até 2 tentativas com backoff)
            for tentativa_dl in range(2):
                if tentativa_dl > 0:
                    backoff = tentativa_dl * 2  # 2s, 4s, ...
                    logger.info(f"Meta download retry {tentativa_dl}: aguardando {backoff}s (media_id={media_id})")
                    await asyncio.sleep(backoff)
                try:
                    r2 = await client.get(
                        media_url,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except httpx.TimeoutException:
                    logger.warning(f"Timeout download mídia Meta tentativa {tentativa_dl+1} (media_id={media_id})")
                    if tentativa_dl == 1:
                        return "[MIDIA_FALHOU]"
                    continue
                if r2.status_code == 401:
                    logger.error(f"Token Meta expirado ao baixar mídia (media_id={media_id})")
                    return "[MIDIA_TOKEN_INVALIDO]"
                r2.raise_for_status()
                media_bytes = r2.content
                content_type = r2.headers.get("content-type", "")
                logger.info(
                    f"Meta mídia baixada: content-type='{content_type}', "
                    f"tamanho={len(media_bytes)//1024}KB, media_id={media_id}"
                )
                break

        # 3. Validar content-type — se Meta retornar HTML (URL expirada), abortar
        base_ct_meta = _normalizar_mime(content_type, "")
        if base_ct_meta.startswith("text/") or base_ct_meta == "application/xml":
            logger.error(
                f"Meta retornou content-type inesperado '{content_type}' "
                f"para {media_id} — URL pode ter expirado"
            )
            return "[MIDIA_FALHOU]"

        # 4. Verificar tamanho mínimo (< 1KB → provavelmente não é mídia real)
        if msg_type in ("audio", "video") and len(media_bytes) < 1024:
            logger.warning(
                f"Mídia muito pequena: {len(media_bytes)} bytes "
                f"(< 1KB) para {media_id} — descartando"
            )
            return "[AUDIO_SEM_CONTEUDO]"

        # 4b. Verificar tamanho máximo
        if len(media_bytes) > _MAX_AUDIO_BYTES:
            logger.warning(
                f"Mídia muito grande: {len(media_bytes)/1024/1024:.1f}MB "
                f"(limite {_MAX_AUDIO_BYTES//1024//1024}MB) para {media_id}"
            )
            return "[MIDIA_MUITO_GRANDE]"

        if msg_type in ("audio", "video"):
            # Transcrever com Whisper (com validação de qualidade interna)
            mime_type_meta = base_ct_meta if base_ct_meta else "audio/ogg"
            texto_transcrito = await _whisper_transcrever(media_bytes, mime_type_meta, settings)

            if texto_transcrito:
                logger.info(
                    f"Meta Whisper OK: {msg_type} "
                    f"({len(media_bytes)//1024}KB): '{texto_transcrito[:100]}'"
                )
                return f"[Mensagem de áudio] {texto_transcrito}"

            logger.warning(
                f"Meta Whisper: sem resultado válido para {msg_type}/{media_id} "
                f"({len(media_bytes)//1024}KB, content-type={content_type})"
            )
            return "[AUDIO_TRANSCRICAO_FALHOU]"

        elif msg_type == "image":
            # Descrição via Claude vision
            import anthropic
            client_claude = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            img_b64 = base64.b64encode(media_bytes).decode()
            media_type_claude = content_type.split(";")[0].strip() or "image/jpeg"
            if media_type_claude not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                media_type_claude = "image/jpeg"
            resp = await client_claude.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type_claude,
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Descreva esta imagem de forma concisa e objetiva em português. "
                                "Se houver texto na imagem, transcreva-o integralmente. "
                                "Responda apenas com a descrição/transcrição, sem introduções ou comentários."
                            ),
                        },
                    ],
                }],
            )
            descricao = resp.content[0].text.strip() if resp.content else ""
            if descricao:
                logger.info(f"Claude descreveu imagem ({len(media_bytes)//1024}KB): '{descricao[:80]}'")
                return f"[Imagem recebida] {descricao}"
            return texto_atual

        elif msg_type == "document":
            # Extração de texto via PyMuPDF
            import fitz  # PyMuPDF
            try:
                doc = fitz.open(stream=media_bytes, filetype="pdf")
                partes = []
                for page in doc:
                    partes.append(page.get_text())
                doc.close()
                texto_pdf = "\n".join(partes).strip()
            except Exception as e_pdf:
                logger.warning(f"PyMuPDF falhou ao extrair texto: {e_pdf}")
                return "[MIDIA_FALHOU]"

            if texto_pdf:
                # Limitar a 4000 chars para não explodir o prompt
                texto_pdf = texto_pdf[:4000]
                logger.info(f"PyMuPDF extraiu {len(texto_pdf)} chars do PDF ({len(media_bytes)//1024}KB)")
                return f"[PDF recebido]\n{texto_pdf}"
            # PDF sem texto selecionável (pode ser escaneado)
            logger.warning(f"PDF sem texto extraível para media_id={media_id}")
            return "[PDF_SEM_TEXTO]"

    except Exception as e:
        logger.error(f"Falha ao resolver mídia ({msg_type}, media_id={media_id}): {e}", exc_info=True)
        return "[MIDIA_FALHOU]"


# =============================================
# META CLOUD API — PROCESSAMENTO EM BACKGROUND
# =============================================

async def _enviar_sequencia_meta(
    msgs: list[str],
    meta_client: "MetaCloudClient",
    numero: str,
    delay: float = 4.0,
) -> None:
    """
    Envia uma lista de mensagens com rate limiting (Meta Cloud API).
    Delay padrão: 4s entre mensagens para o terapeuta conseguir ler cada bloco.
    """
    for i, msg in enumerate(msgs):
        await aguardar_antes_de_enviar(numero, sequencial=True)
        if i == 0 and len(msgs) > 1:
            await asyncio.sleep(1.5)  # pausa breve antes da 1ª mensagem de uma sequência
        elif i > 0:
            await asyncio.sleep(delay)
        await meta_client.send_text_message(phone_number=numero, message=msg)


async def _processar_mensagem_meta(payload: dict) -> None:
    """
    Processa a mensagem recebida via Meta WhatsApp Cloud API em background.

    Fluxo com máquina de estados:
      1. Extrair dados → 2. Validar tipo → 3. Buscar terapeuta →
      4. Verificar estado (PENDENTE/ATIVO/BLOQUEADO) →
      5. Se ATIVO: checar profanidade → 6. RAG pipeline → 7. Responder
    """
    try:
        settings = get_settings()

        # 1. Extrair dados
        phone_number_id, numero_paciente, texto_mensagem, message_id, msg_type, media_id = _extrair_mensagem_meta(payload)

        if not numero_paciente or not texto_mensagem:
            logger.info("Payload Meta sem mensagem processável — ignorando")
            return

        # 2. Deduplicação: descartar mensagens já processadas (Meta envia duplicatas)
        if await _ja_processado(message_id):
            logger.info(f"Mensagem duplicada ignorada: message_id={message_id}")
            return

        logger.info(f"Meta: mensagem de {numero_paciente} (phone_number_id={phone_number_id})")

        # 3. Inicializar cliente Meta e marcar como lida
        meta_client = MetaCloudClient()
        if message_id:
            try:
                await meta_client.mark_as_read(message_id)
            except Exception as e:
                logger.warning(f"Falha ao marcar como lida: {e}")

        # 4. Resolver mídia (áudio → Whisper, imagem → Claude vision, PDF → PyMuPDF)
        if media_id and texto_mensagem in ("[AUDIO_PENDENTE]", "[VIDEO_PENDENTE]", "[IMAGEM_PENDENTE]", "[DOCUMENTO_PDF_PENDENTE]"):
            texto_mensagem = await _resolver_media_meta(
                msg_type, media_id, texto_mensagem,
                meta_client=meta_client, numero_paciente=numero_paciente,
            )

        # 5. Validar tipo de mensagem
        if not texto_mensagem.strip():
            return

        # Tratar marcadores de erro de mídia com mensagens específicas
        _sm = NUMERO_SUPORTE
        _avisos_midia = {
            "[AUDIO_SEM_CONTEUDO]": (
                "Não consegui entender o áudio. "
                "Pode reenviar em voz mais alta ou escrever o que disse?"
            ),
            "[AUDIO_TRANSCRICAO_FALHOU]": (
                "Recebi o áudio, mas não consegui transcrever com clareza. "
                "Pode falar mais devagar e em voz mais alta, ou escrever o que queria dizer?"
            ),
            "[MIDIA_FALHOU]": (
                f"Pedimos desculpas! Tive problema ao processar o arquivo — erro registrado para o administrador. "
                f"Pode reenviar ou escrever como texto? Se persistir: *{_sm}*"
            ),
            "[MIDIA_TOKEN_INVALIDO]": (
                f"Pedimos desculpas! Estou com problema técnico para acessar mídias — erro registrado. "
                f"Por favor, escreva sua mensagem como texto. Se persistir: *{_sm}*"
            ),
            "[MIDIA_MUITO_GRANDE]": (
                "O arquivo é muito grande para processar. "
                "Pode enviar uma versão menor ou escrever como texto?"
            ),
            "[PDF_SEM_TEXTO]": (
                "O PDF parece ser uma imagem escaneada. "
                "Pode enviar uma versão com texto selecionável?"
            ),
        }
        if texto_mensagem in _avisos_midia:
            logger.info(f"Marcador de mídia: {texto_mensagem} para {numero_paciente}")
            try:
                await meta_client.send_text_message(
                    phone_number=numero_paciente,
                    message=_avisos_midia[texto_mensagem],
                )
            except Exception as e:
                logger.warning(f"Falha ao enviar aviso de mídia: {e}")
            return

        if texto_mensagem.startswith("[") and texto_mensagem.endswith("]"):
            logger.info(f"Tipo não suportado: {texto_mensagem} — ignorando")
            return

        # 6. Buscar terapeuta
        terapeuta = _buscar_terapeuta_por_phone_number_id(phone_number_id)
        if not terapeuta:
            logger.warning(f"Nenhum terapeuta para phone_number_id '{phone_number_id}'")
            return

        terapeuta_id = terapeuta["id"]
        nome_terapeuta = terapeuta.get("nome", "Terapeuta")
        contato_terapeuta = terapeuta.get("telefone", "")
        config_terapeuta = {
            "nome_terapeuta": nome_terapeuta,
            "especialidade": terapeuta.get("especialidade", "Terapia Holística"),
            "tom_voz": terapeuta.get("tom_de_voz", "profissional e acolhedor"),
            "contato": contato_terapeuta,
        }

        # 5. Máquina de estados — controle de acesso
        # obter_ou_criar_estado usa requests síncrono → rodar em thread para não bloquear event loop
        estado, is_new = await asyncio.to_thread(obter_ou_criar_estado, terapeuta_id, numero_paciente)

        # ── BLOQUEADO ──────────────────────────────────────────────────────────
        if estado.is_bloqueado:
            await meta_client.send_text_message(
                phone_number=numero_paciente,
                message=gerar_msg_ja_bloqueado(settings.CONTATO_ADMIN, estado.motivo_bloqueio or ""),
            )
            return

        # ── PENDENTE_CODIGO ────────────────────────────────────────────────────
        if estado.is_pendente:
            if is_new:
                # Primeira mensagem ever: salvar ANTES de enviar (garante rastreabilidade)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id,
                    paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem,
                    resposta_agente=" | ".join(MSGS_ONBOARDING),
                    intencao="ONBOARDING",
                )
                await _enviar_sequencia_meta(MSGS_ONBOARDING, meta_client, numero_paciente)
            else:
                # Já recebeu boas-vindas: tentar como código de liberação
                # Strip prefixos de mídia (caso o usuário mande o código por áudio)
                texto_codigo = _extrair_texto_para_codigo(texto_mensagem)
                # validar_codigo usa Supabase sync → to_thread para não bloquear event loop
                codigo_valido = await asyncio.to_thread(validar_codigo, terapeuta_id, numero_paciente, texto_codigo)
                if codigo_valido:
                    await asyncio.to_thread(liberar_acesso, terapeuta_id, numero_paciente, texto_codigo)
                    # Ativar assinatura: define data_expiracao com base nos meses comprados
                    await asyncio.to_thread(ativar_acesso_com_codigo, terapeuta_id, texto_codigo, numero_paciente)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=" | ".join(MSGS_ACESSO_LIBERADO),
                        intencao="CODIGO_VALIDO",
                    )
                    await _enviar_sequencia_meta(
                        MSGS_ACESSO_LIBERADO, meta_client, numero_paciente,
                    )
                else:
                    # Contar tentativas ANTERIORES (já salvas) para escolher mensagem
                    tentativas = await asyncio.to_thread(
                        _contar_tentativas_codigo, terapeuta_id, numero_paciente
                    )
                    msg_invalido = MSG_CODIGO_INVALIDO_FINAL if tentativas >= 4 else MSG_CODIGO_INVALIDO
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=msg_invalido,
                        intencao="CODIGO_INVALIDO",
                    )
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=msg_invalido,
                    )
            return

        # ── ATIVO ──────────────────────────────────────────────────────────────

        # 6a. Aguardando confirmação do nome sugerido
        if estado.aguardando_confirmacao_nome:
            texto_limpo = _extrair_texto_para_codigo(texto_mensagem).lower().strip()
            # Detectar sinais de correção antes de checar confirmação:
            # "meu nome é X", "na verdade", "ops" indicam que o usuário está corrigindo,
            # não confirmando — mesmo que a mensagem contenha palavras como "certo".
            _sinais_correcao = any(s in texto_limpo for s in ["meu nome é", "na verdade", "ops", "é o certo", "é certo", "errei"])
            # "certo" e "correto" foram removidos pois aparecem em correções ("X é o certo")
            confirmou = not _sinais_correcao and any(p in texto_limpo for p in ["sim", "pode", "yes", "ok", "isso", "é isso", "tá", "ta"])
            rejeitou = any(p in texto_limpo for p in ["não", "nao", "no", "errado", "errada", "outro", "outra"])
            nome_sugerido = estado.nome_sugerido or ""

            if confirmou:
                nome = await asyncio.to_thread(confirmar_nome_sugerido, terapeuta_id, numero_paciente, nome_sugerido)
                await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                msg_cadastro = f"Perfeito {nome}, agora vamos criar o acesso da sua plataforma, onde você vai poder acompanhar seus pacientes, diagnósticos e todo o histórico do atendimento."
                await meta_client.send_text_message(phone_number=numero_paciente, message=msg_cadastro)
                await asyncio.sleep(1.5)
                msg_email = "Qual o e-mail para cadastrar na plataforma?"
                await meta_client.send_text_message(phone_number=numero_paciente, message=msg_email)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=msg_cadastro, intencao="NOME_CONFIRMADO",
                )
            elif rejeitou:
                await asyncio.to_thread(rejeitar_nome_sugerido, terapeuta_id, numero_paciente)
                await meta_client.send_text_message(phone_number=numero_paciente, message=MSG_PEDIR_NOME_NOVAMENTE)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=MSG_PEDIR_NOME_NOVAMENTE, intencao="NOME_REJEITADO",
                )
            else:
                # Usuário enviou um novo nome (correção).
                # Tentar regex primeiro ("meu nome é X") antes de chamar o LLM.
                import re as _re
                texto_nome = _extrair_texto_para_codigo(texto_mensagem)
                _match_nome = _re.search(
                    r"(?:meu nome é|me chamo|pode me chamar de)\s+([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+){0,2})",
                    texto_nome,
                    _re.IGNORECASE,
                )
                novo_nome = _match_nome.group(1).strip() if _match_nome else None
                if not novo_nome:
                    novo_nome = await _extrair_nome_com_llm(texto_nome, settings)
                if novo_nome:
                    await asyncio.to_thread(salvar_nome_sugerido, terapeuta_id, numero_paciente, novo_nome)
                    msg_confirmar = gerar_msg_confirmar_nome(novo_nome)
                    await meta_client.send_text_message(phone_number=numero_paciente, message=msg_confirmar)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_confirmar, intencao="NOME_NOVO_SUGERIDO",
                    )
                else:
                    await asyncio.to_thread(rejeitar_nome_sugerido, terapeuta_id, numero_paciente)
                    await meta_client.send_text_message(phone_number=numero_paciente, message=MSG_NOME_NAO_IDENTIFICADO)
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=MSG_NOME_NAO_IDENTIFICADO, intencao="NOME_NAO_IDENTIFICADO",
                    )
            return

        # 6a2. Onboarding de cadastro (email → senha → criar acesso portal)
        if estado.aguardando_onboarding:
            texto_limpo = _extrair_texto_para_codigo(texto_mensagem).strip()
            step = estado.onboarding_step

            if step == "email":
                import re as _re_email
                email_match = _re_email.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', texto_limpo)
                if email_match:
                    email = email_match.group(0).lower()
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_email", email=email)
                    msg = f"O e-mail *{email}* está correto?\n\nResponda *sim* ou *não*."
                    await meta_client.send_text_message(phone_number=numero_paciente, message=msg)
                else:
                    await meta_client.send_text_message(phone_number=numero_paciente, message="Não identifiquei um e-mail válido. Por favor, digite seu e-mail completo (exemplo: nome@email.com)")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente=texto_mensagem, resposta_agente="[ONBOARDING_EMAIL]", intencao="ONBOARDING")
                return

            elif step == "confirmar_email":
                confirmou = any(p in texto_limpo.lower() for p in ["sim", "yes", "ok", "isso", "correto", "certo", "pode", "tá", "ta"])
                if confirmou:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "senha", email=estado.onboarding_email)
                    msg = "Agora escolha uma senha de acesso para a plataforma.\n\nMínimo 6 caracteres."
                    await meta_client.send_text_message(phone_number=numero_paciente, message=msg)
                else:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                    await meta_client.send_text_message(phone_number=numero_paciente, message="Sem problema! Digite o e-mail correto:")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente=texto_mensagem, resposta_agente="[ONBOARDING_CONFIRMA_EMAIL]", intencao="ONBOARDING")
                return

            elif step == "senha":
                senha = texto_limpo
                if len(senha) < 6:
                    await meta_client.send_text_message(phone_number=numero_paciente, message="A senha precisa ter pelo menos 6 caracteres. Tente novamente:")
                else:
                    masked = senha[0] + "*" * (len(senha) - 2) + senha[-1] if len(senha) > 2 else "***"
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_senha", email=estado.onboarding_email, senha_temp=senha)
                    msg = f"Sua senha: *{masked}*\n\nEstá correta? Responda *sim* ou *não*."
                    await meta_client.send_text_message(phone_number=numero_paciente, message=msg)
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_SENHA]", intencao="ONBOARDING")
                return

            elif step == "confirmar_senha":
                confirmou = any(p in texto_limpo.lower() for p in ["sim", "yes", "ok", "isso", "correto", "certo", "pode", "tá", "ta"])
                if confirmou:
                    email = estado.onboarding_email
                    senha = estado.onboarding_senha_temp
                    nome = estado.nome_usuario

                    if not email or not senha:
                        logger.error(f"[ONBOARDING] email ou senha None — estado corrompido para {numero_paciente}")
                        await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "email")
                        msg_retry = "Houve um problema. Vamos recomeçar — qual seu e-mail?"
                        await meta_client.send_text_message(phone_number=numero_paciente, message=msg_retry)
                        await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_ESTADO_CORROMPIDO]", intencao="ONBOARDING")
                        return

                    try:
                        t_id = await asyncio.to_thread(_criar_acesso_portal_sync, email, senha, nome, numero_paciente)
                        await asyncio.to_thread(limpar_onboarding, terapeuta_id, numero_paciente)

                        msg1 = f"Tudo pronto, {nome}! Seu acesso ao portal foi criado com sucesso."
                        await meta_client.send_text_message(phone_number=numero_paciente, message=msg1)
                        await asyncio.sleep(1.5)

                        msg2 = (
                            f"Acesse sua plataforma:\n\n"
                            f"\U0001f517 https://portal-vercel-ten.vercel.app\n"
                            f"\U0001f4e7 Login: {email}\n"
                            f"\U0001f511 Senha: a que você acabou de criar\n\n"
                            f"Lá você acompanha pacientes, diagnósticos, mapas natais e todo o histórico."
                        )
                        await meta_client.send_text_message(phone_number=numero_paciente, message=msg2)
                        await asyncio.sleep(1.5)

                        msg3 = "Acesse e explore a plataforma. Quando quiser, é só me chamar aqui pelo WhatsApp que vamos trabalhar juntos nos seus casos clínicos."
                        await meta_client.send_text_message(phone_number=numero_paciente, message=msg3)

                        logger.info(f"[ONBOARDING] Acesso portal criado para {nome} ({email}) — terapeuta_id={t_id}")

                    except Exception as e:
                        logger.error(f"[ONBOARDING] Erro ao criar acesso: {e}", exc_info=True)
                        # Don't clear onboarding — let user retry
                        await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "confirmar_senha", email=email, senha_temp=senha)
                        msg_erro = "Houve um problema ao criar seu acesso. Tente novamente — sua senha está correta? (sim/não)"
                        await meta_client.send_text_message(phone_number=numero_paciente, message=msg_erro)
                else:
                    await asyncio.to_thread(atualizar_onboarding, terapeuta_id, numero_paciente, "senha", email=estado.onboarding_email)
                    await meta_client.send_text_message(phone_number=numero_paciente, message="Sem problema! Digite a senha novamente:")
                await _salvar_conversa(terapeuta_id=terapeuta_id, paciente_numero=numero_paciente, mensagem_paciente="[SENHA_OCULTADA]", resposta_agente="[ONBOARDING_CRIAR_ACESSO]", intencao="ONBOARDING")
                return

            else:
                logger.error(f"[ONBOARDING] Step desconhecido: {step} para {numero_paciente} — limpando")
                await asyncio.to_thread(limpar_onboarding, terapeuta_id, numero_paciente)

            return  # Sempre retorna se estava em onboarding — impede fall-through

        # 6b. Coletar nome se ainda não temos
        if estado.aguardando_nome:
            import re as _re_nome
            texto_nome = _extrair_texto_para_codigo(texto_mensagem)

            # Fallback 1: regex "meu nome é X", "me chamo X", "sou o X"
            _match_nome_re = _re_nome.search(
                r"(?:meu nome [eé]|me chamo|sou (?:o |a )?|pode me chamar de)\s*([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+){0,2})",
                texto_nome, _re_nome.IGNORECASE,
            )
            nome_extraido = _match_nome_re.group(1).strip() if _match_nome_re else None

            # Fallback 2: texto curto com apenas letras (1-3 palavras) = provavelmente um nome
            if not nome_extraido:
                palavras = [p for p in texto_nome.strip().split() if any(c.isalpha() for c in p)]
                if 1 <= len(palavras) <= 3 and all(p.replace("-","").replace("'","").isalpha() for p in palavras):
                    nome_extraido = " ".join(p.capitalize() for p in palavras)

            # Fallback 3: LLM extraction
            if not nome_extraido:
                nome_extraido = await _extrair_nome_com_llm(texto_nome, settings)
            if nome_extraido:
                await asyncio.to_thread(salvar_nome_sugerido, terapeuta_id, numero_paciente, nome_extraido)
                msg_confirmar = gerar_msg_confirmar_nome(nome_extraido)
                await meta_client.send_text_message(phone_number=numero_paciente, message=msg_confirmar)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=msg_confirmar, intencao="NOME_SUGERIDO",
                )
            else:
                await meta_client.send_text_message(phone_number=numero_paciente, message=MSG_NOME_NAO_IDENTIFICADO)
                await _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=MSG_NOME_NAO_IDENTIFICADO, intencao="NOME_NAO_IDENTIFICADO",
                )
            return

        # 6c. Moderação: detectar profanidade ANTES do RAG
        if detectar_profanidade(texto_mensagem):
            violacoes = await asyncio.to_thread(registrar_violacao, terapeuta_id, numero_paciente)
            aviso = MSG_AVISO_1 if violacoes == 1 else (
                MSG_AVISO_2 if violacoes == 2 else gerar_msg_bloqueio(settings.CONTATO_ADMIN)
            )
            await meta_client.send_text_message(
                phone_number=numero_paciente, message=aviso,
            )
            await _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=aviso,
                intencao=f"VIOLACAO_{violacoes}",
            )
            return

        # 7. Carregar memória e histórico (sequencial — Supabase client não é thread-safe)
        # _buscar_historico_conversa usa Supabase sync → to_thread evita bloquear event loop
        memoria = await carregar_memoria_completa(terapeuta_id, numero_paciente)
        historico = await asyncio.to_thread(_buscar_historico_conversa, terapeuta_id, numero_paciente, 20)

        # Formatar memória para injeção no prompt
        memoria_fmt = formatar_memoria_para_prompt(memoria, estado.nome_usuario)

        # 8. Processar mensagem normalmente (detecção de mudança de assunto removida)
        if estado.aguardando_confirmacao_topico:
            # Limpar estado legado caso tenha ficado preso
            await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
        texto_para_processar = texto_mensagem

        # 9. Rotear mensagem: Haiku para ambíguo, keywords para óbvio
        # Strip prefixo de mídia antes de rotear — evita "[Mensagem de áudio] Oi..."
        # confundir o classificador e rotear áudios clínicos como SAUDACAO
        texto_para_rotear = _extrair_texto_para_codigo(texto_para_processar)
        _is_audio = texto_para_processar.startswith("[Mensagem de áudio]") or texto_mensagem.startswith("[Mensagem de áudio]")
        modo = await rotear_mensagem(
            texto_para_rotear,
            historico[-6:] if historico else [],
            estado.nome_usuario,
            is_audio=_is_audio,
        )
        logger.info(f"Modo roteado (Meta): {modo.value}")
        # classificar_intencao só é chamado nos modos que usam RAG (economiza chamada Haiku)
        intencao = None

        resposta_texto: str | list[str] = ""
        # Inicializa nota de imagem para system prompt (pode ser preenchida no modo CONSULTA)
        _nota_imagem_sp = ""

        # 10. Saudação quando ATIVO
        if modo == ModoOperacao.SAUDACAO:
            # Mensagem muito curta com histórico = sinal de confusão (ex: "uê", "hm", "?")
            # → não repetir pergunta sobre caso/conteúdo; resposta simples de continuidade
            if len(texto_para_processar.strip()) <= 5 and historico:
                resposta_texto = gerar_resposta_confusao(estado.nome_usuario)
            elif memoria.get("is_nova_sessao") and memoria.get("resumos_sessoes"):
                msg_retomada = gerar_msg_retomada_sessao(
                    memoria["resumos_sessoes"], estado.nome_usuario
                )
                if msg_retomada:
                    resposta_texto = msg_retomada
                    asyncio.create_task(
                        processar_fim_sessao_em_background(
                            terapeuta_id, numero_paciente, historico
                        )
                    )
                else:
                    resposta_texto = gerar_saudacao_ativo(estado.nome_usuario, tem_historico_recente=bool(historico))
            else:
                resposta_texto = gerar_saudacao_ativo(estado.nome_usuario, tem_historico_recente=bool(historico))
                if memoria.get("is_nova_sessao") and historico:
                    asyncio.create_task(
                        processar_fim_sessao_em_background(
                            terapeuta_id, numero_paciente, historico
                        )
                    )

        elif modo == ModoOperacao.EMERGENCIA:
            resposta_texto = (
                "Percebo que você pode estar lidando com uma situação delicada. "
                "Sua segurança é prioridade absoluta.\n\n"
                "Se estiver em crise, ligue agora:\n"
                "CVV (Centro de Valorização da Vida): 188\n"
                "SAMU: 192\n"
                "Chat: https://www.cvv.org.br\n\n"
                f"Entre em contato também com {nome_terapeuta}"
            )
            if contato_terapeuta:
                resposta_texto += f": {contato_terapeuta}"

        elif modo == ModoOperacao.FORA_ESCOPO:
            resposta_texto = MENSAGEM_FORA_ESCOPO

        elif modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):

            # Classificar intenção apenas no branch RAG (economiza chamada Haiku)
            intencao = await classificar_intencao(texto_para_processar)

            top_k_busca = 10 if modo == ModoOperacao.CONSULTA else 5
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id, top_k=top_k_busca,
            )
            try:
                ctx_aprendizado = await carregar_contexto_terapeuta(terapeuta_id)
                ctx_formatado = formatar_contexto_personalizado(ctx_aprendizado)
            except Exception as e:
                logger.warning(f"Contexto de aprendizado indisponível (Meta): {e}")
                ctx_formatado = None

            # Montar texto dos chunks para injetar no prompt do especialista
            chunks_texto = "\n\n".join(
                c.get("conteudo", "") for c in contexto_chunks if c.get("conteudo")
            )

            # --- Injeção de Mapa Natal (Swiss Ephemeris via Kerykeion) ---
            # Verifica se a mensagem atual ou o histórico recente contém dados de nascimento.
            # Em modo CONSULTA, calcula o mapa natal e prepende ao contexto para eliminar
            # alucinações de Ascendente e posições planetárias.
            if modo == ModoOperacao.CONSULTA:
                texto_busca_nascimento = texto_para_processar
                # Também escaneia as últimas 10 mensagens do histórico
                if historico:
                    msgs_historico = " ".join(
                        m.get("content", "") or m.get("conteudo", "") or m.get("mensagem", "") or ""
                        for m in historico[-10:]
                    )
                    texto_busca_nascimento = f"{texto_para_processar}\n{msgs_historico}"

                dados_nasc = await extrair_dados_nascimento_llm(texto_busca_nascimento)
                if dados_nasc:
                    logger.info(f"[META-NASC] dados_nasc={dados_nasc} | msg='{texto_para_processar[:80]}'")

                # Interceptor: "refazer mapa" — busca dados do histórico e regera
                if _eh_pedido_refazer_mapa(texto_para_processar):
                    dados_hist = await extrair_dados_nascimento_llm(
                        " ".join(
                            (m.get("content", "") or m.get("conteudo", "") or m.get("mensagem", "") or "")
                            for m in (historico or [])
                        )
                    )
                    if dados_hist and not dados_hist.get("falta_ano") and not dados_hist.get("falta_cidade"):
                        dados_nasc = dados_hist
                        logger.info(f"[Meta] Refazer mapa: dados recuperados do histórico para {numero_paciente}")
                    else:
                        await meta_client.send_text_message(
                            phone_number=numero_paciente,
                            message="Para refazer o mapa, preciso dos dados de nascimento novamente. Me manda nome, data, hora e cidade.",
                        )
                        return

                # Interceptor pré-LLM: pedido de mapa sem nenhum dado → responder direto
                if not dados_nasc and _eh_pedido_mapa_sem_dados(texto_para_processar, historico):
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=_MSG_PEDE_DADOS_MAPA,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=_MSG_PEDE_DADOS_MAPA,
                        intencao="MAPA_NATAL_PEDE_DADOS",
                    )
                    logger.info(f"[Meta] Interceptado pedido de mapa sem dados — solicitando dados — {numero_paciente}")
                    return

                if dados_nasc and dados_nasc.get("falta_cidade"):
                    # Dados de nascimento detectados mas sem cidade — pedir ao paciente
                    nome_nasc = dados_nasc.get("nome", "Paciente")
                    msg_pede_cidade = (
                        f"Captei os dados: {dados_nasc.get('data', '')} às {dados_nasc.get('hora', '')}.\n\n"
                        f"Só falta a *cidade de nascimento*{' de ' + nome_nasc if nome_nasc != 'Paciente' else ''}. "
                        f"Qual a cidade?"
                    )
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=msg_pede_cidade,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_pede_cidade,
                        intencao="MAPA_NATAL_PEDE_CIDADE",
                    )
                    logger.info(f"[Meta] Pedindo cidade de nascimento para mapa natal — {numero_paciente}")
                    return

                if dados_nasc and dados_nasc.get("falta_ano"):
                    # Dados de nascimento detectados mas sem o ano — pedir ao terapeuta
                    nome_nasc = dados_nasc.get("nome", "Paciente")
                    data_parcial = dados_nasc.get("data_parcial", "")
                    msg_pede_ano = (
                        f"Captei os dados de nascimento: {data_parcial}, "
                        f"{dados_nasc.get('hora', '')} em {dados_nasc.get('cidade', '')}.\n\n"
                        f"Para calcular o mapa natal preciso também do *ano de nascimento*. "
                        f"Qual o ano de nascimento{' de ' + nome_nasc if nome_nasc != 'Paciente' else ''}?"
                    )
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=msg_pede_ano,
                    )
                    await _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=msg_pede_ano,
                        intencao="MAPA_NATAL_PEDE_ANO",
                    )
                    logger.info(f"[Meta] Pedindo ano de nascimento para mapa natal — {numero_paciente}")
                    return

                # Cache de mapas: consulta o banco antes de recalcular com Kerykeion.
                # Se o mapa já existe para esse paciente+data+hora, injeta o JSON salvo.
                # "refazer mapa" força nova geração e atualiza o cache.
                _eh_refazer = _eh_pedido_refazer_mapa(texto_para_processar)
                _mapa_json_cache = None
                # Inicializa variável de nota de imagem para system prompt (usada mais abaixo)
                _nota_imagem_sp = ""
                if dados_nasc and not dados_nasc.get("falta_ano") and not dados_nasc.get("falta_cidade") and not _eh_refazer:
                    _mapa_json_cache = await asyncio.to_thread(
                        _buscar_mapa_salvo, terapeuta_id, numero_paciente,
                        dados_nasc["data"], dados_nasc["hora"],
                    )
                    if _mapa_json_cache:
                        logger.info(
                            f"[Meta] Mapa em cache para {numero_paciente} "
                            f"({dados_nasc['data']} {dados_nasc['hora']}) — injetando sem recalcular"
                        )
                        mapa_prefixo = (
                            "MAPA NATAL CALCULADO AUTOMATICAMENTE (Swiss Ephemeris — dado preciso, nao alucinado):\n"
                            f"{_mapa_json_cache}\n\n"
                        )
                        chunks_texto = mapa_prefixo + chunks_texto

                if not _mapa_json_cache and dados_nasc and not dados_nasc.get("falta_ano") and not dados_nasc.get("falta_cidade"):
                    # Pré-mensagem: avisa que está gerando (melhora UX)
                    nome_nasc_pre = dados_nasc.get("nome", "")
                    msg_gerando = (
                        f"Calculando o mapa alquímico de {nome_nasc_pre} agora."
                        if nome_nasc_pre else "Calculando o mapa alquímico agora."
                    )
                    msg_gerando += " A imagem chega em instantes — já faço a leitura na sequência."
                    try:
                        await meta_client.send_text_message(
                            phone_number=numero_paciente, message=msg_gerando,
                        )
                    except Exception:
                        pass  # pré-mensagem não é crítica
                    imagem_enviada = False  # inicializa ANTES do try para o except conseguir verificar
                    _nota_imagem_sp = ""   # será sobrescrito dentro do try se tudo correr bem
                    try:
                        logger.info(f"[META-MAPA] Calculando mapa para {dados_nasc.get('nome')} {dados_nasc['data']} {dados_nasc['hora']} {dados_nasc['cidade']}")
                        mapa_resultado, mapa_png_joel, mapa_png_trad = await asyncio.wait_for(
                            asyncio.to_thread(
                                gerar_mapa_completo,
                                dados_nasc.get("nome", "Paciente"),
                                dados_nasc["data"],
                                dados_nasc["hora"],
                                dados_nasc["cidade"],
                            ),
                            timeout=90.0,
                        )
                        logger.info(f"[META-MAPA] gerar_mapa_completo retornou — joel={'OK '+str(len(mapa_png_joel))+' bytes' if mapa_png_joel else 'None'} | trad={'OK '+str(len(mapa_png_trad))+' bytes' if mapa_png_trad else 'None'}")
                        # Envia as duas imagens antes da resposta textual
                        _caption_base = (
                            f"{dados_nasc.get('nome', 'Paciente')}\n"
                            f"{dados_nasc['data']} {dados_nasc['hora']} | {dados_nasc['cidade']}"
                        )
                        for _img_bytes, _img_caption in [
                            (mapa_png_trad, f"Mapa Natal — {_caption_base}"),
                            (mapa_png_joel, f"Mapa Alquimico — {_caption_base}"),
                        ]:
                            if not _img_bytes:
                                continue
                            for tentativa_img in range(1, 3):
                                try:
                                    resp_img = await meta_client.send_image_message(
                                        phone_number=numero_paciente,
                                        imagem_bytes=_img_bytes,
                                        caption=_img_caption,
                                    )
                                    imagem_enviada = True
                                    _MAPA_FALHAS[numero_paciente] = 0
                                    logger.info(f"[META-MAPA] Imagem enviada com sucesso para {numero_paciente} (tentativa {tentativa_img})")
                                    logger.info(f"Imagem enviada para {numero_paciente} — Meta tentativa {tentativa_img} | resp={resp_img}")
                                    break
                                except Exception as img_send_err:
                                    logger.info(f"[META-MAPA] ERRO envio imagem tentativa {tentativa_img}/2: {img_send_err}")
                                    logger.warning(
                                        f"Envio da imagem falhou tentativa {tentativa_img}/2 (Meta): {img_send_err}",
                                        exc_info=True,
                                    )
                                    if tentativa_img < 2:
                                        await asyncio.sleep(2)
                        if not mapa_png_joel and not mapa_png_trad:
                            logger.info(f"[META-MAPA] Ambas as imagens são None — não geradas para {numero_paciente}")
                            logger.warning(f"Ambas as imagens são None para {numero_paciente} — imagens não geradas (Meta)")

                        # Se imagem não chegou, avisa o usuário com instrução de retry
                        if not imagem_enviada:
                            msg_fallback = (
                                MSG_ERRO_MAPA_IMAGEM
                            )
                            try:
                                await meta_client.send_text_message(
                                    phone_number=numero_paciente, message=msg_fallback,
                                )
                            except Exception:
                                pass

                        # Nota vai para o system prompt (não para chunks — evita LLM reproduzir o texto)
                        _nota_imagem_sp = (
                            "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                            "A imagem do mapa alquimico ja foi enviada como arquivo separado. "
                            "NAO mencione a imagem, NAO diga que foi enviada, NAO diga que houve instabilidade. "
                            "Va direto para a leitura alquimica completa — comece pela primeira linha."
                            if imagem_enviada else
                            "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                            "A imagem do mapa NAO foi enviada desta vez por instabilidade tecnica. "
                            "O terapeuta JA foi avisado sobre o problema via mensagem anterior. "
                            "ENTREGUE A LEITURA ALQUIMICA COMPLETA AGORA — nao peca permissao, nao pergunte se deve continuar, nao mencione a imagem nem o problema tecnico."
                        )
                        mapa_prefixo = (
                            f"MAPA NATAL CALCULADO AUTOMATICAMENTE (Swiss Ephemeris — dado preciso, nao alucinado):\n"
                            f"{mapa_resultado}\n\n"
                        )
                        chunks_texto = mapa_prefixo + chunks_texto
                        # Salvar mapa no banco para cache futuro (background — não bloqueia resposta)
                        # Inclui imagens para upload ao Supabase Storage
                        asyncio.create_task(asyncio.to_thread(
                            _salvar_mapa,
                            terapeuta_id, numero_paciente,
                            dados_nasc.get("nome", ""), dados_nasc["data"],
                            dados_nasc["hora"], dados_nasc["cidade"],
                            mapa_resultado,
                            mapa_png_joel, mapa_png_trad,
                        ))
                        logger.info(
                            f"Mapa natal calculado para '{dados_nasc.get('nome')}' "
                            f"({dados_nasc['data']} {dados_nasc['hora']} em {dados_nasc['cidade']}) — Meta"
                        )
                    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as mapa_err:
                        logger.info(f"[META-MAPA] EXCECAO no calculo/envio do mapa: {type(mapa_err).__name__}: {mapa_err}")
                        logger.warning(
                            f"Cálculo de mapa natal falhou (Meta) — {mapa_err}",
                            exc_info=True,
                        )
                        if imagem_enviada:
                            # Imagem já enviada — exceção ocorreu depois. Continua para gerar o texto.
                            logger.info(f"[META-MAPA] Imagem ja enviada — continuando para gerar texto mesmo com excecao")
                            if not _nota_imagem_sp:
                                _nota_imagem_sp = (
                                    "\n\nINSTRUCAO INTERNA — nao reproduza este aviso na resposta: "
                                    "A imagem do mapa alquimico ja foi enviada como arquivo separado. "
                                    "NAO mencione a imagem, NAO diga que foi enviada, NAO diga que houve instabilidade. "
                                    "Va direto para a leitura alquimica completa — comece pela primeira linha."
                                )
                            # chunks_texto pode não ter o mapa_prefixo, mas o LLM ainda gera a leitura
                        else:
                            # Imagem nunca enviada — falha real no cálculo
                            _MAPA_FALHAS[numero_paciente] = _MAPA_FALHAS.get(numero_paciente, 0) + 1
                            # Evitar crescimento ilimitado do dict de falhas
                            if len(_MAPA_FALHAS) > 200:
                                keys_to_remove = list(_MAPA_FALHAS.keys())[:100]
                                for k in keys_to_remove:
                                    del _MAPA_FALHAS[k]
                            tentativas_falha = _MAPA_FALHAS.get(numero_paciente, 0)
                            if tentativas_falha >= _MAPA_MAX_TENTATIVAS:
                                # 3ª falha consecutiva — avisar o usuário e sugerir suporte
                                _MAPA_FALHAS[numero_paciente] = 0
                                msg_suporte = (
                                    f"Pedimos desculpas pelo transtorno! Após {_MAPA_MAX_TENTATIVAS} tentativas, "
                                    f"o mapa natal ainda não conseguiu ser gerado. "
                                    f"O erro foi registrado automaticamente.\n\n"
                                    f"Por favor, abra um chamado de suporte: *{NUMERO_SUPORTE}*"
                                )
                                try:
                                    await meta_client.send_text_message(
                                        phone_number=numero_paciente, message=msg_suporte,
                                    )
                                except Exception:
                                    pass
                            # tentativas 1 e 2 sem imagem: silencioso — não chamar LLM
                            return

            # Selecionar prompt do agente especialista com fallback para None (usa genérico)
            try:
                if modo == ModoOperacao.CONSULTA:
                    system_prompt_especialista = get_prompt_agente_caso_clinico(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                elif modo == ModoOperacao.PESQUISA:
                    system_prompt_especialista = get_prompt_agente_metodo(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                elif modo == ModoOperacao.CRIACAO_CONTEUDO:
                    system_prompt_especialista = get_prompt_agente_conteudo(
                        config_terapeuta, chunks_texto, memoria_fmt or ""
                    )
                else:
                    system_prompt_especialista = None
            except Exception as e:
                logger.warning(f"Falha ao montar prompt especialista (Meta): {e}. Usando genérico.")
                system_prompt_especialista = None

            # Injetar nota da imagem no system prompt (não nos chunks — evita LLM reproduzir o texto)
            if _nota_imagem_sp:
                system_prompt_especialista = (system_prompt_especialista or "") + _nota_imagem_sp

            try:
                resposta_texto = await gerar_resposta(
                    pergunta=texto_para_processar,
                    terapeuta_id=terapeuta_id,
                    contexto_chunks=contexto_chunks,
                    config_terapeuta=config_terapeuta,
                    historico_mensagens=historico if historico else None,
                    contexto_personalizado=ctx_formatado,
                    memoria_usuario=memoria_fmt,
                    modo_override=modo,
                    system_prompt_override=system_prompt_especialista,
                )
            except Exception as e:
                logger.error(f"Falha ao gerar resposta Claude (Meta): {e}", exc_info=True)
                await meta_client.send_text_message(
                    phone_number=numero_paciente,
                    message=MSG_ERRO_MENSAGEM,
                )
                return
        else:
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id,
            )
            try:
                resposta_texto = await gerar_resposta(
                    pergunta=texto_para_processar,
                    terapeuta_id=terapeuta_id,
                    contexto_chunks=contexto_chunks,
                    config_terapeuta=config_terapeuta,
                    memoria_usuario=memoria_fmt,
                )
            except Exception as e:
                logger.error(f"Falha ao gerar resposta Claude (Meta, fallback): {e}", exc_info=True)
                await meta_client.send_text_message(
                    phone_number=numero_paciente,
                    message=MSG_ERRO_MENSAGEM,
                )
                return

        # 11. Enviar resposta (com rate limiting anti-ban)
        if resposta_texto:
            if isinstance(resposta_texto, list):
                resposta_texto = [humanizar_resposta(seg) for seg in resposta_texto]
                await _enviar_sequencia_meta(resposta_texto, meta_client, numero_paciente)
            elif "---SECAO---" in resposta_texto:
                # Resposta dividida em seções: cada seção vira uma mensagem separada
                secoes = [humanizar_resposta(s.strip()) for s in resposta_texto.split("---SECAO---") if s.strip()]
                await _enviar_sequencia_meta(secoes, meta_client, numero_paciente)
            else:
                resposta_texto = humanizar_resposta(resposta_texto)
                await aguardar_antes_de_enviar(numero_paciente, sequencial=False)
                await meta_client.send_text_message(
                    phone_number=numero_paciente, message=resposta_texto,
                )
            logger.info(f"Resposta enviada para {numero_paciente} via Meta")

        # 12. Salvar conversa com detecção de paciente vinculado
        resposta_salvar = " | ".join(resposta_texto) if isinstance(resposta_texto, list) else resposta_texto
        _intencao_str_meta = (
            f"{modo.value}|{intencao.value if hasattr(intencao, 'value') else str(intencao)}"
            if intencao is not None
            else modo.value
        )

        # Detectar paciente vinculado
        paciente_vinculado_id_meta = None
        if modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            try:
                paciente_vinculado_id_meta = await _detectar_paciente_vinculado(
                    terapeuta_id, numero_paciente, texto_mensagem, resposta_salvar or "", modo.value,
                )
            except Exception as e:
                logger.warning(f"Detecção de paciente vinculado falhou (Meta): {e}")

        await _salvar_conversa(
            terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
            mensagem_paciente=texto_mensagem, resposta_agente=resposta_salvar,
            intencao=_intencao_str_meta,
            paciente_vinculado_id=paciente_vinculado_id_meta,
        )

        # 13. Background: timestamp + perfil + aprendizado + guardião
        asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
        asyncio.create_task(
            atualizar_perfil_apos_interacao(
                terapeuta_id, numero_paciente, estado.nome_usuario, texto_mensagem, modo.value
            )
        )
        # Guardião: monitora resposta em background, nunca bloqueia o usuário
        if resposta_salvar:
            asyncio.create_task(
                verificar_resposta(terapeuta_id, numero_paciente, texto_para_processar, resposta_salvar)
            )
        if modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            try:
                asyncio.create_task(
                    analisar_conversa(
                        terapeuta_id=terapeuta_id, mensagem=texto_mensagem,
                        resposta=resposta_salvar, modo=modo.value,
                    )
                )
            except Exception as e:
                logger.warning(f"Falha no aprendizado contínuo (Meta): {e}")
        # Extracao automatica de diagnostico (background, somente CONSULTA com paciente vinculado)
        if modo == ModoOperacao.CONSULTA and paciente_vinculado_id_meta and resposta_salvar:
            asyncio.create_task(
                processar_diagnostico_auto(
                    resposta=resposta_salvar,
                    terapeuta_id=terapeuta_id,
                    paciente_id=paciente_vinculado_id_meta,
                )
            )

    except Exception as e:
        logger.error(f"Erro ao processar mensagem Meta: {e}", exc_info=True)


# =============================================
# META CLOUD API — ROTAS
# =============================================

@router.get("/meta", summary="Verificação do webhook Meta (challenge)")
async def verificar_webhook_meta(
    request: Request,
):
    """
    Endpoint de verificação do webhook da Meta WhatsApp Cloud API.
    A Meta envia um GET com hub.mode, hub.verify_token e hub.challenge.
    Se o verify_token bater, retorna o hub.challenge para confirmar o webhook.
    """
    settings = get_settings()
    params = request.query_params

    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    logger.info(
        f"Webhook Meta verificação recebida — mode={mode}, "
        f"token={'***' if token else 'vazio'}, challenge={challenge[:20]}..."
    )

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        logger.info("Webhook Meta verificado com sucesso!")
        # Meta espera o challenge como resposta em texto puro
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=challenge)

    logger.warning(
        f"Webhook Meta verificação falhou — token inválido "
        f"(recebido: {'***' if token else 'vazio'}, "
        f"META_VERIFY_TOKEN configurado: {'sim' if settings.META_VERIFY_TOKEN else 'NÃO — variável vazia!'})"
    )
    raise HTTPException(status_code=403, detail="Token de verificação inválido")


@router.post("/meta", summary="Recebe webhook da Meta WhatsApp Cloud API")
async def receber_webhook_meta(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Endpoint que recebe os webhooks da Meta WhatsApp Cloud API quando uma
    mensagem chega no WhatsApp. Processa em background para responder rápido (200 OK).

    A Meta envia o payload com object='whatsapp_business_account' e as mensagens
    dentro de entry[].changes[].value.messages[].
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Webhook Meta recebeu payload inválido (não é JSON)")
        raise HTTPException(status_code=400, detail="Payload inválido — esperado JSON")

    # Verificar se é um payload válido do WhatsApp
    if body.get("object") != "whatsapp_business_account":
        logger.debug(f"Webhook Meta ignorado — object: {body.get('object')}")
        return {"status": "ignorado"}

    # Verificar se contém mensagens (e não apenas status updates)
    entry = body.get("entry", [])
    if not entry:
        return {"status": "ignorado", "motivo": "sem entries"}

    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ignorado", "motivo": "sem changes"}

    value = changes[0].get("value", {})
    messages = value.get("messages", [])

    # Se não tem mensagens, pode ser um status update (delivered, read, etc.)
    if not messages:
        statuses = value.get("statuses", [])
        if statuses:
            logger.debug(f"Status update Meta recebido: {statuses[0].get('status', 'N/A')}")
        return {"status": "ignorado", "motivo": "sem mensagens (status update)"}

    # Processar a mensagem em background (não travar o webhook)
    background_tasks.add_task(_processar_mensagem_meta, body)

    numero_remetente = messages[0].get("from", "desconhecido")
    logger.info(
        f"Webhook Meta recebido — remetente={numero_remetente}, "
        f"tipo={messages[0].get('type', 'N/A')}"
    )

    # Meta espera 200 OK imediatamente
    return {"status": "recebido", "origem": "meta_cloud_api"}
