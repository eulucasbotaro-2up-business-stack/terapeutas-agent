"""
Agente de Renovação — campanhas automáticas para clientes perto de vencer.

Fluxo:
  D-15 → D-10 → D-7 → D-3 → D-1 → D-0 (suspender + acionar reengajamento)

Acionado diariamente pelo automation_router via POST /automation/renovacao/run
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.core.supabase_client import get_supabase
from src.agents.whatsapp_sender import enviar_mensagem, _registrar_log

logger = logging.getLogger(__name__)

# Etapas da campanha com a antecedência em dias
_ETAPAS: list[dict] = [
    {"etapa": "d15", "dias_antes": 15},
    {"etapa": "d10", "dias_antes": 10},
    {"etapa": "d7",  "dias_antes": 7},
    {"etapa": "d3",  "dias_antes": 3},
    {"etapa": "d1",  "dias_antes": 1},
]

# Link base de renovação — será customizado por plano
_LINK_RENOVACAO_BASE = "https://terapeutas-agent.railway.app/renovar"


def _link_renovacao(plano: str) -> str:
    """Retorna link de renovação específico do plano (Asaas)."""
    links = {
        "praticante": "https://www.asaas.com/c/praticante",  # substituir por link real
        "terapeuta":  "https://www.asaas.com/c/terapeuta",
        "alquimista": "https://www.asaas.com/c/alquimista",
    }
    return links.get(plano, _LINK_RENOVACAO_BASE)


def _montar_mensagem(etapa: str, nome: str, data_expiracao: str, plano: str) -> str:
    """Monta o texto da mensagem de acordo com a etapa."""
    link = _link_renovacao(plano)
    nome_fmt = nome.split()[0] if nome else "Terapeuta"
    plano_fmt = plano.capitalize()

    mensagens = {
        "d15": (
            f"Oi {nome_fmt}! Seu plano {plano_fmt} vence em 15 dias (dia {data_expiracao}).\n"
            f"Para manter o assistente disponível para seus pacientes sem interrupção, renove aqui:\n"
            f"→ {link}"
        ),
        "d10": (
            f"Lembrete: seu acesso ao Assistente Alquímico vence em 10 dias.\n"
            f"Seus pacientes ficam sem as respostas automáticas quando isso acontece.\n"
            f"Renove com 1 clique: → {link}"
        ),
        "d7": (
            f"{nome_fmt}, faltam 7 dias para o vencimento do seu plano.\n"
            f"Você pode renovar o plano atual ou fazer upgrade:\n"
            f"🌱 Praticante — R$97/mês\n"
            f"⭐ Terapeuta — R$197/mês (mais popular)\n"
            f"✨ Alquimista — R$597/mês\n\n"
            f"→ Renovar agora: {link}"
        ),
        "d3": (
            f"⚠️ Faltam apenas 3 dias para o vencimento do seu plano, {nome_fmt}.\n"
            f"Após o vencimento, o assistente para de responder seus pacientes.\n"
            f"Para continuar sem interrupção: → {link}"
        ),
        "d1": (
            f"{nome_fmt}, amanhã é o último dia do seu plano ativo.\n"
            f"Renove agora para não interromper o atendimento: → {link}\n\n"
            f"Se tiver qualquer dificuldade com o pagamento, responda aqui que te ajudo."
        ),
    }
    return mensagens.get(etapa, f"Seu plano vence em breve. Renove: {link}")


def _etapa_para_proximo_envio(etapa_atual: str, dias_restantes: int) -> Optional[str]:
    """Determina qual é a próxima etapa a enviar baseado nos dias restantes."""
    for e in _ETAPAS:
        if dias_restantes <= e["dias_antes"] and e["etapa"] > etapa_atual:
            return e["etapa"]
    return None


def _calcular_proxima_etapa(dias_restantes: int) -> Optional[str]:
    """Determina a etapa correta para os dias restantes."""
    for e in reversed(_ETAPAS):
        if dias_restantes <= e["dias_antes"]:
            return e["etapa"]
    return None


async def executar_campanha_renovacao() -> dict:
    """
    Ponto de entrada principal — chamado diariamente pelo cron.

    Fluxo:
    1. Buscar assinaturas que vencem em ≤ 15 dias
    2. Para cada uma: verificar/criar campanha, calcular etapa, enviar se necessário
    3. Retornar resumo das ações tomadas

    Returns:
        Dict com counts de ações (campanhas_iniciadas, mensagens_enviadas, erros)
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc)

    stats = {
        "campanhas_iniciadas": 0,
        "mensagens_enviadas": 0,
        "ja_renovadas": 0,
        "erros": 0,
        "verificados": 0,
    }

    # 1. Buscar assinaturas ativas expirando em ≤ 15 dias
    expiracao_limite = (agora + timedelta(days=15)).isoformat()
    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, terapeuta_id, numero_ativo, codigo, data_expiracao, status_assinatura")
        .eq("status_assinatura", "ativo")
        .not_.is_("numero_ativo", "null")
        .not_.is_("data_expiracao", "null")
        .lte("data_expiracao", expiracao_limite)
        .gt("data_expiracao", agora.isoformat())
        .execute()
    )

    assinaturas = resultado.data or []
    stats["verificados"] = len(assinaturas)
    logger.info(f"[RENOVAÇÃO] {len(assinaturas)} assinatura(s) expirando em ≤ 15 dias")

    for row in assinaturas:
        try:
            codigo_id   = row["id"]
            numero      = row["numero_ativo"]
            expiracao   = datetime.fromisoformat(row["data_expiracao"].replace("Z", "+00:00"))
            dias_rest   = max(0, (expiracao.date() - agora.date()).days)

            # 2. Buscar perfil do usuário para nome
            perfil = (
                supabase.table("perfil_usuario")
                .select("nome_usuario")
                .eq("numero_telefone", numero)
                .limit(1)
                .execute()
            )
            nome = (perfil.data[0].get("nome_usuario") or "Terapeuta") if perfil.data else "Terapeuta"

            # Buscar plano (do chat_estado ou default)
            estado = (
                supabase.table("chat_estado")
                .select("plano")
                .eq("numero_telefone", numero)
                .limit(1)
                .execute()
            )
            plano = (estado.data[0].get("plano") or "terapeuta") if estado.data else "terapeuta"

            data_exp_fmt = expiracao.strftime("%d/%m/%Y")

            # 3. Verificar se já existe campanha
            campanha = (
                supabase.table("campanhas_renovacao")
                .select("id, etapa_atual, status, ultima_mensagem_em, proxima_mensagem_em")
                .eq("codigo_id", codigo_id)
                .eq("status", "ativa")
                .limit(1)
                .execute()
            )

            if not campanha.data:
                # Criar nova campanha
                etapa = _calcular_proxima_etapa(dias_rest) or "d15"
                nova = supabase.table("campanhas_renovacao").insert({
                    "codigo_id":           codigo_id,
                    "terapeuta_id":        row["terapeuta_id"],
                    "numero_telefone":     numero,
                    "nome_usuario":        nome,
                    "plano":               plano,
                    "data_expiracao":      expiracao.date().isoformat(),
                    "dias_para_vencer":    dias_rest,
                    "etapa_atual":         etapa,
                    "proxima_mensagem_em": agora.isoformat(),
                    "link_renovacao":      _link_renovacao(plano),
                }).execute()

                campanha_id = nova.data[0]["id"] if nova.data else None
                stats["campanhas_iniciadas"] += 1
                etapa_atual = etapa
            else:
                camp = campanha.data[0]
                campanha_id = camp["id"]
                etapa_atual = camp["etapa_atual"]

                # Verificar se já está renovada
                cod_atual = (
                    supabase.table("codigos_liberacao")
                    .select("status_assinatura, data_expiracao")
                    .eq("id", codigo_id)
                    .limit(1)
                    .execute()
                )
                if cod_atual.data:
                    st = cod_atual.data[0].get("status_assinatura")
                    nova_exp = cod_atual.data[0].get("data_expiracao")
                    if nova_exp and nova_exp > expiracao_limite:
                        # Renovado! Marcar campanha como concluída
                        supabase.table("campanhas_renovacao").update(
                            {"status": "renovada"}
                        ).eq("id", campanha_id).execute()
                        stats["ja_renovadas"] += 1
                        continue

                # Verificar se é hora de enviar próxima mensagem
                proxima_str = camp.get("proxima_mensagem_em")
                if proxima_str:
                    proxima = datetime.fromisoformat(proxima_str.replace("Z", "+00:00"))
                    if agora < proxima:
                        continue  # ainda não é hora

                # Calcular etapa correta para hoje
                nova_etapa = _calcular_proxima_etapa(dias_rest)
                if nova_etapa and nova_etapa != etapa_atual:
                    etapa_atual = nova_etapa

            # 4. Enviar mensagem
            mensagem = _montar_mensagem(etapa_atual, nome, data_exp_fmt, plano)
            ok = await enviar_mensagem(numero, mensagem)

            status_log = "enviado" if ok else "falhou"
            _registrar_log(
                tipo_campanha="renovacao",
                numero=numero,
                etapa=etapa_atual,
                mensagem=mensagem,
                status=status_log,
                campanha_id=campanha_id,
            )

            if ok:
                # Calcular próximo envio
                proxima_etapa_idx = None
                for i, e in enumerate(_ETAPAS):
                    if e["etapa"] == etapa_atual and i < len(_ETAPAS) - 1:
                        proxima_etapa_idx = i + 1
                        break

                proxima_mensagem_em = agora + timedelta(days=3)  # default
                if proxima_etapa_idx is not None:
                    dias_prox = _ETAPAS[proxima_etapa_idx]["dias_antes"]
                    proxima_mensagem_em = expiracao - timedelta(days=dias_prox)

                supabase.table("campanhas_renovacao").update({
                    "etapa_atual":         etapa_atual,
                    "ultima_mensagem_em":  agora.isoformat(),
                    "proxima_mensagem_em": proxima_mensagem_em.isoformat(),
                    "mensagens_enviadas":  supabase.rpc("increment", {"x": 1}),
                }).eq("id", campanha_id).execute()

                stats["mensagens_enviadas"] += 1
                logger.info(
                    f"[RENOVAÇÃO] {nome} ({numero}) — etapa {etapa_atual}, "
                    f"{dias_rest} dias restantes"
                )
            else:
                stats["erros"] += 1

        except Exception as e:
            logger.error(f"[RENOVAÇÃO] Erro ao processar {row.get('numero_ativo')}: {e}")
            stats["erros"] += 1

    # 5. Verificar assinaturas expiradas hoje e acionar reengajamento
    await _processar_vencidos_hoje(supabase, agora, stats)

    logger.info(f"[RENOVAÇÃO] Resumo: {stats}")
    return stats


