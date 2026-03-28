"""
Registro de Aprendizados do Sistema — Terapeutas Agent.

Toda vez que um bug é descoberto e corrigido, o aprendizado entra aqui.
Este módulo injeta as lições aprendidas no system prompt para que erros
conhecidos não se repitam e o agente fique cada vez mais inteligente.

Estrutura de cada aprendizado:
- id: identificador único
- categoria: tipo de problema (ALUCINACAO_LLM, GEOCODIFICACAO, ESTADO, etc.)
- problema: descrição do que aconteceu de errado
- causa_raiz: por que aconteceu
- solucao: o que foi feito para corrigir
- regra_para_llm: instrução direta para o LLM não repetir o erro
- gatilho: quando esse aprendizado é relevante
- data: quando foi descoberto
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# BASE DE CONHECIMENTO — ERROS RESOLVIDOS
# =============================================================================

APRENDIZADOS: list[dict] = [
    {
        "id": "hallucination_refazer_mapa_01",
        "categoria": "ALUCINACAO_LLM",
        "problema": "Quando a imagem do mapa falhava, o LLM recebia instrução '_nota_imagem_sp' com texto 'Se o terapeuta pedir para reenviar a imagem, diga que ele deve digitar refazer mapa'. O LLM interpretava o contexto inteiro como um pedido de reenvio e saía repetindo a instrução como resposta, ignorando 'ENTREGUE A LEITURA ALQUÍMICA AGORA'.",
        "causa_raiz": "Instrução condicional dentro do system prompt ('Se X acontecer, diga Y') — o LLM executa o 'diga Y' independentemente da condição X.",
        "solucao": "Removida a instrução condicional. _nota_imagem_sp agora é imperativa e direta: 'VAI DIRETO PARA A LEITURA, NÃO MENCIONE A IMAGEM'.",
        "regra_para_llm": "NUNCA coloque instruções no formato 'Se o usuário pedir X, diga Y' em _nota_imagem_sp ou em instruções internas — use sempre imperativos diretos.",
        "gatilho": "qualquer instrução interna com estrutura condicional para o LLM",
        "data": "2026-03-28",
    },
    {
        "id": "image_sent_disclaimer_02",
        "categoria": "ALUCINACAO_LLM",
        "problema": "Mesmo quando a imagem do mapa natal foi enviada com sucesso (imagem_enviada=True), o LLM dizia 'Houve uma instabilidade no envio da imagem, mas a leitura está completa'. O LLM inventava um disclaimer de erro que não existia.",
        "causa_raiz": "Instrução: 'Confirme em UMA frase curta que o mapa foi enviado' — o LLM 'confirmava' inventando contexto negativo, possivelmente influenciado por aprendizados anteriores sobre falhas de imagem.",
        "solucao": "Instrução de sucesso alterada para: 'A imagem já foi enviada. NÃO mencione a imagem, NÃO diga que houve instabilidade. Vá direto para a leitura — comece pela primeira linha.'",
        "regra_para_llm": "Quando a imagem foi enviada com sucesso, NÃO mencione o envio. A imagem já está visível no chat. Vá direto para o conteúdo.",
        "gatilho": "imagem_enviada=True + LLM mencionando instabilidade ou confirmando envio",
        "data": "2026-03-28",
    },
    {
        "id": "geocoding_nominatim_hang_03",
        "categoria": "PERFORMANCE_INFRA",
        "problema": "A função geocodificar_cidade() usava Nominatim (geopy) que pendurava indefinidamente mesmo com timeout=10 configurado. O service no Railway ficava completamente silencioso — sem logs, sem resposta — após receber dados de nascimento.",
        "causa_raiz": "Nominatim é uma chamada de rede síncrona. Em containers Railway sem internet confiável, o socket TCP pode abrir mas nunca receber dados, ignorando o timeout da biblioteca.",
        "solucao": "Cache hardcoded _COORDS_BR com 60+ cidades brasileiras. Lookup instantâneo para qualquer cidade comum. Nominatim só é chamado como último fallback. asyncio.wait_for(timeout=90s) envolve toda a chamada gerar_mapa_completo via asyncio.to_thread.",
        "regra_para_llm": "N/A (problema de infraestrutura, não de prompt)",
        "gatilho": "qualquer chamada Nominatim/geopy em produção Railway",
        "data": "2026-03-28",
    },
    {
        "id": "asyncio_cancelled_error_04",
        "categoria": "TRATAMENTO_EXCECAO",
        "problema": "asyncio.CancelledError é BaseException, não Exception. O bloco 'except Exception' no handler do mapa natal não capturava CancelledError, fazendo o background task morrer silenciosamente sem enviar mensagem de erro ou log.",
        "causa_raiz": "Python: BaseException > Exception > CancelledError. except Exception não captura BaseException.",
        "solucao": "Bloco alterado para: except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as mapa_err",
        "regra_para_llm": "N/A (problema de código Python)",
        "gatilho": "qualquer except Exception em código que usa asyncio.wait_for ou background tasks",
        "data": "2026-03-28",
    },
    {
        "id": "logging_sem_basicconfig_05",
        "categoria": "OBSERVABILIDADE",
        "problema": "main.py usava apenas print() para startup. Não havia logging.basicConfig() configurado. Todos os logger.warning() e logger.error() do sistema sumiam no Railway — erros críticos eram invisíveis nos logs.",
        "causa_raiz": "Python logging: sem handler configurado, apenas o 'last resort' handler é usado, que pode não exibir WARNING nos logs do Railway.",
        "solucao": "Adicionado logging.basicConfig(level=logging.WARNING, format='...') no topo de main.py, antes de qualquer import de módulo que usa logger.",
        "regra_para_llm": "N/A (problema de configuração)",
        "gatilho": "novo deploy / novo ambiente onde logs de WARNING não aparecem",
        "data": "2026-03-28",
    },
    {
        "id": "mpl_lock_thread_pool_06",
        "categoria": "CONCORRENCIA",
        "problema": "threading.Lock() com 'with _MPL_LOCK' bloqueava indefinidamente quando o thread pool do asyncio estava saturado — chamadas concorrentes de gerar_imagem_mapa_natal ficavam presas aguardando o lock sem timeout.",
        "causa_raiz": "asyncio.to_thread usa um ThreadPoolExecutor com N threads. Se N threads estão todas esperando o lock, nenhuma avança — deadlock suave.",
        "solucao": "_MPL_LOCK.acquire(timeout=60.0) em vez de 'with _MPL_LOCK'. Se acquire falhar, levanta RuntimeError em vez de bloquear para sempre.",
        "regra_para_llm": "N/A (problema de código Python)",
        "gatilho": "qualquer threading.Lock em código chamado via asyncio.to_thread",
        "data": "2026-03-28",
    },
    {
        "id": "nome_paciente_regex_fraco_07",
        "categoria": "EXTRACAO_DADOS",
        "problema": "extrair_dados_nascimento() só extraía nomes com prefixo explícito 'paciente: Nome' ou 'nome: Nome'. Formato livre 'Lucas Botaro 27/01/1995 12:00h São Paulo capital' retornava nome='Paciente' (placeholder). O bot dizia 'Calculando o mapa alquímico de Paciente agora'.",
        "causa_raiz": "Regex de nome muito restritivo — exigia keywords como 'paciente:' antes do nome.",
        "solucao": "Duas correções: (1) Regex adicional captura nome antes da data no formato livre. (2) Substituição completa do regex por agente LLM (Haiku) que interpreta qualquer formato.",
        "regra_para_llm": "N/A (problema resolvido pelo agente LLM extrator)",
        "gatilho": "dados de nascimento enviados sem prefixo 'paciente:' ou 'nome:'",
        "data": "2026-03-28",
    },
    {
        "id": "erro_mapa_primeira_tentativa_08",
        "categoria": "UX_FEEDBACK",
        "problema": "MSG_ERRO_MAPA_CALCULO era enviada na 1ª e 2ª tentativa de falha de cálculo de mapa. O usuário via 'Pedimos desculpas! Houve uma instabilidade técnica' imediatamente, mesmo sendo um erro transiente que poderia se resolver sozinho.",
        "causa_raiz": "O bloco else do exception handler enviava a mensagem em todas as tentativas < _MAPA_MAX_TENTATIVAS.",
        "solucao": "Tentativas 1 e 2 são silenciosas. Só na 3ª (>= _MAPA_MAX_TENTATIVAS) o usuário é avisado com número de suporte.",
        "regra_para_llm": "N/A (lógica de retry)",
        "gatilho": "cálculo de mapa falhando nas primeiras tentativas",
        "data": "2026-03-28",
    },
    {
        "id": "leitura_mapa_fragmentada_09",
        "categoria": "FORMATACAO_WHATSAPP",
        "problema": "A instrução 'Respostas longas DEVEM ter pelo menos 2 seções separadas por ---SECAO---' forçava o LLM a fragmentar a leitura do mapa natal em múltiplas mensagens WhatsApp. O terapeuta recebia a análise em 4-5 mensagens separadas, quebrando o fluxo de leitura.",
        "causa_raiz": "Regra genérica de formatação não distinguia leitura de mapa (tema único) de diagnóstico clínico (múltiplos temas).",
        "solucao": "Regra específica: leitura de mapa natal é UM tema único — fica em UMA seção. Cabeçalho (*Nome — Data — Hora — Cidade*) em linha própria no início. Casos clínicos mantêm 2-3 seções quando temas são distintos.",
        "regra_para_llm": "LEITURA DE MAPA NATAL: toda a análise astrológica é UM tema — UMA seção. Não use ---SECAO--- no meio da leitura do mapa.",
        "gatilho": "leitura de mapa natal sendo dividida em múltiplas mensagens",
        "data": "2026-03-28",
    },
    {
        "id": "extracao_dados_regex_fragil_10",
        "categoria": "EXTRACAO_DADOS",
        "problema": "O extrator regex de dados de nascimento falhava com variações comuns: 'SP' (em vez de São Paulo), 'São Paulo - capital', 'São Paulo/SP', 'BH', 'Rio'. Áudio transcrito com linguagem natural ('nasceu em são paulo') também falhava.",
        "causa_raiz": "Regex não consegue normalizar semântica de linguagem natural. Cada variação precisaria de uma nova regra.",
        "solucao": "Substituído por agente LLM (Claude Haiku, max_tokens=150, timeout=12s) que interpreta qualquer formato. Normaliza automaticamente: 'SP'→'São Paulo', 'BH'→'Belo Horizonte', 'Rio'→'Rio de Janeiro', datas por extenso, horas em linguagem natural. Fallback automático para regex se LLM falhar.",
        "regra_para_llm": "N/A (problema resolvido pelo agente Haiku)",
        "gatilho": "dados de nascimento em formato não-padrão ou áudio transcrito",
        "data": "2026-03-28",
    },
    {
        "id": "refazer_mapa_pede_dados_novamente_11",
        "categoria": "ESTADO_CONVERSACAO",
        "problema": "Quando usuário digitava 'refazer mapa', o interceptor buscava dados de nascimento no histórico via extrair_dados_nascimento(). O regex falhava em encontrar os dados mesmo com eles presentes no histórico (por causa das variações de formato), e o bot pedia os dados novamente: 'Para refazer o mapa, preciso dos dados de nascimento novamente'.",
        "causa_raiz": "Mesmo problema do regex frágil (#10), agora na busca de histórico.",
        "solucao": "Interceptor 'refazer mapa' agora usa await extrair_dados_nascimento_llm() para buscar dados no histórico. O LLM consegue reconhecer dados mesmo em formatos variados dentro do texto concatenado do histórico.",
        "regra_para_llm": "N/A",
        "gatilho": "usuário digita 'refazer mapa' após já ter fornecido dados em formato não-padrão",
        "data": "2026-03-28",
    },
    {
        "id": "eh_pedido_mapa_sem_dados_history_12",
        "categoria": "ESTADO_CONVERSACAO",
        "problema": "_eh_pedido_mapa_sem_dados() retornava False quando 'mapa natal' aparecia no histórico (lógica: se já foi discutido, é follow-up). Mas 'mapa natal' aparecia nas respostas do BOT (onboarding: 'pode fazer mapa natal completo'). Resultado: 'Quero fazer um mapa Natal' sem dados entrava no cálculo com dados incorretos do histórico.",
        "causa_raiz": "Indicadores de contexto de mapa no histórico incluíam texto do BOT, não apenas do usuário.",
        "solucao": "Com o agente LLM extrator, se não há dados de nascimento reais no texto, extrair_dados_nascimento_llm() retorna None. O fluxo correto (pedir dados) é restaurado.",
        "regra_para_llm": "N/A",
        "gatilho": "mensagem sobre mapa natal sem dados, histórico contém texto do bot mencionando mapa natal",
        "data": "2026-03-28",
    },
]


# =============================================================================
# FUNÇÕES DE CONSULTA
# =============================================================================

def get_aprendizados_para_llm() -> str:
    """
    Retorna string formatada com as regras relevantes para o LLM.
    Filtra apenas aprendizados com regra_para_llm definida (não 'N/A').
    Usado para injetar no system prompt e evitar erros conhecidos.
    """
    regras = [
        a for a in APRENDIZADOS
        if a.get("regra_para_llm") and a["regra_para_llm"] != "N/A"
    ]
    if not regras:
        return ""

    linhas = ["REGRAS CRÍTICAS — ERROS CONHECIDOS QUE NÃO DEVEM SE REPETIR:"]
    for r in regras:
        linhas.append(f"[{r['categoria']}] {r['regra_para_llm']}")

    return "\n".join(linhas)


def get_resumo_aprendizados() -> str:
    """
    Retorna resumo legível de todos os aprendizados.
    Usado para relatórios e contexto do agente de evolução.
    """
    linhas = [f"BASE DE APRENDIZADOS — {len(APRENDIZADOS)} lições registradas\n"]
    for i, a in enumerate(APRENDIZADOS, 1):
        linhas.append(
            f"{i}. [{a['categoria']}] {a['id']}\n"
            f"   Problema: {a['problema'][:120]}...\n"
            f"   Solução: {a['solucao'][:120]}...\n"
        )
    return "\n".join(linhas)


def get_aprendizados_por_categoria(categoria: str) -> list[dict]:
    """Retorna todos os aprendizados de uma categoria específica."""
    return [a for a in APRENDIZADOS if a["categoria"] == categoria]


def adicionar_aprendizado(novo: dict) -> None:
    """
    Adiciona um novo aprendizado à base em runtime.
    Para persistência permanente, o aprendizado deve ser adicionado
    manualmente à lista APRENDIZADOS acima.
    """
    required = {"id", "categoria", "problema", "solucao", "regra_para_llm"}
    if not required.issubset(novo.keys()):
        raise ValueError(f"Aprendizado deve ter campos: {required}")
    APRENDIZADOS.append(novo)
    logger.info(f"Novo aprendizado adicionado: {novo['id']}")
    print(f"[APRENDIZADO] Novo: {novo['id']} [{novo['categoria']}]", flush=True)
