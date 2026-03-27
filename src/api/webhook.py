"""
Rota de webhook para receber mensagens do WhatsApp via Evolution API e Meta Cloud API.
Processa a mensagem com RAG e responde automaticamente ao paciente.
"""

import asyncio
import logging
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
from src.core.estado import (
    obter_ou_criar_estado,
    validar_codigo,
    liberar_acesso,
    registrar_nome_usuario,
    detectar_profanidade,
    registrar_violacao,
    gerar_msg_bloqueio,
    gerar_msg_ja_bloqueado,
    gerar_saudacao_ativo,
    gerar_msg_boas_vindas_nome,
    MSGS_ONBOARDING,
    MSG_CODIGO_INVALIDO,
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
    detectar_mudanca_assunto,
    gerar_msg_confirma_mudanca,
    gerar_msg_retomada_topico,
    salvar_confirmacao_topico,
    limpar_confirmacao_topico,
    eh_confirmacao,
    eh_negacao,
)
from src.rag.retriever import buscar_contexto
from src.rag.generator import gerar_resposta, classificar_intencao
from src.rag.aprendizado import (
    analisar_conversa,
    carregar_contexto_terapeuta,
    formatar_contexto_personalizado,
)
from src.whatsapp.evolution import EvolutionClient
from src.whatsapp.meta_cloud import MetaCloudClient
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

async def _enviar_sequencia_evolution(
    msgs: list[str],
    evolution: "EvolutionClient",
    instance: str,
    numero: str,
    delay: float = 3.0,
) -> None:
    """
    Envia uma lista de mensagens com rate limiting (Evolution API).
    Delay padrão: 3s — acima do mínimo oficial da Meta (6s por usuário),
    conservador o suficiente para respostas sequenciais sem risco de ban.
    """
    for i, msg in enumerate(msgs):
        await aguardar_antes_de_enviar(numero, sequencial=True)
        if i > 0:
            await asyncio.sleep(delay)
        await evolution.enviar_mensagem(instance=instance, numero=numero, texto=msg)


