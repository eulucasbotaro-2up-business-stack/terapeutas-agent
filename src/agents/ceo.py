"""
Agente CEO — orquestrador central do negócio.

Responsável por:
- Gerar relatório diário do negócio
- Calcular MRR, churn, projeções
- Identificar alertas e delegar para agentes especializados
- Supervisionar campanhas de renovação e reengajamento

Acionado diariamente via POST /automation/relatorio/diario
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Preços dos planos (R$)
_PRECOS_PLANO = {
    "praticante": 97,
    "terapeuta":  197,
    "alquimista": 597,
}

_TICKET_MEDIO_DEFAULT = 197  # Terapeuta é o plano principal


async def gerar_relatorio_diario() -> dict:
    """
    Gera relatório completo do estado do negócio.

    Returns:
        Dict com todas as métricas do negócio.
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc)

    # ─── 1. MRR ATUAL ──────────────────────────────────────────────
    ativos = (
        supabase.table("codigos_liberacao")
        .select("id, status_assinatura")
        .eq("status_assinatura", "ativo")
        .not_.is_("numero_ativo", "null")
        .execute()
    )
    total_ativos = len(ativos.data or [])

    # Tentar buscar por plano (se coluna existir)
    try:
        por_plano = (
            supabase.table("chat_estado")
            .select("plano")
            .eq("estado", "ATIVO")
            .execute()
        )
        contagem_planos: dict[str, int] = {}
        for r in (por_plano.data or []):
            p = r.get("plano") or "terapeuta"
            contagem_planos[p] = contagem_planos.get(p, 0) + 1
    except Exception:
        contagem_planos = {"terapeuta": total_ativos}

    mrr_atual = sum(
        contagem_planos.get(p, 0) * preco
        for p, preco in _PRECOS_PLANO.items()
    )
    if mrr_atual == 0 and total_ativos > 0:
        mrr_atual = total_ativos * _TICKET_MEDIO_DEFAULT

    # ─── 2. VARIAÇÕES DO MÊS ──────────────────────────────────────
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    novos_mes = (
        supabase.table("codigos_liberacao")
        .select("id")
        .eq("status_assinatura", "ativo")
        .gte("usado_em", inicio_mes.isoformat())
        .execute()
    )
    total_novos_mes = len(novos_mes.data or [])

    suspensoes_mes = (
        supabase.table("codigos_liberacao")
        .select("id")
        .in_("status_assinatura", ["suspenso_pagamento", "expirado", "cancelado"])
        .gte("updated_at", inicio_mes.isoformat())
        .execute()
    )
    total_churn_mes = len(suspensoes_mes.data or [])

    # ─── 3. ALERTAS ───────────────────────────────────────────────
    # Vencendo em ≤ 15 dias
    expiracao_15d = (agora + timedelta(days=15)).isoformat()
    vencendo = (
        supabase.table("codigos_liberacao")
        .select("id")
        .eq("status_assinatura", "ativo")
        .lte("data_expiracao", expiracao_15d)
        .gt("data_expiracao", agora.isoformat())
        .execute()
    )
    total_vencendo = len(vencendo.data or [])

    # Suspensas ativas (recuperáveis)
    suspensas = (
        supabase.table("codigos_liberacao")
        .select("id")
        .in_("status_assinatura", ["suspenso_pagamento", "expirado"])
        .not_.is_("numero_ativo", "null")
        .gte("updated_at", (agora - timedelta(days=90)).isoformat())
        .execute()
    )
    total_suspensas = len(suspensas.data or [])

    # Leads novos na landing
    leads = (
        supabase.table("leads_landing")
        .select("id")
        .eq("status", "novo")
        .execute()
    )
    total_leads_novos = len(leads.data or [])

    # ─── 4. CAMPANHAS ATIVAS ──────────────────────────────────────
    camps_renov = (
        supabase.table("campanhas_renovacao")
        .select("id")
        .eq("status", "ativa")
        .execute()
    )

    camps_reeng = (
        supabase.table("campanhas_reengajamento")
        .select("id")
        .eq("status", "ativa")
        .execute()
    )

    # ─── 5. PROJEÇÕES ─────────────────────────────────────────────
    dias_no_mes = 30
    dias_passados = agora.day
    dias_restantes = dias_no_mes - dias_passados

    taxa_crescimento_diaria = total_novos_mes / max(dias_passados, 1)
    mrr_projetado = mrr_atual + (taxa_crescimento_diaria * dias_restantes * _TICKET_MEDIO_DEFAULT)
    mrr_em_risco = total_vencendo * _TICKET_MEDIO_DEFAULT + total_suspensas * _TICKET_MEDIO_DEFAULT

    churn_rate = (total_churn_mes / max(total_ativos + total_churn_mes, 1)) * 100

    # ─── 6. MONTAGEM DO RELATÓRIO ─────────────────────────────────
    relatorio = {
        "data": agora.strftime("%d/%m/%Y %H:%M"),
        "mrr_atual": mrr_atual,
        "clientes_ativos": total_ativos,
        "distribuicao_planos": contagem_planos,
        "novos_mes": total_novos_mes,
        "churn_mes": total_churn_mes,
        "churn_rate_pct": round(churn_rate, 1),
        "mrr_projetado_fim_mes": int(mrr_projetado),
        "mrr_em_risco": mrr_em_risco,
        "alertas": {
            "vencendo_15_dias":     total_vencendo,
            "suspensas_recuperaveis": total_suspensas,
            "leads_novos":          total_leads_novos,
            "campanhas_renovacao_ativas": len(camps_renov.data or []),
            "campanhas_reengajamento_ativas": len(camps_reeng.data or []),
        },
        "acoes_recomendadas": _gerar_acoes(
            total_vencendo, total_suspensas, total_leads_novos, churn_rate
        ),
    }

    logger.info(
        f"[CEO] Relatório diário — MRR: R${mrr_atual} | "
        f"Ativos: {total_ativos} | Churn: {churn_rate:.1f}%"
    )

    return relatorio