async def _processar_vencidos_hoje(supabase, agora: datetime, stats: dict) -> None:
    """Processa assinaturas que venceram hoje — bloqueia e inicia reengajamento."""
    from src.core.assinatura import bloquear_chat_por_codigo

    # Buscar expirados ainda com status 'ativo'
    vencidos = (
        supabase.table("codigos_liberacao")
        .select("id, terapeuta_id, numero_ativo, codigo")
        .eq("status_assinatura", "ativo")
        .lt("data_expiracao", agora.isoformat())
        .not_.is_("numero_ativo", "null")
        .execute()
    )

    for row in (vencidos.data or []):
        try:
            # Marcar como expirado
            supabase.table("codigos_liberacao").update({
                "status_assinatura": "expirado",
            }).eq("id", row["id"]).execute()

            # Bloquear chat
            bloquear_chat_por_codigo(
                terapeuta_id=row["terapeuta_id"],
                numero_telefone=row["numero_ativo"],
                motivo="ASSINATURA_EXPIRADA",
            )

            # Marcar campanha de renovação como suspensa
            supabase.table("campanhas_renovacao").update({
                "status": "suspensa",
            }).eq("codigo_id", row["id"]).eq("status", "ativa").execute()

            logger.warning(
                f"[RENOVAÇÃO] Assinatura expirada bloqueada: {row['numero_ativo']}"
            )

        except Exception as e:
            logger.error(f"[RENOVAÇÃO] Erro ao bloquear vencido {row.get('numero_ativo')}: {e}")