async def _processar_mensagem(payload: dict) -> None:
    """
    Processa a mensagem recebida via Evolution API em background.

    Fluxo com máquina de estados:
      1. Extrair dados → 2. Validar tipo → 3. Buscar terapeuta →
      4. Verificar estado (PENDENTE/ATIVO/BLOQUEADO) →
      5. Se ATIVO: checar profanidade → 6. RAG pipeline → 7. Responder
    """
    try:
        settings = get_settings()

        # 1. Extrair número e texto
        numero_paciente, texto_mensagem = extrair_numero_mensagem(payload)
        instance_name = payload.get("instance", "")

        logger.info(f"Evolution: mensagem de {numero_paciente} na instância {instance_name}")

        # 2. Validar tipo de mensagem
        if not texto_mensagem or not texto_mensagem.strip():
            logger.info("Mensagem sem texto — ignorando")
            return

        evolution = EvolutionClient()

        if texto_mensagem == "[AUDIO_NAO_SUPORTADO]":
            await evolution.enviar_mensagem(
                instance=instance_name, numero=numero_paciente,
                texto=formatar_aviso_audio(),
            )
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
        estado, is_new = obter_ou_criar_estado(terapeuta_id, numero_paciente)

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
                _salvar_conversa(
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
                if validar_codigo(terapeuta_id, numero_paciente, texto_mensagem):
                    liberar_acesso(terapeuta_id, numero_paciente, texto_mensagem)
                    # Ativar assinatura: define data_expiracao com base nos meses comprados
                    ativar_acesso_com_codigo(terapeuta_id, texto_mensagem, numero_paciente)
                    _salvar_conversa(
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
                    _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=MSG_CODIGO_INVALIDO,
                        intencao="CODIGO_INVALIDO",
                    )
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente,
                        texto=MSG_CODIGO_INVALIDO,
                    )
            return

        # ── ATIVO ──────────────────────────────────────────────────────────────

        # 5a. Coletar nome se ainda não temos
        if estado.aguardando_nome:
            nome = registrar_nome_usuario(terapeuta_id, numero_paciente, texto_mensagem)
            msg_nome = gerar_msg_boas_vindas_nome(nome)
            await evolution.enviar_mensagem(
                instance=instance_name, numero=numero_paciente, texto=msg_nome,
            )
            _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=msg_nome,
                intencao="NOME_REGISTRADO",
            )
            return

        # 5b. Moderação: detectar profanidade ANTES do RAG
        if detectar_profanidade(texto_mensagem):
            violacoes = registrar_violacao(terapeuta_id, numero_paciente)
            aviso = MSG_AVISO_1 if violacoes == 1 else (
                MSG_AVISO_2 if violacoes == 2 else gerar_msg_bloqueio(settings.CONTATO_ADMIN)
            )
            await evolution.enviar_mensagem(
                instance=instance_name, numero=numero_paciente, texto=aviso,
            )
            _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=aviso,
                intencao=f"VIOLACAO_{violacoes}",
            )
            return

        # 6. Carregar memória e histórico (sequencial — Supabase client não é thread-safe)
        memoria = await carregar_memoria_completa(terapeuta_id, numero_paciente)
        historico = _buscar_historico_conversa(terapeuta_id, numero_paciente, 20)

        # Formatar memória para injeção no prompt
        memoria_fmt = formatar_memoria_para_prompt(memoria, estado.nome_usuario)

        # 7. Tratar confirmação de mudança de assunto (se pendente)
        if estado.aguardando_confirmacao_topico:
            topico_ant = estado.topico_anterior or "assunto anterior"
            msg_pendente = estado.mensagem_pendente_topico or texto_mensagem

            if eh_confirmacao(texto_mensagem):
                # Usuário confirmou a mudança: processar a mensagem que disparou
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                texto_para_processar = msg_pendente
                logger.info(f"Mudança de assunto CONFIRMADA para {numero_paciente}")
            elif eh_negacao(texto_mensagem):
                # Usuário quer continuar o assunto anterior
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                retomada = gerar_msg_retomada_topico(topico_ant, estado.nome_usuario)
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente, texto=retomada,
                )
                _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=retomada,
                    intencao="RETOMADA_TOPICO",
                )
                asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
                return
            else:
                # Usuário enviou outra coisa — limpar e processar normalmente
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                texto_para_processar = texto_mensagem
        else:
            texto_para_processar = texto_mensagem

        # 8. Detectar modo e classificar intenção
        modo = detectar_modo(texto_para_processar)
        logger.info(f"Modo detectado: {modo.value}")
        intencao = await classificar_intencao(texto_para_processar)

        resposta_texto: str | list[str] = ""

        # 9. Saudação quando ATIVO
        if modo == ModoOperacao.SAUDACAO:
            # Se nova sessão E tem histórico: retomar o que foi discutido
            if memoria.get("is_nova_sessao") and memoria.get("resumos_sessoes"):
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
                    resposta_texto = gerar_saudacao_ativo(estado.nome_usuario)
            else:
                resposta_texto = gerar_saudacao_ativo(estado.nome_usuario)
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
            # 9a. Detectar mudança de assunto antes de responder
            if (
                not estado.aguardando_confirmacao_topico
                and historico
                and len(historico) >= 6  # mínimo 3 trocas
            ):
                mudou, topico_ant = detectar_mudanca_assunto(historico, texto_para_processar)
                if mudou:
                    # Salvar estado + enviar confirmação (não processa RAG agora)
                    await salvar_confirmacao_topico(
                        terapeuta_id, numero_paciente, texto_para_processar, topico_ant
                    )
                    confirmacao = gerar_msg_confirma_mudanca(topico_ant, estado.nome_usuario)
                    await evolution.enviar_mensagem(
                        instance=instance_name, numero=numero_paciente, texto=confirmacao,
                    )
                    _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=confirmacao,
                        intencao="CONFIRMACAO_TOPICO",
                    )
                    asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
                    return

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

            resposta_texto = await gerar_resposta(
                pergunta=texto_para_processar,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
                historico_mensagens=historico if historico else None,
                contexto_personalizado=ctx_formatado,
                memoria_usuario=memoria_fmt,
            )
        else:
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id,
            )
            resposta_texto = await gerar_resposta(
                pergunta=texto_para_processar,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
                memoria_usuario=memoria_fmt,
            )

        # 10. Enviar resposta (com rate limiting anti-ban)
        if resposta_texto:
            if isinstance(resposta_texto, list):
                await _enviar_sequencia_evolution(
                    resposta_texto, evolution, instance_name, numero_paciente,
                )
            else:
                resposta_texto = humanizar_resposta(resposta_texto)
                await aguardar_antes_de_enviar(numero_paciente, sequencial=False)
                await evolution.enviar_mensagem(
                    instance=instance_name, numero=numero_paciente, texto=resposta_texto,
                )
            logger.info(f"Resposta enviada para {numero_paciente}")

        # 11. Salvar conversa
        resposta_salvar = " | ".join(resposta_texto) if isinstance(resposta_texto, list) else resposta_texto
        _salvar_conversa(
            terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
            mensagem_paciente=texto_mensagem, resposta_agente=resposta_salvar,
            intencao=f"{modo.value}|{intencao.value if hasattr(intencao, 'value') else str(intencao)}",
        )

        # 12. Background: timestamp + perfil + aprendizado
        asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
        asyncio.create_task(
            atualizar_perfil_apos_interacao(
                terapeuta_id, numero_paciente, estado.nome_usuario, texto_mensagem, modo.value
            )
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

    except Exception as e:
        logger.error(f"Erro ao processar mensagem Evolution: {e}", exc_info=True)


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


def _extrair_mensagem_meta(payload: dict) -> tuple[str, str, str, str]:
    """
    Extrai dados da mensagem do payload da Meta WhatsApp Cloud API.

    Args:
        payload: Payload JSON recebido no webhook da Meta.

    Returns:
        Tupla (phone_number_id, numero_remetente, texto_mensagem, message_id):
        - phone_number_id: ID do número de telefone do business
        - numero_remetente: Número do paciente que enviou a mensagem
        - texto_mensagem: Conteúdo da mensagem em texto
        - message_id: ID da mensagem (wamid.xxx) para marcar como lida
    """
    try:
        entry = payload.get("entry", [])
        if not entry:
            return "", "", "", ""

        changes = entry[0].get("changes", [])
        if not changes:
            return "", "", "", ""

        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id", "")

        messages = value.get("messages", [])
        if not messages:
            return phone_number_id, "", "", ""

        msg = messages[0]
        numero_remetente = msg.get("from", "")
        message_id = msg.get("id", "")
        msg_type = msg.get("type", "")

        # Extrair texto de acordo com o tipo de mensagem
        texto = ""
        if msg_type == "text":
            texto = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            texto = msg.get("image", {}).get("caption", "[IMAGEM_RECEBIDA]")
            if not texto:
                texto = "[IMAGEM_RECEBIDA]"
        elif msg_type == "audio":
            texto = "[AUDIO_NAO_SUPORTADO]"
        elif msg_type == "document":
            texto = msg.get("document", {}).get("caption", "[DOCUMENTO_RECEBIDO]")
            if not texto:
                texto = "[DOCUMENTO_RECEBIDO]"
        elif msg_type == "interactive":
            # Botões e listas interativas
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                texto = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                texto = interactive.get("list_reply", {}).get("title", "")
        else:
            texto = f"[TIPO_NAO_SUPORTADO:{msg_type}]"

        logger.info(
            "Mensagem Meta recebida de %s: '%s' (tipo=%s, id=%s)",
            numero_remetente,
            texto[:50] + "..." if len(texto) > 50 else texto,
            msg_type,
            message_id,
        )

        return phone_number_id, numero_remetente, texto, message_id

    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        logger.error("Erro ao extrair dados do payload Meta: %s", exc)
        return "", "", "", ""


# =============================================
# META CLOUD API — PROCESSAMENTO EM BACKGROUND
# =============================================

async def _enviar_sequencia_meta(
    msgs: list[str],
    meta_client: "MetaCloudClient",
    numero: str,
    delay: float = 3.0,
) -> None:
    """
    Envia uma lista de mensagens com rate limiting (Meta Cloud API).
    Delay padrão: 3s — conservador para respostas sequenciais sem risco de ban.
    O rate limiter global garante mínimo de 3s entre qualquer envio ao mesmo número.
    """
    for i, msg in enumerate(msgs):
        await aguardar_antes_de_enviar(numero, sequencial=True)
        if i > 0:
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
        phone_number_id, numero_paciente, texto_mensagem, message_id = _extrair_mensagem_meta(payload)

        if not numero_paciente or not texto_mensagem:
            logger.info("Payload Meta sem mensagem processável — ignorando")
            return

        logger.info(f"Meta: mensagem de {numero_paciente} (phone_number_id={phone_number_id})")

        # 2. Inicializar cliente Meta e marcar como lida
        meta_client = MetaCloudClient()
        if message_id:
            try:
                await meta_client.mark_as_read(message_id)
            except Exception as e:
                logger.warning(f"Falha ao marcar como lida: {e}")

        # 3. Validar tipo de mensagem
        if not texto_mensagem.strip():
            return

        if texto_mensagem == "[AUDIO_NAO_SUPORTADO]":
            await meta_client.send_text_message(
                phone_number=numero_paciente, message=formatar_aviso_audio(),
            )
            return

        if texto_mensagem.startswith("[") and texto_mensagem.endswith("]"):
            logger.info(f"Tipo não suportado: {texto_mensagem} — ignorando")
            return

        # 4. Buscar terapeuta
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
        estado, is_new = obter_ou_criar_estado(terapeuta_id, numero_paciente)

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
                _salvar_conversa(
                    terapeuta_id=terapeuta_id,
                    paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem,
                    resposta_agente=" | ".join(MSGS_ONBOARDING),
                    intencao="ONBOARDING",
                )
                await _enviar_sequencia_meta(MSGS_ONBOARDING, meta_client, numero_paciente)
            else:
                # Já recebeu boas-vindas: tentar como código de liberação
                if validar_codigo(terapeuta_id, numero_paciente, texto_mensagem):
                    liberar_acesso(terapeuta_id, numero_paciente, texto_mensagem)
                    # Ativar assinatura: define data_expiracao com base nos meses comprados
                    ativar_acesso_com_codigo(terapeuta_id, texto_mensagem, numero_paciente)
                    _salvar_conversa(
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
                    _salvar_conversa(
                        terapeuta_id=terapeuta_id,
                        paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem,
                        resposta_agente=MSG_CODIGO_INVALIDO,
                        intencao="CODIGO_INVALIDO",
                    )
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=MSG_CODIGO_INVALIDO,
                    )
            return

        # ── ATIVO ──────────────────────────────────────────────────────────────

        # 6a. Coletar nome se ainda não temos
        if estado.aguardando_nome:
            nome = registrar_nome_usuario(terapeuta_id, numero_paciente, texto_mensagem)
            msg_nome = gerar_msg_boas_vindas_nome(nome)
            await meta_client.send_text_message(
                phone_number=numero_paciente, message=msg_nome,
            )
            _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=msg_nome,
                intencao="NOME_REGISTRADO",
            )
            return

        # 6b. Moderação: detectar profanidade ANTES do RAG
        if detectar_profanidade(texto_mensagem):
            violacoes = registrar_violacao(terapeuta_id, numero_paciente)
            aviso = MSG_AVISO_1 if violacoes == 1 else (
                MSG_AVISO_2 if violacoes == 2 else gerar_msg_bloqueio(settings.CONTATO_ADMIN)
            )
            await meta_client.send_text_message(
                phone_number=numero_paciente, message=aviso,
            )
            _salvar_conversa(
                terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                mensagem_paciente=texto_mensagem, resposta_agente=aviso,
                intencao=f"VIOLACAO_{violacoes}",
            )
            return

        # 7. Carregar memória e histórico (sequencial — Supabase client não é thread-safe)
        memoria = await carregar_memoria_completa(terapeuta_id, numero_paciente)
        historico = _buscar_historico_conversa(terapeuta_id, numero_paciente, 20)

        # Formatar memória para injeção no prompt
        memoria_fmt = formatar_memoria_para_prompt(memoria, estado.nome_usuario)

        # 8. Tratar confirmação de mudança de assunto (se pendente)
        if estado.aguardando_confirmacao_topico:
            topico_ant = estado.topico_anterior or "assunto anterior"
            msg_pendente = estado.mensagem_pendente_topico or texto_mensagem

            if eh_confirmacao(texto_mensagem):
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                texto_para_processar = msg_pendente
                logger.info(f"Mudança de assunto CONFIRMADA para {numero_paciente} (Meta)")
            elif eh_negacao(texto_mensagem):
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                retomada = gerar_msg_retomada_topico(topico_ant, estado.nome_usuario)
                await meta_client.send_text_message(
                    phone_number=numero_paciente, message=retomada,
                )
                _salvar_conversa(
                    terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                    mensagem_paciente=texto_mensagem, resposta_agente=retomada,
                    intencao="RETOMADA_TOPICO",
                )
                asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
                return
            else:
                await limpar_confirmacao_topico(terapeuta_id, numero_paciente)
                texto_para_processar = texto_mensagem
        else:
            texto_para_processar = texto_mensagem

        # 9. Detectar modo e classificar intenção
        modo = detectar_modo(texto_para_processar)
        logger.info(f"Modo detectado (Meta): {modo.value}")
        intencao = await classificar_intencao(texto_para_processar)

        resposta_texto: str | list[str] = ""

        # 10. Saudação quando ATIVO
        if modo == ModoOperacao.SAUDACAO:
            if memoria.get("is_nova_sessao") and memoria.get("resumos_sessoes"):
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
                    resposta_texto = gerar_saudacao_ativo(estado.nome_usuario)
            else:
                resposta_texto = gerar_saudacao_ativo(estado.nome_usuario)
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
            # 10a. Detectar mudança de assunto antes de responder
            if (
                not estado.aguardando_confirmacao_topico
                and historico
                and len(historico) >= 6
            ):
                mudou, topico_ant = detectar_mudanca_assunto(historico, texto_para_processar)
                if mudou:
                    await salvar_confirmacao_topico(
                        terapeuta_id, numero_paciente, texto_para_processar, topico_ant
                    )
                    confirmacao = gerar_msg_confirma_mudanca(topico_ant, estado.nome_usuario)
                    await meta_client.send_text_message(
                        phone_number=numero_paciente, message=confirmacao,
                    )
                    _salvar_conversa(
                        terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
                        mensagem_paciente=texto_mensagem, resposta_agente=confirmacao,
                        intencao="CONFIRMACAO_TOPICO",
                    )
                    asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
                    return

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

            resposta_texto = await gerar_resposta(
                pergunta=texto_para_processar,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
                historico_mensagens=historico if historico else None,
                contexto_personalizado=ctx_formatado,
                memoria_usuario=memoria_fmt,
            )
        else:
            contexto_chunks = await buscar_contexto(
                pergunta=texto_para_processar, terapeuta_id=terapeuta_id,
            )
            resposta_texto = await gerar_resposta(
                pergunta=texto_para_processar,
                terapeuta_id=terapeuta_id,
                contexto_chunks=contexto_chunks,
                config_terapeuta=config_terapeuta,
                memoria_usuario=memoria_fmt,
            )

        # 11. Enviar resposta (com rate limiting anti-ban)
        if resposta_texto:
            if isinstance(resposta_texto, list):
                await _enviar_sequencia_meta(resposta_texto, meta_client, numero_paciente)
            else:
                resposta_texto = humanizar_resposta(resposta_texto)
                await aguardar_antes_de_enviar(numero_paciente, sequencial=False)
                await meta_client.send_text_message(
                    phone_number=numero_paciente, message=resposta_texto,
                )
            logger.info(f"Resposta enviada para {numero_paciente} via Meta")

        # 12. Salvar conversa
        resposta_salvar = " | ".join(resposta_texto) if isinstance(resposta_texto, list) else resposta_texto
        _salvar_conversa(
            terapeuta_id=terapeuta_id, paciente_numero=numero_paciente,
            mensagem_paciente=texto_mensagem, resposta_agente=resposta_salvar,
            intencao=f"{modo.value}|{intencao.value if hasattr(intencao, 'value') else str(intencao)}",
        )

        # 13. Background: timestamp + perfil + aprendizado
        asyncio.create_task(atualizar_timestamp_mensagem(terapeuta_id, numero_paciente))
        asyncio.create_task(
            atualizar_perfil_apos_interacao(
                terapeuta_id, numero_paciente, estado.nome_usuario, texto_mensagem, modo.value
            )
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
        f"(recebido: {token[:10]}..., esperado: {settings.META_VERIFY_TOKEN[:10]}...)"
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
