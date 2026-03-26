"""
Endpoint de teste — permite conversar com o agente sem WhatsApp.
Mantém histórico de conversa por sessão para contexto multi-turno.
Inclui gerenciamento de sessões por paciente (confirmação, troca, dados isolados).
Suporta upload de imagens (analise visual via Claude), PDFs e audio.
"""

import base64
import io
import logging
from collections import defaultdict
from typing import Optional

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.core.prompts import detectar_modo, ModoOperacao, MENSAGEM_FORA_ESCOPO
from src.core.niveis import filtrar_chunks_por_nivel, mensagem_nivel_bloqueado
from src.core.pacientes import (
    gerenciador_pacientes,
    formatar_contexto_paciente,
)
from src.rag.retriever import buscar_contexto
from src.rag.generator import gerar_resposta
from src.core.ux_rules import humanizar_resposta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teste", tags=["Teste"])

# Histórico em memória por session_id (simples, para teste)
_historico: dict[str, list[dict]] = defaultdict(list)

# Estado de onboarding por session_id
# etapa 0 = sessao nova (ainda nao iniciou)
# etapa 1 = esperando nome do terapeuta
# etapa 2 = esperando info do paciente
# etapa 3+ = fluxo normal (diagnostico via RAG)
_onboarding: dict[str, dict] = {}


def _get_onboarding(session_id: str) -> dict:
    """Retorna o estado de onboarding da sessao. Cria se nao existir."""
    if session_id not in _onboarding:
        _onboarding[session_id] = {"etapa": 0, "nome_terapeuta": None}
    return _onboarding[session_id]


def _extrair_nome_simples(mensagem: str) -> str:
    """Extrai o nome do terapeuta de uma resposta simples.
    Pega a primeira palavra com letra maiuscula ou, se nao houver, a primeira palavra."""
    msg = mensagem.strip().rstrip(".!,;")
    # Se a resposta e curta (ate 4 palavras), pega a primeira palavra relevante
    palavras = msg.split()
    if not palavras:
        return msg
    # Tenta pegar primeira palavra que comeca com maiuscula
    for p in palavras:
        p_limpa = p.strip(".,!?;:")
        if p_limpa and p_limpa[0].isupper() and len(p_limpa) >= 2:
            return p_limpa
    # Se nenhuma com maiuscula, pega a primeira
    return palavras[0].strip(".,!?;:").capitalize()


class ChatRequest(BaseModel):
    terapeuta_id: str
    mensagem: str
    session_id: str = "default"