def _gerar_acoes(
    vencendo: int,
    suspensas: int,
    leads: int,
    churn_rate: float,
) -> list[str]:
    """Gera lista de ações recomendadas com base nos alertas."""
    acoes = []

    if vencendo > 0:
        acoes.append(
            f"⚠️ {vencendo} assinatura(s) vencendo em ≤ 15 dias — "
            f"Agente Renovação acionado automaticamente"
        )
    if suspensas > 0:
        acoes.append(
            f"📉 {suspensas} assinatura(s) suspensa(s) recuperáveis — "
            f"Agente Reengajamento acionado automaticamente"
        )
    if leads > 0:
        acoes.append(
            f"🎯 {leads} lead(s) novo(s) na landing sem contato — "
            f"Agente Vendedor deve contatar em até 2h"
        )
    if churn_rate > 10:
        acoes.append(
            f"🚨 Churn {churn_rate:.1f}% acima do limite (10%) — "
            f"Revisão urgente do processo de CS"
        )
    if churn_rate > 5:
        acoes.append(
            f"⚠️ Churn {churn_rate:.1f}% acima da meta (5%) — "
            f"CS revisar motivos de saída"
        )
    if not acoes:
        acoes.append("✅ Tudo dentro dos limites normais. Manter monitoramento diário.")

    return acoes


def formatar_relatorio_texto(relatorio: dict) -> str:
    """Formata o relatório como texto para envio via WhatsApp ou console."""
    data     = relatorio["data"]
    mrr      = relatorio["mrr_atual"]
    ativos   = relatorio["clientes_ativos"]
    novos    = relatorio["novos_mes"]
    churn    = relatorio["churn_mes"]
    churn_p  = relatorio["churn_rate_pct"]
    projetado = relatorio["mrr_projetado_fim_mes"]
    em_risco  = relatorio["mrr_em_risco"]
    alertas  = relatorio["alertas"]
    acoes    = relatorio["acoes_recomendadas"]

    linhas = [
        f"📊 RELATÓRIO CEO — {data}",
        "",
        "💰 FINANCEIRO",
        f"  MRR atual:          R${mrr:,.0f}",
        f"  Clientes ativos:    {ativos}",
        f"  Novos este mês:     +{novos}",
        f"  Churn este mês:     -{churn} ({churn_p}%)",
        f"  Projeção fim mês:   R${projetado:,.0f}",
        f"  MRR em risco:       R${em_risco:,.0f}",
        "",
        "⚠️ ALERTAS",
        f"  Vencendo ≤ 15 dias: {alertas['vencendo_15_dias']}",
        f"  Suspensas recuper.: {alertas['suspensas_recuperaveis']}",
        f"  Leads novos:        {alertas['leads_novos']}",
        f"  Campanhas renov.:   {alertas['campanhas_renovacao_ativas']}",
        f"  Campanhas reeng.:   {alertas['campanhas_reengajamento_ativas']}",
        "",
        "✅ AÇÕES",
    ]
    for a in acoes:
        linhas.append(f"  {a}")

    return "\n".join(linhas)
