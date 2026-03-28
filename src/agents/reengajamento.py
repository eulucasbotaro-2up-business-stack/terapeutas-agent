"""
Agente de Reengajamento — recupera clientes suspensos ou com assinatura expirada.

Fluxo:
  D+0 → D+2 → D+5 (com desconto 15%) → D+7 (desconto 20%) → D+14 → D+30 (abandona)

Acionado diariamente pelo automation_router via POST /automation/reengajamento/run
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.core.supabase_client import get_supabase
from src.agents.whatsapp_sender import enviar_mensagem, _registrar_log

logger = logging.getLogger(__name__)

# Etapas com dias após suspensão
_ETAPAS = [
    {"etapa": "d0",  "dias_apos": 0,  "desconto": 0},
    {"etapa": "d2",  "dias_apos": 2,  "desconto": 0},
    {"etapa": "d5",  "dias_apos": 5,  "desconto": 15},
    {"etapa": "d7",  "dias_apos": 7,  "desconto": 20},
    {"etapa": "d14", "dias_apos": 14, "desconto": 0},
    {"etapa": "d30", "dias_apos": 30, "desconto": 0},
]

_LINK_BASE = "https://terapeutas-agent.railway.app/reativar"


def _link_reativacao(plano: str, desconto: int = 0) -> str:
    """Retorna link de reativação, com parâmetro de desconto se houver."""
    planos = {
        "praticante": "https://www.asaas.com/c/praticante",
        "terapeuta":  "https://www.asaas.com/c/terapeuta",
        "alquimista": "https://www.asaas.com/c/alquimista",
    }
    base = planos.get(plano, _LINK_BASE)
    if desconto:
        base += f"?desconto={desconto}"
    return base


def _montar_mensagem(
    etapa: str,
    nome: str,
    plano: str,
    desconto: int = 0,
) -> str:
    """Monta mensagem da etapa de reengajamento."""
    link = _link_reativacao(plano, desconto)
    nome_fmt = nome.split()[0] if nome else "Terapeuta"
    plano_fmt = plano.capitalize()

    msgs = {
        "d0": (
            f"Oi {nome_fmt}, seu acesso ao Assistente Alquímico foi pausado hoje.\n"
            f"Para reativar e continuar com seus pacientes: → {link}\n"
            f"Se precisar de ajuda com o pagamento, responda aqui."
        ),
        "d2": (
            f"{nome_fmt}, notei que seu acesso ainda está pausado.\n"
            f"Seus pacientes ficam sem a orientação alquímica quando isso acontece.\n"
            f"Posso ajudar com algo? Para reativar: → {link}"
        ),
        "d5": (
            f"{nome_fmt}, preparamos algo especial para você voltar.\n"
            f"Reative seu plano {plano_fmt} com {desconto}% de desconto no primeiro mês:\n"
            f"→ {link}\n"
            f"(Oferta válida por 48 horas)"
        ),
        "d7": (
            f"Última mensagem antes de encerrar seu acesso, {nome_fmt}.\n"
            f"Se quiser voltar, ainda dá tempo — {desconto}% de desconto:\n"
            f"→ {link}\n"
            f"Válido por 24h. Se decidiu seguir em frente, obrigado pelo tempo com a gente."
        ),
        "d14": (
            f"Oi {nome_fmt}! Passaram 2 semanas.\n"
            f"O Assistente evoluiu — nova biblioteca do Joel, protocolos avançados "
            f"e leitura quântica de casais disponíveis.\n"
            f"Se quiser voltar: → {link}"
        ),
        "d30": (
            f"{nome_fmt}, é minha última tentativa de contato.\n"
            f"Se um dia decidir voltar, é só acessar: → {link}\n"
            f"O plano Praticante começa em R$97/mês. Sucesso na sua prática! 🌿"
        ),
    }
    return msgs.get(etapa, f"Reative seu acesso: {link}")


def _etapa_para_hoje(data_suspensao: datetime, agora: datetime) -> Optional[str]:
    """Retorna qual etapa deve ser executada hoje com base nos dias desde a suspensão."""
    dias = (agora.date() - data_suspensao.date()).days

    etapa_correta = None
    for e in _ETAPAS:
        if dias >= e["dias_apos"]:
            etapa_correta = e["etapa"]
        else:
            break

    return etapa_correta


async def executar_campanha_reengajamento() -> dict:
    """
    Ponto de entrada principal — chamado diariamente pelo cron.

    1. Buscar assinaturas suspensas/expiradas há ≤ 90 dias
    2. Para cada uma: verificar/criar campanha, calcular etapa, enviar se necessário
    3. Retornar resumo das ações

    Returns:
        Dict com counts de ações
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc)

    stats = {
        "campanhas_iniciadas": 0,
        "mensagens_enviadas":  0,
        "reconvertidos":       0,
        "abandonados":         0,
        "erros":               0,
        "verificados":         0,
    }

    # 1. Buscar suspensas/expiradas recentemente (≤ 90 dias)
    limite_90d = (agora - timedelta(days=90)).isoformat()
    resultado = (
        supabase.table("codigos_liberacao")
        .select("id, terapeuta_id, numero_ativo, codigo, data_expiracao, status_assinatura, updated_at")
        .in_("status_assinatura", ["suspenso_pagamento", "expirado"])
        .not_.is_("numero_ativo", "null")
        .gte("updated_at", limite_90d)
        .execute()
    )

    assinaturas = resultado.data or []
    stats["verificados"] = len(assinaturas)
    logger.info(f"[REENGAJAMENTO] {len(assinaturas)} assinatura(s) para reengajar")

    for row in assinaturas:
        try:
            codigo_id  = row["id"]
            numero     = row["numero_ativo"]
            motivo     = row["status_assinatura"].upper()

            # Data de suspensão = updated_at do código
            data_susp_str = row.get("updated_at") or agora.isoformat()
            data_susp = datetime.fromisoformat(data_susp_str.replace("Z", "+00:00"))

            # Buscar nome do usuário
            perfil = (
                supabase.table("perfil_usuario")
                .select("nome_usuario")
                .eq("numero_telefone", numero)
                .limit(1)
                .execute()
            )
            nome = (perfil.data[0].get("nome_usuario") or "Terapeuta") if perfil.data else "Terapeuta"

            estado = (
                supabase.table("chat_estado")
                .select("plano")
                .eq("numero_telefone", numero)
                .limit(1)
                .execute()
            )
            plano = (estado.data[0].get("plano") or "terapeuta") if estado.data else "terapeuta"

            # 2. Verificar se campanha existe
            campanha = (
                supabase.table("campanhas_reengajamento")
                .select("id, etapa_atual, status, ultima_mensagem_em, proxima_mensagem_em, oferta_desconto_enviada")
                .eq("codigo_id", codigo_id)
                .eq("status", "ativa")
                .limit(1)
                .execute()
            )

            if not campanha.data:
                # Criar nova campanha
                nova = supabase.table("campanhas_reengajamento").insert({
                    "codigo_id":           codigo_id,
                    "terapeuta_id":        row["terapeuta_id"],
                    "numero_telefone":     numero,
                    "nome_usuario":        nome,
                    "plano_anterior":      plano,
                    "motivo_suspensao":    motivo,
                    "data_suspensao":      data_susp.date().isoformat(),
                    "etapa_atual":         "d0",
                    "proxima_mensagem_em": agora.isoformat(),
                }).execute()

                campanha_id = nova.data[0]["id"] if nova.data else None
                stats["campanhas_iniciadas"] += 1
                etapa_atual = "d0"
            else:
                camp = campanha.data[0]
                campanha_id = camp["id"]
                etapa_atual = camp["etapa_atual"]

                # Verificar se já reconvertido
                cod_atual = (
                    supabase.table("codigos_liberacao")
                    .select("status_assinatura")
                    .eq("id", codigo_id)
                    .limit(1)
                    .execute()
                )
                if cod_atual.data and cod_atual.data[0].get("status_assinatura") == "ativo":
                    supabase.table("campanhas_reengajamento").update(
                        {"status": "reconvertida"}
                    ).eq("id", campanha_id).execute()
                    stats["reconvertidos"] += 1

                    # Mensagem de boas-vindas de volta
                    await enviar_mensagem(
                        numero,
                        f"✅ Bem-vindo de volta, {nome.split()[0]}! "
                        f"Seu acesso ao Assistente Alquímico está reativado. "
                        f"A metodologia do Joel está aqui quando precisar. 🌟"
                    )
                    continue

                # Verificar se é hora de próxima mensagem
                proxima_str = camp.get("proxima_mensagem_em")
                if proxima_str:
                    proxima = datetime.fromisoformat(proxima_str.replace("Z", "+00:00"))
                    if agora < proxima:
                        continue

                # Avançar etapa
                nova_etapa = _etapa_para_hoje(data_susp, agora)
                if nova_etapa and nova_etapa > etapa_atual:
                    etapa_atual = nova_etapa
                elif nova_etapa == etapa_atual:
                    pass  # reenvia mesma etapa se ainda no mesmo dia
                else:
                    continue  # nada a fazer

            # D+30 sem resposta → abandonar
            dias_decorridos = (agora.date() - data_susp.date()).days
            if dias_decorridos > 30 and etapa_atual == "d30":
                supabase.table("campanhas_reengajamento").update(
                    {"status": "abandonada"}
                ).eq("id", campanha_id).execute()
                stats["abandonados"] += 1
                continue

            # Determinar desconto da etapa
            desconto = 0
            for e in _ETAPAS:
                if e["etapa"] == etapa_atual:
                    desconto = e["desconto"]
                    break

            # 3. Enviar mensagem
            mensagem = _montar_mensagem(etapa_atual, nome, plano, desconto)
            ok = await enviar_mensagem(numero, mensagem)

            status_log = "enviado" if ok else "falhou"
            _registrar_log(
                tipo_campanha="reengajamento",
                numero=numero,
                etapa=etapa_atual,
                mensagem=mensagem,
                status=status_log,
                campanha_id=campanha_id,
            )

            if ok:
                # Calcular próximo envio (próxima etapa)
                proxima_etapa_dias = None
                for i, e in enumerate(_ETAPAS):
                    if e["etapa"] == etapa_atual and i < len(_ETAPAS) - 1:
                        proxima_etapa_dias = _ETAPAS[i + 1]["dias_apos"]
                        break

                if proxima_etapa_dias is not None:
                    proxima_dt = data_susp + timedelta(days=proxima_etapa_dias)
                else:
                    proxima_dt = agora + timedelta(days=365)  # fim da sequência

                supabase.table("campanhas_reengajamento").update({
                    "etapa_atual":              etapa_atual,
                    "ultima_mensagem_em":       agora.isoformat(),
                    "proxima_mensagem_em":      proxima_dt.isoformat(),
                    "oferta_desconto_enviada":  desconto > 0,
                    "desconto_oferecido":       desconto,
                }).eq("id", campanha_id).execute()

                stats["mensagens_enviadas"] += 1
                logger.info(
                    f"[REENGAJAMENTO] {nome} ({numero}) — etapa {etapa_atual}, "
                    f"desconto {desconto}%"
                )
            else:
                stats["erros"] += 1

        except Exception as e:
            logger.error(f"[REENGAJAMENTO] Erro ao processar {row.get('numero_ativo')}: {e}")
            stats["erros"] += 1

    logger.info(f"[REENGAJAMENTO] Resumo: {stats}")
    return stats
