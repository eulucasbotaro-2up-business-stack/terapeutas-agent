"""
Rota de webhook para receber mensagens do WhatsApp via Evolution API.
Processa a mensagem com RAG e responde automaticamente ao paciente.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.core.supabase_client import get_supabase
from src.core.prompts import (
    detectar_modo,
    ModoOperacao,
    gerar_boas_vindas,
    MENSAGEM_FORA_ESCOPO,
)
from src.rag.retriever import buscar_contexto
from src.rag.generator import gerar_resposta, classificar_intencao
from src.rag.aprendizado import (
    analisar_conversa,
    carregar_contexto_terapeuta,
    formatar_contexto_personalizado,
)
from src.whatsapp.evolution import EvolutionClient
from src.core.ux_rules import humanizar_resposta
from src.whatsapp.messages import (
    extrair_numero_mensagem,
    eh_mensagem_valida,
    formatar_aviso_audio,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook WhatsApp"])


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


def _salvar_conversa(
    terapeuta_id: str,
    paciente_numero: str,
    mensagem_paciente: str,
    resposta_agente: str,
    intencao: str,
) -> None:
    """
    Salva o registro da conversa na tabela 'conversas' para historico.
    Usa nomes de colunas corretos do schema do banco.
    """
    supabase = get_supabase()

    try:
        supabase.table("conversas").insert({
            "id": str(uuid4()),
            "terapeuta_id": terapeuta_id,
            "paciente_numero": paciente_numero,
            "mensagem_paciente": mensagem_paciente,
            "resposta_agente": resposta_agente,
            "intencao": intencao,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }).execute()

        logger.info(
            f"Conversa salva — terapeuta={terapeuta_id}, paciente={paciente_numero}"
        )
    except Exception as e:
        # Nao queremos que falha ao salvar conversa impeca a resposta
        logger.error(f"Erro ao salvar conversa: {e}")


# =============================================
# PROCESSAMENTO EM BACKGROUND
# =============================================

async def _processar_mensagem(payload: dict) -> None:
    """
    Processa a mensagem recebida do WhatsApp em background.
    Fluxo completo: classificar intenção → buscar contexto → gerar resposta → enviar.

    Args:
        payload: Payload JSON completo do webhook da Evolution API.
    """
    try:
        # 1. Extrair número e texto da mensagem (payload completo como dict)
        numero_paciente, texto_mensagem = extrair_numero_mensagem(payload)
        instance_name = payload.get("instance", "")

        logger.info(
            f"Processando mensagem de {numero_paciente} "
            f"na instância {instance_name}"
        )

        # 2. Validar que temos texto para processar
        if not texto_mensagem or not texto_mensagem.strip():
            logger.info("Mensagem sem texto (áudio, imagem, etc) — ignorando")
            return

        # Tratar mensagens de áudio com aviso específico
        if texto_mensagem == "[AUDIO_NAO_SUPORTADO]":
            evolution = EvolutionClient()
            await evolution.enviar_mensagem(
                instance=instance_name,
                numero=numero_paciente,
                texto=formatar_aviso_audio(),
            )
            return

        # Ignorar outros tipos não suportados
        if texto_mensagem.startswith("[") and texto_mensagem.endswith("]"):
            logger.info(f"Tipo de mensagem não suportado: {texto_mensagem} — ignorando")
            return

        # 3. Identificar o terapeuta pela instância do Evolution
        terapeuta = _buscar_terapeuta_por_instancia(instance_name)
        if not terapeuta:
            logger.warning(
                f"Nenhum terapeuta encontrado para instância '{instance_name}'"
            )
            return

        terapeuta_id = terapeuta["id"]
        nome_terapeuta = terapeuta.get("nome", "Terapeuta")
        contato_terapeuta = terapeuta.get("telefone", "")
        especialidade = terapeuta.get("especialidade", "Terapia Holística")
        tom_voz = terapeuta.get("tom_de_voz", "profissional e acolhedor")

        # Configuração do terapeuta para o gerador de respostas
        config_terapeuta = {
            "nome_terapeuta": nome_terapeuta,
            "especialidade": especialidade,
            "tom_voz": tom_voz,
            "contato": contato_terapeuta,
        }

        # 4. Inicializar cliente Evolution para enviar respostas
        evolution = EvolutionClient()

        # 5. Detectar modo de operacao (CONSULTA, CRIACAO_CONTEUDO, PESQUISA, SAUDACAO, EMERGENCIA, FORA_ESCOPO)
        modo = detectar_modo(texto_mensagem)
        logger.info(f"Modo de operação detectado: {modo.value}")

        # 6. Classificar a intenção da mensagem (via LLM, para logging e fallback)
        intencao = await classificar_intencao(texto_mensagem)
        logger.info(f"Intenção classificada (LLM): {intencao}")

        resposta_texto = ""

        # 7. Processar de acordo com o modo detectado
        if modo == ModoOperacao.SAUDACAO:
            # Usa a mensagem de boas-vindas da Alquimia (apresenta os 3 modos)
            resposta_texto = gerar_boas_vindas(config_terapeuta)

        elif modo == ModoOperacao.EMERGENCIA:
            # Emergencia: acolhimento + encaminhamento profissional obrigatorio
            resposta_texto = (
                "Percebo que voce pode estar lidando com uma situacao delicada. "
                "Sua seguranca e prioridade absoluta.\n\n"
                "*Se estiver em crise, ligue agora:*\n"
                "CVV (Centro de Valorizacao da Vida): *188*\n"
                "SAMU: *192*\n"
                "Chat: https://www.cvv.org.br\n\n"
                f"Entre em contato tambem com *{nome_terapeuta}*"
            )
            if contato_terapeuta:
                resposta_texto += f": {contato_terapeuta}"
            resposta_texto += (
                "\n\nA alquimia cuida do campo, mas a seguranca clinica vem primeiro. "
                "Procure ajuda profissional imediata."
            )

        elif modo == ModoOperacao.FORA_ESCOPO:
            # Usa a mensagem de fora de escopo da Alquimia
            resposta_texto = MENSAGEM_FORA_ESCOPO

        elif modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            # Modos principais — usar RAG com o modo detectado
            # CONSULTA usa top_k=10 para trazer mais contexto alquimico no diagnostico
            top_k_busca = 10 if modo == ModoOperacao.CONSULTA else 5
            contexto_chunks = await buscar_contexto(
                pergunta=texto_mensagem,
                terapeuta_id=terapeuta_id,
                top_k=top_k_busca,
            )

            # Buscar historico de conversa (essencial para CONSULTA multi-turno / anamnese)
            historico = _buscar_historico_conversa(
                terapeuta_id=terapeuta_id,
                paciente_numero=numero_paciente,
                limite=20,
            )

            # Carregar contexto personalizado de aprendizado continuo
            try:
                ctx_aprendizado = await carregar_contexto_terapeuta(terapeuta_id)
                ctx_formatado = formatar_contexto_personalizado(ctx_aprendizado)
            except Exception as e:
                logger.warning(f"Falha ao carregar contexto de aprendizado: {e}")
                ctx_formatado = None

            # Gerar resposta com RAG + historico + contexto personalizado
            resposta_texto = await gerar_resposta(
                pergunta=texto_mensagem,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
                historico_mensagens=historico if historico else None,
                contexto_personalizado=ctx_formatado,
            )

        else:
            # Modo nao reconhecido — fallback para RAG com modo PESQUISA
            logger.warning(f"Modo nao reconhecido: {modo} — tratando como PESQUISA via RAG")
            contexto_chunks = await buscar_contexto(
                pergunta=texto_mensagem,
                terapeuta_id=terapeuta_id,
            )
            resposta_texto = await gerar_resposta(
                pergunta=texto_mensagem,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
            )

        # 7. Humanizar resposta antes de enviar (regras UX do Lucas)
        if resposta_texto:
            resposta_texto = humanizar_resposta(resposta_texto)

            await evolution.enviar_mensagem(
                instance=instance_name,
                numero=numero_paciente,
                texto=resposta_texto,
            )
            logger.info(f"Resposta enviada para {numero_paciente}")

        # 8. Salvar conversa no banco (registra tanto o modo quanto a intencao LLM)
        _salvar_conversa(
            terapeuta_id=terapeuta_id,
            paciente_numero=numero_paciente,
            mensagem_paciente=texto_mensagem,
            resposta_agente=resposta_texto,
            intencao=f"{modo.value}|{intencao.value if hasattr(intencao, 'value') else str(intencao)}",
        )

        # 9. Analise de aprendizado em background (nao bloqueia o fluxo)
        # Apenas para modos principais que geram resposta via RAG
        if modo in (ModoOperacao.CONSULTA, ModoOperacao.CRIACAO_CONTEUDO, ModoOperacao.PESQUISA):
            try:
                asyncio.create_task(
                    analisar_conversa(
                        terapeuta_id=terapeuta_id,
                        mensagem=texto_mensagem,
                        resposta=resposta_texto,
                        modo=modo.value,
                    )
                )
                logger.info(f"Analise de aprendizado disparada em background para terapeuta {terapeuta_id}")
            except Exception as e:
                # Aprendizado nunca deve quebrar o fluxo principal
                logger.warning(f"Falha ao disparar analise de aprendizado: {e}")

    except Exception as e:
        logger.error(f"Erro ao processar mensagem do webhook: {e}", exc_info=True)


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

    # Validar se é uma mensagem que deve ser processada
    if not eh_mensagem_valida(body):
        evento = body.get("event", "desconhecido")
        logger.debug(f"Evento ignorado ou mensagem inválida: {evento}")
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
