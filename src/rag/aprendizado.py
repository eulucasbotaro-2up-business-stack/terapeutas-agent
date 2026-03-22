"""
Motor de Aprendizado Continuo — Terapeutas Agent.

O agente aprende e melhora a cada interacao com cada terapeuta.
Detecta padroes de uso, nivel de maturidade, temas recorrentes,
e personaliza as respostas ao longo do tempo.

Funcionalidades:
- Analise pos-conversa: extrai padroes apos cada interacao
- Contexto acumulado: carrega perfil personalizado antes de cada resposta
- Feedback: terapeuta avalia respostas do agente
- Relatorio semanal: resumo de uso e evolucao
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from src.core.config import get_settings
from src.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES DE TEMAS E PADROES
# =============================================================================

# Temas que o sistema detecta automaticamente nas conversas
TEMAS_DETECTAVEIS: dict[str, list[str]] = {
    "ansiedade": ["ansiedade", "ansioso", "ansiosa", "panico", "nervoso", "nervosa"],
    "depressao": ["depressao", "deprimido", "deprimida", "tristeza", "melancolico"],
    "trauma": ["trauma", "traumas", "traumatico", "ptsd", "estresse pos"],
    "relacionamento": ["casal", "casais", "relacionamento", "parceiro", "parceira", "conjugal"],
    "autoestima": ["autoestima", "autoimagem", "inseguranca", "confianca"],
    "luto": ["luto", "perda", "morte", "falecimento", "saudade"],
    "sono": ["insonia", "sono", "dormir", "pesadelo"],
    "elemento_fogo": ["fogo", "elemento fogo", "igneo", "colera", "raiva"],
    "elemento_agua": ["agua", "elemento agua", "emocional", "fluidez"],
    "elemento_terra": ["terra", "elemento terra", "estabilidade", "material"],
    "elemento_ar": ["ar", "elemento ar", "mental", "pensamento"],
    "florais": ["floral", "florais", "essencia", "composto floral"],
    "dna_alquimico": ["dna", "genetico", "hereditario", "ancestral", "padrao familiar"],
    "nigredo": ["nigredo", "sombra", "dissolucao", "morte simbolica"],
    "rubedo": ["rubedo", "transformacao", "integracao"],
    "astrologia": ["mapa astral", "mapa natal", "astrologia", "astral", "data de nascimento"],
    "protocolo": ["protocolo", "protocolos", "kit primus", "kite primus"],
    "chakras": ["chakra", "chakras", "chackra", "chackras", "centro energetico"],
    "miasmas": ["miasma", "miasmas", "miasmatico"],
    "pletora": ["pletora", "quatro elementos", "4 elementos"],
}

# Palavras-chave para detectar nivel de maturidade da terapeuta
INDICADORES_NIVEL: dict[int, list[str]] = {
    1: ["o que e", "como funciona", "me explica", "basico", "iniciante", "comecar"],
    2: ["elemento", "campo", "desequilibrio", "diagnostico", "pletora"],
    3: ["dna", "identidade", "padrao familiar", "hereditario", "leitura dna"],
    4: ["nigredo", "rubedo", "dissolucao", "trindade", "tartarus", "ciclo"],
    5: ["fluxus", "continuum", "mapa astral", "biorritmo", "astrologia", "john dee"],
    6: ["protocolo", "floral", "composto", "kit primus", "aplicacao terapeutica"],
}

# Indicadores de estilo de resposta preferido
INDICADORES_ESTILO: dict[str, list[str]] = {
    "direto": ["direto ao ponto", "resumo", "rapido", "objetivo", "curto"],
    "detalhado": ["detalhe", "aprofunde", "explique mais", "completo", "tudo sobre"],
    "pratico": ["pratica", "aplicar", "como usar", "passo a passo", "receita"],
    "teorico": ["teoria", "conceito", "fundamento", "porque", "origem"],
}


# =============================================================================
# A. ANALISE POS-CONVERSA
# =============================================================================

async def analisar_conversa(
    terapeuta_id: str,
    mensagem: str,
    resposta: str,
    modo: str,
    chunks_usados: list[dict] | None = None,
) -> None:
    """
    Analisa a conversa apos cada interacao e extrai padroes.

    Roda em background para nao atrasar a resposta.
    Detecta temas recorrentes, florais indicados, nivel de maturidade
    e estilo preferido da terapeuta.

    Args:
        terapeuta_id: UUID do terapeuta.
        mensagem: Texto da mensagem original da terapeuta.
        resposta: Texto da resposta gerada pelo agente.
        modo: Modo de operacao usado (CONSULTA, CRIACAO_CONTEUDO, PESQUISA).
        chunks_usados: Lista de chunks RAG usados na resposta.
    """
    try:
        logger.info(f"Iniciando analise de aprendizado para terapeuta {terapeuta_id}")
        mensagem_lower = mensagem.lower()

        # 1. Detectar temas recorrentes
        temas_detectados = _detectar_temas(mensagem_lower)
        for tema in temas_detectados:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="tema_recorrente",
                chave=tema,
                valor=modo,
            )

        # 2. Detectar florais/protocolos mencionados na resposta
        florais_detectados = _detectar_florais(resposta.lower())
        for floral in florais_detectados:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="floral_mais_indicado",
                chave=floral,
            )

        # 3. Estimar nivel de maturidade da pergunta
        nivel = _estimar_nivel(mensagem_lower)
        if nivel > 0:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="nivel_pergunta",
                chave=str(nivel),
                valor=mensagem[:200],
            )

        # 4. Detectar estilo preferido
        estilo = _detectar_estilo(mensagem_lower)
        if estilo:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="estilo_preferido",
                chave=estilo,
            )

        # 5. Registrar o modo usado (consulta, conteudo, pesquisa)
        await atualizar_padrao(
            terapeuta_id=terapeuta_id,
            tipo="modo_uso",
            chave=modo,
        )

        # 6. Atualizar contexto acumulado com base nos padroes
        await _atualizar_contexto_acumulado(terapeuta_id)

        logger.info(
            f"Analise concluida para terapeuta {terapeuta_id}: "
            f"{len(temas_detectados)} temas, nivel={nivel}, estilo={estilo}"
        )

    except Exception as e:
        # Nunca deixar o aprendizado quebrar o fluxo principal
        logger.error(f"Erro na analise de aprendizado: {e}", exc_info=True)


def _detectar_temas(texto: str) -> list[str]:
    """Detecta temas presentes no texto com base nas palavras-chave."""
    temas = []
    for tema, palavras in TEMAS_DETECTAVEIS.items():
        for palavra in palavras:
            if palavra in texto:
                temas.append(tema)
                break  # Um match por tema e suficiente
    return temas


def _detectar_florais(texto: str) -> list[str]:
    """Detecta mencoes a florais e compostos na resposta do agente."""
    florais = []
    # Padrao generico: detecta quando a resposta menciona florais especificos
    indicadores = [
        "floral de", "composto de", "essencia de", "protocolo de",
        "kit primus", "kite primus", "aura das flores",
    ]
    for indicador in indicadores:
        if indicador in texto:
            # Extrai o contexto ao redor do indicador
            pos = texto.find(indicador)
            trecho = texto[pos:pos + 80]
            florais.append(trecho.strip()[:60])
    return florais


def _estimar_nivel(texto: str) -> int:
    """Estima o nivel de maturidade da pergunta (1-6)."""
    scores: dict[int, int] = {n: 0 for n in range(1, 7)}
    for nivel, palavras in INDICADORES_NIVEL.items():
        for palavra in palavras:
            if palavra in texto:
                scores[nivel] += 1

    nivel_max = max(scores, key=lambda n: scores[n])
    return nivel_max if scores[nivel_max] > 0 else 0


def _detectar_estilo(texto: str) -> str | None:
    """Detecta o estilo de resposta preferido pela terapeuta."""
    for estilo, palavras in INDICADORES_ESTILO.items():
        for palavra in palavras:
            if palavra in texto:
                return estilo
    return None


async def _atualizar_contexto_acumulado(terapeuta_id: str) -> None:
    """
    Recalcula e atualiza o contexto acumulado da terapeuta
    com base nos padroes mais frequentes.
    """
    supabase = get_supabase()

    try:
        # Buscar todos os padroes da terapeuta
        resultado = (
            supabase.table("padroes_terapeuta")
            .select("*")
            .eq("terapeuta_id", terapeuta_id)
            .order("frequencia", desc=True)
            .execute()
        )

        if not resultado.data:
            return

        padroes = resultado.data

        # Calcular nivel de maturidade medio (baseado nos niveis das perguntas)
        niveis = [
            int(p["chave"]) for p in padroes
            if p["tipo"] == "nivel_pergunta" and p["chave"].isdigit()
        ]
        if niveis:
            # Media ponderada pela frequencia
            padroes_nivel = [
                p for p in padroes if p["tipo"] == "nivel_pergunta" and p["chave"].isdigit()
            ]
            soma_ponderada = sum(int(p["chave"]) * p["frequencia"] for p in padroes_nivel)
            soma_frequencias = sum(p["frequencia"] for p in padroes_nivel)
            nivel_medio = round(soma_ponderada / soma_frequencias, 1) if soma_frequencias > 0 else 1
            await _upsert_contexto(terapeuta_id, "nivel_maturidade", str(nivel_medio))

        # Top 5 temas mais frequentes
        temas = [
            p for p in padroes if p["tipo"] == "tema_recorrente"
        ][:5]
        if temas:
            temas_texto = ", ".join(f"{t['chave']} ({t['frequencia']}x)" for t in temas)
            await _upsert_contexto(terapeuta_id, "temas_dominados", temas_texto)

        # Estilo mais frequente
        estilos = [
            p for p in padroes if p["tipo"] == "estilo_preferido"
        ]
        if estilos:
            estilo_top = estilos[0]["chave"]
            await _upsert_contexto(terapeuta_id, "tom_preferido", estilo_top)

        # Modo de uso mais frequente
        modos = [
            p for p in padroes if p["tipo"] == "modo_uso"
        ]
        if modos:
            modo_top = modos[0]["chave"]
            await _upsert_contexto(terapeuta_id, "modo_principal", modo_top)

    except Exception as e:
        logger.error(f"Erro ao atualizar contexto acumulado: {e}", exc_info=True)


async def _upsert_contexto(terapeuta_id: str, tipo: str, conteudo: str) -> None:
    """Insere ou atualiza um registro na tabela contexto_terapeuta."""
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("contexto_terapeuta").upsert(
            {
                "terapeuta_id": terapeuta_id,
                "tipo": tipo,
                "conteudo": conteudo,
                "atualizado_em": agora,
            },
            on_conflict="terapeuta_id,tipo",
        ).execute()
    except Exception as e:
        logger.error(f"Erro ao upsert contexto ({tipo}): {e}")


# =============================================================================
# B. CARREGAR CONTEXTO ACUMULADO
# =============================================================================

async def carregar_contexto_terapeuta(terapeuta_id: str) -> dict:
    """
    Carrega o contexto personalizado acumulado da terapeuta.

    Busca no banco:
    - Padroes mais frequentes
    - Nivel de maturidade estimado
    - Temas que ela mais domina
    - Estilo de resposta preferido

    Retorna um dict que e injetado no prompt como "CONTEXTO PERSONALIZADO".

    Args:
        terapeuta_id: UUID do terapeuta.

    Returns:
        Dict com chaves: nivel, temas, estilo, padroes, modo_principal.
        Retorna valores padrao se nao houver dados ainda.
    """
    supabase = get_supabase()
    contexto = {
        "nivel": "ainda em avaliacao",
        "temas": "ainda sem dados suficientes",
        "estilo": "padrao (equilibrado)",
        "padroes": "ainda sem dados suficientes",
        "modo_principal": "nao definido",
        "tem_dados": False,
    }

    try:
        # Buscar contexto acumulado
        resultado = (
            supabase.table("contexto_terapeuta")
            .select("tipo, conteudo")
            .eq("terapeuta_id", terapeuta_id)
            .execute()
        )

        if resultado.data:
            contexto["tem_dados"] = True
            for registro in resultado.data:
                tipo = registro["tipo"]
                conteudo = registro["conteudo"]

                if tipo == "nivel_maturidade":
                    contexto["nivel"] = conteudo
                elif tipo == "temas_dominados":
                    contexto["temas"] = conteudo
                elif tipo == "tom_preferido":
                    contexto["estilo"] = conteudo
                elif tipo == "modo_principal":
                    contexto["modo_principal"] = conteudo

        # Buscar top padroes recentes para enriquecer o contexto
        padroes = (
            supabase.table("padroes_terapeuta")
            .select("tipo, chave, frequencia")
            .eq("terapeuta_id", terapeuta_id)
            .order("frequencia", desc=True)
            .limit(10)
            .execute()
        )

        if padroes.data:
            contexto["tem_dados"] = True
            padroes_resumo = [
                f"{p['tipo']}: {p['chave']} ({p['frequencia']}x)"
                for p in padroes.data
            ]
            contexto["padroes"] = "; ".join(padroes_resumo)

        logger.info(
            f"Contexto carregado para terapeuta {terapeuta_id}: "
            f"nivel={contexto['nivel']}, tem_dados={contexto['tem_dados']}"
        )

    except Exception as e:
        logger.error(f"Erro ao carregar contexto da terapeuta: {e}", exc_info=True)

    return contexto


# =============================================================================
# C. REGISTRAR FEEDBACK
# =============================================================================

async def registrar_feedback(
    terapeuta_id: str,
    conversa_id: str,
    avaliacao: int,
    comentario: str | None = None,
    tipo: str = "consulta",
) -> dict:
    """
    Salva feedback da terapeuta sobre uma resposta do agente.

    Args:
        terapeuta_id: UUID do terapeuta.
        conversa_id: UUID da conversa avaliada.
        avaliacao: Nota de 1 (ruim) a 5 (excelente).
        comentario: Feedback livre (opcional).
        tipo: Tipo da interacao ('consulta', 'conteudo', 'pesquisa').

    Returns:
        Dict com os dados do feedback salvo.
    """
    supabase = get_supabase()

    registro = {
        "terapeuta_id": terapeuta_id,
        "conversa_id": conversa_id,
        "avaliacao": avaliacao,
        "comentario": comentario,
        "tipo": tipo,
    }

    try:
        resultado = (
            supabase.table("feedback_respostas")
            .insert(registro)
            .execute()
        )

        logger.info(
            f"Feedback registrado: terapeuta={terapeuta_id}, "
            f"conversa={conversa_id}, nota={avaliacao}"
        )

        # Se a nota for baixa (1-2), registrar como padrao para aprender
        if avaliacao <= 2:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="resposta_ruim",
                chave=tipo,
                valor=comentario or "sem comentario",
            )

        # Se a nota for alta (4-5), registrar como padrao positivo
        if avaliacao >= 4:
            await atualizar_padrao(
                terapeuta_id=terapeuta_id,
                tipo="resposta_boa",
                chave=tipo,
                valor=comentario or "sem comentario",
            )

        return resultado.data[0] if resultado.data else registro

    except Exception as e:
        logger.error(f"Erro ao registrar feedback: {e}", exc_info=True)
        raise


# =============================================================================
# D. ATUALIZAR PADRAO
# =============================================================================

async def atualizar_padrao(
    terapeuta_id: str,
    tipo: str,
    chave: str,
    valor: str | None = None,
) -> None:
    """
    Incrementa frequencia de um padrao existente ou cria um novo.

    Usa UPSERT: se o padrao (terapeuta_id, tipo, chave) ja existe,
    incrementa a frequencia e atualiza ultima_ocorrencia.
    Se nao existe, cria com frequencia=1.

    Args:
        terapeuta_id: UUID do terapeuta.
        tipo: Tipo do padrao (ex: 'tema_recorrente', 'floral_mais_indicado').
        chave: O padrao em si (ex: 'ansiedade', 'elemento fogo').
        valor: Detalhes adicionais (opcional).
    """
    supabase = get_supabase()
    agora = datetime.now(timezone.utc).isoformat()

    try:
        # Primeiro, tenta buscar se o padrao ja existe
        existente = (
            supabase.table("padroes_terapeuta")
            .select("id, frequencia")
            .eq("terapeuta_id", terapeuta_id)
            .eq("tipo", tipo)
            .eq("chave", chave)
            .limit(1)
            .execute()
        )

        if existente.data and len(existente.data) > 0:
            # Padrao existe — incrementar frequencia
            padrao_id = existente.data[0]["id"]
            nova_frequencia = existente.data[0]["frequencia"] + 1

            dados_update: dict = {
                "frequencia": nova_frequencia,
                "ultima_ocorrencia": agora,
            }
            if valor is not None:
                dados_update["valor"] = valor

            supabase.table("padroes_terapeuta").update(
                dados_update
            ).eq("id", padrao_id).execute()

            logger.debug(
                f"Padrao atualizado: {tipo}/{chave} = {nova_frequencia}x "
                f"(terapeuta {terapeuta_id})"
            )
        else:
            # Padrao novo — criar
            supabase.table("padroes_terapeuta").insert({
                "terapeuta_id": terapeuta_id,
                "tipo": tipo,
                "chave": chave,
                "valor": valor,
                "frequencia": 1,
                "ultima_ocorrencia": agora,
            }).execute()

            logger.debug(
                f"Novo padrao criado: {tipo}/{chave} (terapeuta {terapeuta_id})"
            )

    except Exception as e:
        logger.error(f"Erro ao atualizar padrao ({tipo}/{chave}): {e}", exc_info=True)


# =============================================================================
# E. GERAR RELATORIO SEMANAL
# =============================================================================

async def gerar_relatorio_semanal(terapeuta_id: str) -> dict:
    """
    Gera um resumo semanal de uso e evolucao para a terapeuta.

    Inclui:
    - Quantas consultas fez na semana
    - Temas mais abordados
    - Florais mais indicados
    - Sugestao de materiais para aprofundar
    - Evolucao do nivel de maturidade
    - Media de satisfacao (baseada em feedbacks)

    Args:
        terapeuta_id: UUID do terapeuta.

    Returns:
        Dict com o relatorio completo.
    """
    supabase = get_supabase()
    uma_semana_atras = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    relatorio: dict = {
        "periodo": {
            "inicio": uma_semana_atras,
            "fim": datetime.now(timezone.utc).isoformat(),
        },
        "total_conversas": 0,
        "conversas_por_modo": {},
        "temas_mais_abordados": [],
        "florais_mais_indicados": [],
        "nivel_maturidade": "sem dados",
        "evolucao_nivel": "sem dados suficientes",
        "media_satisfacao": None,
        "total_feedbacks": 0,
        "sugestao_materiais": [],
    }

    try:
        # 1. Total de conversas na semana
        conversas = (
            supabase.table("conversas")
            .select("id, intencao, criado_em")
            .eq("terapeuta_id", terapeuta_id)
            .gte("criado_em", uma_semana_atras)
            .execute()
        )

        if conversas.data:
            relatorio["total_conversas"] = len(conversas.data)

            # Conversas por modo/intencao
            modos: dict[str, int] = {}
            for c in conversas.data:
                intencao = c.get("intencao", "desconhecida")
                # Intencao pode ter formato "MODO|INTENCAO_LLM"
                modo = intencao.split("|")[0] if "|" in intencao else intencao
                modos[modo] = modos.get(modo, 0) + 1
            relatorio["conversas_por_modo"] = modos

        # 2. Temas mais abordados (padroes da semana)
        temas = (
            supabase.table("padroes_terapeuta")
            .select("chave, frequencia")
            .eq("terapeuta_id", terapeuta_id)
            .eq("tipo", "tema_recorrente")
            .order("frequencia", desc=True)
            .limit(10)
            .execute()
        )

        if temas.data:
            relatorio["temas_mais_abordados"] = [
                {"tema": t["chave"], "frequencia": t["frequencia"]}
                for t in temas.data
            ]

        # 3. Florais mais indicados
        florais = (
            supabase.table("padroes_terapeuta")
            .select("chave, frequencia")
            .eq("terapeuta_id", terapeuta_id)
            .eq("tipo", "floral_mais_indicado")
            .order("frequencia", desc=True)
            .limit(5)
            .execute()
        )

        if florais.data:
            relatorio["florais_mais_indicados"] = [
                {"floral": f["chave"], "frequencia": f["frequencia"]}
                for f in florais.data
            ]

        # 4. Nivel de maturidade atual
        contexto = (
            supabase.table("contexto_terapeuta")
            .select("conteudo")
            .eq("terapeuta_id", terapeuta_id)
            .eq("tipo", "nivel_maturidade")
            .limit(1)
            .execute()
        )

        if contexto.data:
            nivel_atual = contexto.data[0]["conteudo"]
            relatorio["nivel_maturidade"] = nivel_atual

            # Sugerir materiais com base no nivel
            try:
                nivel_num = float(nivel_atual)
                relatorio["sugestao_materiais"] = _sugerir_materiais(nivel_num)
            except (ValueError, TypeError):
                pass

        # 5. Media de satisfacao (feedbacks da semana)
        feedbacks = (
            supabase.table("feedback_respostas")
            .select("avaliacao")
            .eq("terapeuta_id", terapeuta_id)
            .gte("criado_em", uma_semana_atras)
            .execute()
        )

        if feedbacks.data:
            notas = [f["avaliacao"] for f in feedbacks.data if f["avaliacao"]]
            relatorio["total_feedbacks"] = len(notas)
            if notas:
                relatorio["media_satisfacao"] = round(sum(notas) / len(notas), 1)

        logger.info(
            f"Relatorio semanal gerado para terapeuta {terapeuta_id}: "
            f"{relatorio['total_conversas']} conversas"
        )

    except Exception as e:
        logger.error(f"Erro ao gerar relatorio semanal: {e}", exc_info=True)
        relatorio["erro"] = str(e)

    return relatorio


def _sugerir_materiais(nivel: float) -> list[dict]:
    """
    Sugere materiais para aprofundamento com base no nivel de maturidade.

    A logica e: sugerir materiais do nivel atual e do proximo nivel.
    """
    # Mapeamento nivel -> materiais sugeridos (da escola de alquimia)
    materiais_por_nivel: dict[int, list[str]] = {
        1: ["Material de Pesquisa.pdf", "PERGUNTAS FREQUENTES.pdf"],
        2: ["QUATRO ELEMENTOS E PLETORA.pdf", "MATRIX E TRAUMAS.pdf", "Miasmas.pdf"],
        3: ["DNA.pdf", "REFERENCIA DO DNA.pdf"],
        4: ["Apostila Trindade e Tartarus - Nigredo.pdf", "Apostila Rubedo - 1a Edicao (1).pdf"],
        5: ["O Fluxus Continuum de John Dee PDF (1).pdf", "ASTROLOGIA.pdf", "BIORRITIMOS.pdf"],
        6: ["COMO USAR OS PROTOCOLOS.pdf", "SIGNIFICADO KITE PRIMUS.pdf", "A Aura das flores.pdf"],
    }

    descricao_niveis: dict[int, str] = {
        1: "Observacao e Pesquisa",
        2: "Estrutura do Campo",
        3: "DNA e Identidade",
        4: "Ciclos e Dissolucao",
        5: "Tempo e Consciencia",
        6: "Materializacao Terapeutica",
    }

    sugestoes = []
    nivel_int = int(nivel)
    proximo_nivel = min(nivel_int + 1, 6)

    # Sugerir materiais do proximo nivel
    if proximo_nivel in materiais_por_nivel:
        for material in materiais_por_nivel[proximo_nivel]:
            sugestoes.append({
                "material": material,
                "nivel": proximo_nivel,
                "descricao": descricao_niveis.get(proximo_nivel, ""),
                "motivo": f"Proximo passo na evolucao (Nivel {proximo_nivel})",
            })

    # Se esta entre niveis, sugerir consolidar o nivel atual tambem
    parte_decimal = nivel - nivel_int
    if parte_decimal < 0.5 and nivel_int in materiais_por_nivel:
        for material in materiais_por_nivel[nivel_int]:
            sugestoes.append({
                "material": material,
                "nivel": nivel_int,
                "descricao": descricao_niveis.get(nivel_int, ""),
                "motivo": f"Consolidar o Nivel {nivel_int} atual",
            })

    return sugestoes


# =============================================================================
# F. FUNCAO AUXILIAR: FORMATAR CONTEXTO PARA PROMPT
# =============================================================================

def formatar_contexto_personalizado(contexto: dict) -> str:
    """
    Formata o contexto personalizado da terapeuta para injecao no prompt.

    Args:
        contexto: Dict retornado por carregar_contexto_terapeuta().

    Returns:
        String formatada para adicionar ao system prompt.
    """
    if not contexto.get("tem_dados"):
        return (
            "CONTEXTO PERSONALIZADO DESTA TERAPEUTA:\n"
            "- Primeira interacao ou dados insuficientes. "
            "Trate como nova terapeuta e seja acolhedora."
        )

    return (
        "CONTEXTO PERSONALIZADO DESTA TERAPEUTA:\n"
        f"- Nivel de maturidade estimado: {contexto['nivel']}\n"
        f"- Temas que mais domina: {contexto['temas']}\n"
        f"- Estilo preferido: {contexto['estilo']}\n"
        f"- Modo de uso principal: {contexto['modo_principal']}\n"
        f"- Padroes recorrentes: {contexto['padroes']}\n\n"
        "Use este contexto para personalizar a resposta. Se a terapeuta e avancada (nivel 4+), "
        "va direto ao ponto com linguagem tecnica. Se e iniciante (nivel 1-2), seja mais didatica."
    )
