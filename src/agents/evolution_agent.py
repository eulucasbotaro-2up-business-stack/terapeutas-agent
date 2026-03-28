"""
Agente de Evolução — analisa conversas, detecta padrões de erro e sugere melhorias.

Este agente tem duas funções principais:
1. ANÁLISE REATIVA: quando chamado após um erro, analisa o que aconteceu e
   gera um novo aprendizado estruturado para entrar em registro_erros.py
2. ANÁLISE PROATIVA: periodicamente analisa logs de conversas para detectar
   padrões de insatisfação, confusão ou falha silenciosa

O agente usa Claude Opus para análise profunda — é chamado raramente (post-mortem)
e não está no caminho crítico de latência.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# PROMPT DO AGENTE DE EVOLUÇÃO
# =============================================================================

SYSTEM_PROMPT_EVOLUTION = """Você é o Agente de Evolução do Terapeutas Agent — um sistema de IA para terapeutas alquímicos.

Sua função é analisar erros, padrões de falha e comportamentos indesejados do agente principal, e gerar aprendizados estruturados para que esses erros nunca se repitam.

Você tem acesso a:
- Logs de conversas WhatsApp entre terapeutas e o agente
- Descrições de bugs reportados
- Histórico de erros resolvidos

Ao analisar um problema, você sempre:
1. Identifica a CAUSA RAIZ (não apenas o sintoma)
2. Propõe uma solução técnica clara
3. Gera uma REGRA PARA O LLM (instrução direta que entra no system prompt)
4. Categoriza o problema

Categorias disponíveis:
- ALUCINACAO_LLM: LLM inventando informações, seguindo instruções erradas, contradizendo dados reais
- FORMATACAO_WHATSAPP: mensagens mal fragmentadas, formato incorreto, seções desnecessárias
- EXTRACAO_DADOS: falha em extrair nome, data, hora, cidade de mensagens do usuário
- ESTADO_CONVERSACAO: bot perde contexto, pede dados já fornecidos, estado incorreto
- GEOCODIFICACAO: falha em identificar coordenadas de cidade
- PERFORMANCE_INFRA: timeouts, hangs, lentidão, Railway, containers
- CONCORRENCIA: locks, threads, asyncio, race conditions
- TRATAMENTO_EXCECAO: exceções não capturadas, erros silenciosos
- OBSERVABILIDADE: logs ausentes, erros invisíveis, falta de debug
- UX_FEEDBACK: mensagens de erro prematuras, tom incorreto, experiência ruim
- ONBOARDING: fluxo de boas-vindas, coleta de nome, confirmação

Ao gerar um aprendizado, use EXATAMENTE este formato JSON:
{
  "id": "descricao_curta_snake_case_NN",
  "categoria": "CATEGORIA",
  "problema": "Descrição precisa do que aconteceu de errado (o QUE o usuário viu)",
  "causa_raiz": "Por que aconteceu tecnicamente",
  "solucao": "O que foi/deve ser feito para corrigir",
  "regra_para_llm": "Instrução imperativa e direta para o LLM não repetir. Use 'N/A' se for problema de infra/código.",
  "gatilho": "Em que situação esse erro pode ocorrer",
  "data": "YYYY-MM-DD"
}"""


# =============================================================================
# FUNÇÕES DO AGENTE
# =============================================================================

async def analisar_erro_e_gerar_aprendizado(
    descricao_erro: str,
    contexto: Optional[str] = None,
    conversa_exemplo: Optional[str] = None,
) -> dict:
    """
    Analisa um erro descrito e gera um aprendizado estruturado.

    Args:
        descricao_erro: O que aconteceu de errado (pode ser informal)
        contexto: Contexto técnico adicional (stack trace, logs, etc.)
        conversa_exemplo: Exemplo da conversa onde o erro ocorreu

    Returns:
        Dict com o aprendizado estruturado (mesmo formato de APRENDIZADOS em registro_erros.py)
    """
    import anthropic
    import json
    from src.core.config import get_settings

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    partes = [f"ERRO REPORTADO:\n{descricao_erro}"]
    if contexto:
        partes.append(f"\nCONTEXTO TÉCNICO:\n{contexto}")
    if conversa_exemplo:
        partes.append(f"\nEXEMPLO DE CONVERSA:\n{conversa_exemplo}")
    partes.append(
        "\nGere o aprendizado estruturado em JSON. "
        "Responda APENAS com o JSON, sem markdown, sem explicações."
    )

    resposta = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT_EVOLUTION,
        messages=[{"role": "user", "content": "\n".join(partes)}],
    )

    texto = resposta.content[0].text.strip()
    # Remove markdown se presente
    import re
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto).strip()

    aprendizado = json.loads(texto)
    logger.info(f"[EVOLUTION] Aprendizado gerado: {aprendizado.get('id')}")
    print(f"[EVOLUTION] Novo aprendizado: {aprendizado.get('id')} [{aprendizado.get('categoria')}]", flush=True)
    return aprendizado


async def analisar_conversa_para_melhorias(
    conversa: list[dict],
    numero_paciente: str = "desconhecido",
) -> Optional[dict]:
    """
    Analisa uma conversa completa e detecta se houve falha ou padrão problemático.
    Retorna um aprendizado se detectar algo, None se a conversa foi normal.

    Args:
        conversa: Lista de mensagens [{"role": "user/agent", "content": "..."}]
        numero_paciente: Identificador para logging

    Returns:
        Dict com aprendizado estruturado, ou None se sem problemas detectados
    """
    import anthropic
    from src.core.config import get_settings

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    conversa_fmt = "\n".join(
        f"[{m.get('role', 'desconhecido').upper()}]: {m.get('content', '')[:200]}"
        for m in conversa[-20:]  # últimas 20 mensagens
    )

    prompt = f"""Analise esta conversa entre um terapeuta e o agente IA:

{conversa_fmt}

Detecte se houve algum destes problemas:
1. Agente pediu dados que o usuário já tinha fornecido
2. Agente inventou informação (alucinação)
3. Agente deu mensagem de erro incorreta ou desnecessária
4. Agente fragmentou uma resposta que deveria ser coesa
5. Agente ficou em loop ou não avançou
6. Usuário demonstrou frustração explícita ("já falei isso", "não é isso", "errado")
7. Imagem não chegou quando deveria ter chegado

Se NÃO detectar nenhum problema, responda apenas: {{"problema_detectado": false}}

Se detectar problema, gere o aprendizado completo em JSON (mesmo formato padrão).
Responda APENAS com JSON."""

    try:
        resposta = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=600,
            system=SYSTEM_PROMPT_EVOLUTION,
            messages=[{"role": "user", "content": prompt}],
        )

        import json, re
        texto = resposta.content[0].text.strip()
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto).strip()

        dados = json.loads(texto)

        if dados.get("problema_detectado") is False:
            return None

        logger.info(f"[EVOLUTION] Problema detectado em conversa de {numero_paciente}: {dados.get('id')}")
        return dados

    except Exception as e:
        logger.warning(f"[EVOLUTION] Análise de conversa falhou: {e}")
        return None


async def gerar_relatorio_evolucao() -> str:
    """
    Gera um relatório em linguagem natural de todos os aprendizados registrados,
    com sugestões de próximos passos para melhorar o agente.
    """
    import anthropic
    from src.core.config import get_settings
    from src.rag.registro_erros import get_resumo_aprendizados

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    resumo = get_resumo_aprendizados()

    resposta = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT_EVOLUTION,
        messages=[{
            "role": "user",
            "content": (
                f"Com base nos aprendizados registrados abaixo, gere um relatório "
                f"em português sobre:\n"
                f"1. Padrões de erro mais frequentes\n"
                f"2. Áreas de maior fragilidade do sistema\n"
                f"3. Top 5 melhorias prioritárias para o próximo sprint\n"
                f"4. Sugestões de testes para prevenir regressões\n\n"
                f"{resumo}"
            ),
        }],
    )

    return resposta.content[0].text


# =============================================================================
# ENDPOINT PARA ACIONAR O AGENTE VIA API
# =============================================================================

async def processar_feedback_erro(
    erro: str,
    contexto: Optional[str] = None,
    salvar_automaticamente: bool = False,
) -> dict:
    """
    Ponto de entrada principal: recebe descrição de erro e retorna aprendizado.
    Se salvar_automaticamente=True, adiciona ao registro em runtime.

    Uso via HTTP (endpoint /admin/evolution):
        POST {"erro": "Bot pediu dados que já tinham sido enviados", "contexto": "..."}
    """
    from src.rag.registro_erros import adicionar_aprendizado

    aprendizado = await analisar_erro_e_gerar_aprendizado(
        descricao_erro=erro,
        contexto=contexto,
    )

    if salvar_automaticamente:
        adicionar_aprendizado(aprendizado)

    return aprendizado