@router.post("/chat")
async def chat_teste(req: ChatRequest):
    """Endpoint de teste: envia mensagem e recebe resposta do agente com histórico."""
    try:
        supabase = get_supabase()
        result = supabase.table("terapeutas").select("*").eq("id", req.terapeuta_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Terapeuta nao encontrado")

        terapeuta = result.data[0]

        # =================================================================
        # FLUXO DE ONBOARDING EM ETAPAS
        # =================================================================
        onb = _get_onboarding(req.session_id)

        # ETAPA 0 — Sessao nova: envia boas-vindas e marca etapa 1
        if onb["etapa"] == 0:
            resposta = (
                "Ola, muito prazer! Eu sou o facilitador para seus "
                "atendimentos aqui na Escola de Alquimia do Joel Aleixo."
                "\n\nComo gostaria que eu te chamasse?"
            )
            onb["etapa"] = 1
            # Salvar mensagem do usuario e resposta no historico
            _historico[req.session_id].append({
                "role": "terapeuta",
                "content": req.mensagem,
            })
            _historico[req.session_id].append({
                "role": "agente",
                "content": resposta,
            })
            logger.info(f"[ONBOARDING] Etapa 0->1 | session={req.session_id}")
            return {
                "resposta": resposta,
                "modo": "ONBOARDING_BOAS_VINDAS",
                "fontes": "",
                "chunks_encontrados": 0,
            }

        # ETAPA 1 — Esperando nome do terapeuta
        if onb["etapa"] == 1:
            nome = _extrair_nome_simples(req.mensagem)
            onb["nome_terapeuta"] = nome
            onb["etapa"] = 2
            resposta = (
                f"Perfeito, {nome}! Que bom ter voce aqui."
                "\n\nMe conta, sobre quem vamos falar hoje?"
            )
            _historico[req.session_id].append({
                "role": "terapeuta",
                "content": req.mensagem,
            })
            _historico[req.session_id].append({
                "role": "agente",
                "content": resposta,
            })
            logger.info(
                f"[ONBOARDING] Etapa 1->2 | nome={nome} | session={req.session_id}"
            )
            return {
                "resposta": resposta,
                "modo": "ONBOARDING_NOME",
                "fontes": "",
                "chunks_encontrados": 0,
            }

        # ETAPA 2 — Esperando info do paciente, avanca para fluxo normal
        if onb["etapa"] == 2:
            onb["etapa"] = 3
            logger.info(
                f"[ONBOARDING] Etapa 2->3 | session={req.session_id} | "
                f"terapeuta={onb['nome_terapeuta']}"
            )
            # Cai no fluxo normal abaixo (etapa 3+)

        # =================================================================
        # ETAPA 3+ — Fluxo normal (deteccao de modo, RAG, diagnostico)
        # =================================================================
        modo = detectar_modo(req.mensagem)

        # Salvar mensagem do usuário no histórico
        _historico[req.session_id].append({
            "role": "terapeuta",
            "content": req.mensagem,
        })

        # Saudacao apos onboarding: nao reseta, mantem fluxo normal
        if modo == ModoOperacao.SAUDACAO:
            nome_t = onb.get("nome_terapeuta") or terapeuta.get("nome", "Terapeuta")
            resposta = f"Oi, {nome_t}! Como posso te ajudar agora?"
            resposta = humanizar_resposta(resposta)
            _historico[req.session_id].append({"role": "agente", "content": resposta})
            return {"resposta": resposta, "modo": "SAUDACAO", "fontes": "", "chunks_encontrados": 0}

        if modo == ModoOperacao.EMERGENCIA:
            resposta = humanizar_resposta(
                "Percebo que voce esta passando por um momento muito dificil. "
                "Por favor, ligue agora para o CVV no 188 ou acesse cvv.org.br. "
                "Eles estao disponiveis 24 horas e podem te ajudar."
            )
            _historico[req.session_id].append({"role": "agente", "content": resposta})
            return {"resposta": resposta, "modo": "EMERGENCIA", "fontes": "", "chunks_encontrados": 0}

        if modo == ModoOperacao.FORA_ESCOPO:
            resposta = humanizar_resposta(MENSAGEM_FORA_ESCOPO)
            _historico[req.session_id].append({"role": "agente", "content": resposta})
            return {"resposta": resposta, "modo": "FORA_ESCOPO", "fontes": "", "chunks_encontrados": 0}

        # =====================================================================
        # GERENCIAMENTO DE PACIENTE (apenas no modo CONSULTA)
        # =====================================================================
        contexto_paciente = None
        info_paciente = {}

        if modo == ModoOperacao.CONSULTA:
            sessao_paciente, msg_sistema = gerenciador_pacientes.processar_mensagem(
                req.session_id, req.mensagem
            )

            # Se o gerenciador gerou mensagem de sistema (pedido de nome ou confirmacao),
            # insere antes da resposta principal
            if msg_sistema:
                msg_sistema_humanizada = humanizar_resposta(msg_sistema)
                _historico[req.session_id].append({
                    "role": "agente",
                    "content": msg_sistema_humanizada,
                })

            # Formatar contexto do paciente para o prompt
            if sessao_paciente:
                contexto_paciente = formatar_contexto_paciente(sessao_paciente)
                info_paciente = {
                    "paciente_nome": sessao_paciente.nome_paciente,
                    "paciente_turno": sessao_paciente.turno,
                    "paciente_confirmado": sessao_paciente.confirmado,
                }

        # =====================================================================
        # BUSCA E FILTRAGEM DE CHUNKS
        # =====================================================================
        nivel_acesso = terapeuta.get("nivel_acesso", 1) or 1
        # CONSULTA usa top_k=10 para trazer mais contexto alquimico no diagnostico
        top_k_busca = 10 if modo == ModoOperacao.CONSULTA else 5
        chunks = await buscar_contexto(req.mensagem, req.terapeuta_id, top_k=top_k_busca)

        # Filtrar chunks pelo nivel de acesso do terapeuta
        chunks, nivel_bloqueado = filtrar_chunks_por_nivel(chunks, nivel_acesso)

        # Se todos os chunks foram filtrados (conteudo bloqueado), retorna mensagem de nivel
        if not chunks and nivel_bloqueado is not None:
            resposta = humanizar_resposta(
                mensagem_nivel_bloqueado(nivel_bloqueado, nivel_acesso)
            )
            _historico[req.session_id].append({"role": "agente", "content": resposta})
            return {
                "resposta": resposta,
                "modo": "NIVEL_BLOQUEADO",
                "fontes": "",
                "chunks_encontrados": 0,
                "nivel_acesso": nivel_acesso,
                "nivel_necessario": nivel_bloqueado,
            }

        logger.info(
            f"[TESTE] Chunks: {len(chunks)} | Modo: {modo.value} | "
            f"Nivel: {nivel_acesso} | "
            f"Historico: {len(_historico[req.session_id])} msgs | "
            f"Paciente: {info_paciente.get('paciente_nome', 'N/A')} | "
            f"Mensagem: '{req.mensagem[:80]}'"
        )

        # Usar nome do onboarding se disponivel, senao o do banco
        nome_terapeuta = (
            onb.get("nome_terapeuta")
            or terapeuta.get("nome", "Joel Aleixo")
        )

        config_terapeuta = {
            "nome": nome_terapeuta,
            "especialidade": terapeuta.get("especialidade", "Alquimia Terapeutica"),
            "tom_de_voz": terapeuta.get("tom_de_voz", "profissional e acolhedor"),
            "contato": terapeuta.get("telefone", ""),
        }

        # Passar histórico completo pro gerador
        historico = _historico[req.session_id][:-1]  # Tudo menos a última (que é a mensagem atual)

        resposta_texto = await gerar_resposta(
            pergunta=req.mensagem,
            terapeuta_id=req.terapeuta_id,
            contexto_chunks=chunks,
            config_terapeuta=config_terapeuta,
            historico_mensagens=historico if historico else None,
            contexto_personalizado=contexto_paciente,
        )

        resposta_texto = humanizar_resposta(resposta_texto)

        # Salvar resposta no histórico
        _historico[req.session_id].append({"role": "agente", "content": resposta_texto})

        # Limitar histórico a 40 mensagens (20 turnos)
        if len(_historico[req.session_id]) > 40:
            _historico[req.session_id] = _historico[req.session_id][-40:]

        # Fontes NUNCA sao retornadas ao frontend — quebra humanizacao
        resposta_final = {
            "resposta": resposta_texto,
            "modo": modo.value if hasattr(modo, 'value') else str(modo),
            "fontes": "",
            "chunks_encontrados": len(chunks),
        }

        # Adicionar info do paciente na resposta (apenas em modo CONSULTA)
        if info_paciente:
            resposta_final["paciente"] = info_paciente

        return resposta_final

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no chat de teste: {e}", exc_info=True)
        return {"resposta": f"Erro interno: {str(e)}", "modo": "ERRO", "fontes": ""}


@router.post("/limpar")
async def limpar_historico(session_id: str = "default"):
    """Limpa o histórico de uma sessão, onboarding e sessões de pacientes."""
    _historico.pop(session_id, None)
    _onboarding.pop(session_id, None)
    gerenciador_pacientes.limpar_sessao(session_id)
    return {"status": "historico limpo", "session_id": session_id}


@router.get("/paciente/{session_id}")
async def info_paciente(session_id: str):
    """Retorna informações da sessão ativa do paciente e histórico de pacientes."""
    sessao = gerenciador_pacientes.get_sessao_ativa(session_id)
    historico = gerenciador_pacientes.get_historico_pacientes(session_id)

    return {
        "sessao_ativa": sessao.to_dict() if sessao else None,
        "historico_pacientes": historico,
        "total_pacientes": len(historico) + (1 if sessao else 0),
    }


# =========================================================================
# UPLOAD DE ARQUIVOS (imagens, PDFs, audio)
# =========================================================================

# Tipos MIME aceitos
MIME_IMAGENS = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MIME_PDFS = {"application/pdf"}
MIME_AUDIO = {
    "audio/mpeg", "audio/mp3", "audio/ogg", "audio/wav",
    "audio/x-wav", "audio/mp4", "audio/m4a", "audio/x-m4a",
}

# Prompt especifico para analise de mapa astral / imagens
PROMPT_ANALISE_IMAGEM = (
    "Analise esta imagem com cuidado. "
    "Se for um mapa astral (carta natal), identifique:\n"
    "- Os signos solares, lunares e ascendente visiveis\n"
    "- As casas astrologicas e seus significados\n"
    "- Posicoes planetarias relevantes\n"
    "- Aspectos (conjuncoes, oposicoes, quadraturas, trigonos)\n\n"
    "Conecte a analise com o diagnostico alquimico do paciente, usando o "
    "conhecimento da Astrologia Alquimica do Joel Aleixo:\n"
    "- Casa 1 (Aries): identidade, corpo fisico, vitalidade\n"
    "- Casa 4 (Cancer): emocoes, raizes, familia, memoria ancestral\n"
    "- Casa 6 (Virgem): saude, rotina, purificacao\n"
    "- Casa 8 (Escorpiao): transformacao, crises, morte simbolica, regeneracao\n"
    "- Casa 12 (Peixes): inconsciente, espiritualidade, karmas\n\n"
    "Se for uma foto de cartas (tarot, oraculo), identifique as cartas visiveis "
    "e interprete seus significados no contexto alquimico.\n\n"
    "Se for qualquer outra imagem, descreva o que voce ve e como pode se "
    "relacionar com o processo terapeutico do paciente."
)


def _detectar_tipo_arquivo(content_type: str, filename: str) -> str:
    """Detecta o tipo do arquivo: 'imagem', 'pdf' ou 'audio'."""
    ct = (content_type or "").lower()
    ext = (filename or "").lower().rsplit(".", 1)[-1] if filename else ""

    if ct in MIME_IMAGENS or ext in ("jpg", "jpeg", "png", "webp", "gif"):
        return "imagem"
    if ct in MIME_PDFS or ext == "pdf":
        return "pdf"
    if ct in MIME_AUDIO or ext in ("mp3", "ogg", "wav", "m4a", "oga", "opus"):
        return "audio"
    return "desconhecido"


def _extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """Extrai texto de um PDF usando PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=conteudo_bytes, filetype="pdf")
        textos = []
        for pagina in doc:
            textos.append(pagina.get_text())
        doc.close()
        texto = "\n".join(textos).strip()
        if not texto:
            return "[PDF sem texto extraivel — pode ser imagem escaneada]"
        return texto
    except ImportError:
        return "[PyMuPDF nao instalado — nao foi possivel extrair texto do PDF]"
    except Exception as e:
        return f"[Erro ao extrair texto do PDF: {e}]"


async def _transcrever_audio(conteudo_bytes: bytes, filename: str) -> str:
    """Transcreve audio usando OpenAI Whisper API."""
    try:
        import openai
        settings = get_settings()
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

        # Criar file-like object com nome para a API
        audio_file = io.BytesIO(conteudo_bytes)
        audio_file.name = filename or "audio.mp3"

        transcricao = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt",
        )
        return transcricao.text.strip()
    except ImportError:
        return "[OpenAI nao instalado — nao foi possivel transcrever audio]"
    except Exception as e:
        return f"[Erro ao transcrever audio: {e}]"


@router.post("/upload")
async def upload_arquivo(
    arquivo: UploadFile = File(...),
    session_id: str = Form(default="default"),
    terapeuta_id: str = Form(default="5085ff75-fe00-49fe-95f4-a5922a0cf179"),
    mensagem: str = Form(default=""),
):
    """
    Endpoint de upload: recebe imagem, PDF ou audio e processa.
    - Imagens: envia pro Claude com visao para analise (mapa astral, cartas)
    - PDFs: extrai texto e adiciona como contexto na conversa
    - Audio: transcreve com Whisper e processa como mensagem de texto
    """
    try:
        # Validar terapeuta
        supabase = get_supabase()
        result = supabase.table("terapeutas").select("*").eq("id", terapeuta_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Terapeuta nao encontrado")
        terapeuta = result.data[0]

        # Ler conteudo do arquivo
        conteudo = await arquivo.read()
        tipo = _detectar_tipo_arquivo(arquivo.content_type, arquivo.filename)

        logger.info(
            f"[UPLOAD] Tipo: {tipo} | Arquivo: {arquivo.filename} | "
            f"Tamanho: {len(conteudo)} bytes | Session: {session_id}"
        )

        if tipo == "desconhecido":
            return {
                "resposta": (
                    "Desculpe, esse tipo de arquivo nao e suportado. "
                    "Envie imagens (JPG, PNG), PDFs ou audios (MP3, OGG, WAV, M4A)."
                ),
                "modo": "UPLOAD_ERRO",
                "tipo_arquivo": tipo,
            }

        # =================================================================
        # IMAGEM — Envia pro Claude com visao multimodal
        # =================================================================
        if tipo == "imagem":
            # Converter para base64
            base64_data = base64.b64encode(conteudo).decode("utf-8")

            # Determinar media type
            media_type = arquivo.content_type or "image/jpeg"
            if media_type not in MIME_IMAGENS:
                media_type = "image/jpeg"

            # Texto do usuario (mensagem opcional + prompt de analise)
            texto_usuario = mensagem.strip() if mensagem.strip() else ""
            prompt_completo = PROMPT_ANALISE_IMAGEM
            if texto_usuario:
                prompt_completo = f"{texto_usuario}\n\n{PROMPT_ANALISE_IMAGEM}"

            # Recuperar historico para contexto
            historico = _historico[session_id][-20:]  # Ultimas 20 msgs

            # Montar mensagens com historico + imagem
            messages = []
            for msg in historico:
                role_original = msg.get("role", "")
                content = msg.get("content", "").strip()
                if not content:
                    continue
                if role_original in ("terapeuta", "user"):
                    role = "user"
                elif role_original in ("agente", "assistant"):
                    role = "assistant"
                else:
                    continue
                if messages and messages[-1]["role"] == role:
                    messages[-1]["content"] += "\n\n" + content
                else:
                    messages.append({"role": role, "content": content})

            # Adicionar mensagem com imagem
            msg_imagem = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt_completo,
                    },
                ],
            }

            # Garantir alternancia de roles
            if messages and messages[-1]["role"] == "user":
                messages.append({"role": "assistant", "content": "Entendido, estou pronto para analisar."})
            messages.append(msg_imagem)

            # Garantir primeira mensagem e user
            if messages and messages[0]["role"] != "user":
                messages.insert(0, {"role": "user", "content": "[Inicio da conversa]"})

            # Chamar Claude com visao
            settings = get_settings()
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                temperature=0,
                system=(
                    "Voce e o facilitador da Escola de Alquimia do Joel Aleixo. "
                    "Analise imagens (mapas astrais, cartas, fotos) com profundidade "
                    "alquimica e conecte com o processo terapeutico do paciente. "
                    "Responda em portugues brasileiro, de forma acolhedora e profissional."
                ),
                messages=messages,
            )

            resposta_texto = response.content[0].text
            resposta_texto = humanizar_resposta(resposta_texto)

            # Salvar no historico
            _historico[session_id].append({
                "role": "terapeuta",
                "content": f"[Enviou imagem: {arquivo.filename}] {texto_usuario}",
            })
            _historico[session_id].append({
                "role": "agente",
                "content": resposta_texto,
            })

            logger.info(
                f"[UPLOAD] Imagem analisada | Resposta: {len(resposta_texto)} chars | "
                f"Tokens: input={response.usage.input_tokens}, output={response.usage.output_tokens}"
            )

            return {
                "resposta": resposta_texto,
                "modo": "UPLOAD_IMAGEM",
                "tipo_arquivo": "imagem",
                "arquivo": arquivo.filename,
            }

        # =================================================================
        # PDF — Extrai texto e adiciona como contexto
        # =================================================================
        if tipo == "pdf":
            texto_pdf = _extrair_texto_pdf(conteudo)

            # Limitar tamanho do texto (maximo ~8000 chars para nao estourar contexto)
            if len(texto_pdf) > 8000:
                texto_pdf = texto_pdf[:8000] + "\n\n[... texto truncado por limite de tamanho ...]"

            texto_usuario = mensagem.strip() if mensagem.strip() else "Analise este documento."

            # Adicionar texto do PDF como contexto na conversa
            msg_contexto = (
                f"[Documento PDF enviado: {arquivo.filename}]\n\n"
                f"Conteudo extraido do PDF:\n---\n{texto_pdf}\n---\n\n"
                f"{texto_usuario}"
            )

            _historico[session_id].append({
                "role": "terapeuta",
                "content": msg_contexto,
            })

            # Gerar resposta usando o fluxo normal (RAG + historico)
            onb = _get_onboarding(session_id)
            nome_terapeuta = onb.get("nome_terapeuta") or terapeuta.get("nome", "Joel Aleixo")

            config_terapeuta = {
                "nome": nome_terapeuta,
                "especialidade": terapeuta.get("especialidade", "Alquimia Terapeutica"),
                "tom_de_voz": terapeuta.get("tom_de_voz", "profissional e acolhedor"),
                "contato": terapeuta.get("telefone", ""),
            }

            chunks = await buscar_contexto(texto_usuario, terapeuta_id, top_k=5)
            nivel_acesso = terapeuta.get("nivel_acesso", 1) or 1
            chunks, _ = filtrar_chunks_por_nivel(chunks, nivel_acesso)

            historico = _historico[session_id][:-1]

            resposta_texto = await gerar_resposta(
                pergunta=msg_contexto,
                terapeuta_id=terapeuta_id,
                contexto_chunks=chunks,
                config_terapeuta=config_terapeuta,
                historico_mensagens=historico if historico else None,
            )

            resposta_texto = humanizar_resposta(resposta_texto)

            _historico[session_id].append({
                "role": "agente",
                "content": resposta_texto,
            })

            logger.info(
                f"[UPLOAD] PDF processado | Texto: {len(texto_pdf)} chars | "
                f"Resposta: {len(resposta_texto)} chars"
            )

            return {
                "resposta": resposta_texto,
                "modo": "UPLOAD_PDF",
                "tipo_arquivo": "pdf",
                "arquivo": arquivo.filename,
                "texto_extraido_chars": len(texto_pdf),
            }

        # =================================================================
        # AUDIO — Transcreve com Whisper e processa como texto
        # =================================================================
        if tipo == "audio":
            transcricao = await _transcrever_audio(conteudo, arquivo.filename)

            if transcricao.startswith("["):
                # Erro na transcricao
                return {
                    "resposta": f"Nao foi possivel transcrever o audio. {transcricao}",
                    "modo": "UPLOAD_ERRO",
                    "tipo_arquivo": "audio",
                }

            logger.info(
                f"[UPLOAD] Audio transcrito | Duracao: ~{len(conteudo) // 16000}s | "
                f"Transcricao: '{transcricao[:100]}...'"
            )

            # Adicionar transcricao como mensagem do terapeuta e processar normalmente
            _historico[session_id].append({
                "role": "terapeuta",
                "content": f"[Audio transcrito: {arquivo.filename}]\n{transcricao}",
            })

            # Gerar resposta usando o fluxo normal
            onb = _get_onboarding(session_id)
            nome_terapeuta = onb.get("nome_terapeuta") or terapeuta.get("nome", "Joel Aleixo")

            config_terapeuta = {
                "nome": nome_terapeuta,
                "especialidade": terapeuta.get("especialidade", "Alquimia Terapeutica"),
                "tom_de_voz": terapeuta.get("tom_de_voz", "profissional e acolhedor"),
                "contato": terapeuta.get("telefone", ""),
            }

            chunks = await buscar_contexto(transcricao, terapeuta_id, top_k=5)
            nivel_acesso = terapeuta.get("nivel_acesso", 1) or 1
            chunks, _ = filtrar_chunks_por_nivel(chunks, nivel_acesso)

            historico = _historico[session_id][:-1]

            resposta_texto = await gerar_resposta(
                pergunta=transcricao,
                terapeuta_id=terapeuta_id,
                contexto_chunks=chunks,
                config_terapeuta=config_terapeuta,
                historico_mensagens=historico if historico else None,
            )

            resposta_texto = humanizar_resposta(resposta_texto)

            _historico[session_id].append({
                "role": "agente",
                "content": resposta_texto,
            })

            return {
                "resposta": resposta_texto,
                "modo": "UPLOAD_AUDIO",
                "tipo_arquivo": "audio",
                "arquivo": arquivo.filename,
                "transcricao": transcricao,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no upload: {e}", exc_info=True)
        return {"resposta": f"Erro ao processar arquivo: {str(e)}", "modo": "UPLOAD_ERRO"}
