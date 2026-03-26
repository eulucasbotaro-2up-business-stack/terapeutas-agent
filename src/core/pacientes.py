"""
Sistema de gerenciamento de sessoes por paciente.

Permite ao agente:
- Manter historico SEPARADO por paciente (sem misturar casos)
- Detectar quando o terapeuta troca de paciente
- Confirmar periodicamente de qual paciente estao falando
- Extrair dados clinicos de cada mensagem (sintomas, florais, cartas, etc.)
- Fase investigativa antes de qualquer tratamento
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# PALAVRAS-CHAVE PARA DETECTAR TROCA DE PACIENTE
# =============================================================================

PALAVRAS_TROCA_PACIENTE = [
    "outro caso",
    "outra caso",
    "nova paciente",
    "novo paciente",
    "outro paciente",
    "outra paciente",
    "agora sobre",
    "mudando de caso",
    "caso diferente",
    "paciente diferente",
    "proximo caso",
    "proxima caso",
    "próximo caso",
    "próxima caso",
    "quero falar de",
    "quero falar sobre",
    "vamos falar de",
    "vamos falar sobre",
    "tenho um caso",
    "tenho uma paciente",
    "tenho um paciente",
    "recebi uma paciente",
    "recebi um paciente",
    "atendi uma paciente",
    "atendi um paciente",
    "chegou uma paciente",
    "chegou um paciente",
    "estou atendendo",
    "comecei a atender",
]

# Padroes regex para extrair nome do paciente
# Ex: "paciente Maria", "a Maria", "sobre a Joana", "caso do Pedro"
PADROES_NOME_PACIENTE = [
    r"(?:paciente|cliente)\s+(?:chamad[oa]\s+)?([A-Z][a-záéíóúãõâêîôûç]+)",
    r"(?:sobre|caso)\s+(?:d[oa]\s+)?([A-Z][a-záéíóúãõâêîôûç]+)",
    r"(?:a|o)\s+([A-Z][a-záéíóúãõâêîôûç]+)\s+(?:tem|está|veio|chegou|relatou|apresenta)",
    r"(?:atendendo|atendi)\s+(?:a|o)?\s*([A-Z][a-záéíóúãõâêîôûç]+)",
    r"(?:chama|nome)\s+(?:é\s+)?([A-Z][a-záéíóúãõâêîôûç]+)",
]

# Categorias de dados que o agente extrai de cada mensagem
CATEGORIAS_DADOS = {
    "sintomas": [
        "ansiedade", "depressao", "depressão", "insonia", "insônia", "medo",
        "raiva", "tristeza", "angustia", "angústia", "pânico", "panico",
        "estresse", "stress", "burnout", "dor", "choro", "apatia",
        "irritabilidade", "nervosismo", "culpa", "vergonha", "solidao",
        "solidão", "abandono", "rejeicao", "rejeição", "trauma",
        "compulsao", "compulsão", "obsessao", "obsessão", "fobia",
        "cansaco", "cansaço", "exaustao", "exaustão", "desanimo",
        "desânimo", "bloqueio", "resistencia", "resistência",
    ],
    "florais": [
        "rescue", "cherry plum", "rock rose", "clematis", "impatiens",
        "star of bethlehem", "walnut", "mimulus", "aspen", "red chestnut",
        "cerato", "scleranthus", "gentian", "gorse", "hornbeam",
        "wild oat", "chicory", "vervain", "vine", "beech",
        "rock water", "water violet", "heather", "agrimony",
        "centaury", "holly", "larch", "pine", "elm", "sweet chestnut",
        "willow", "oak", "crab apple", "chestnut bud", "white chestnut",
        "honeysuckle", "wild rose", "olive", "mustard",
        # Florais de Saint Germain e outros
        "floral", "essencia", "essência", "tintura",
    ],
    "cartas": [
        "taro", "tarô", "carta", "arcano", "maior", "menor",
        "espadas", "copas", "ouros", "paus", "bastoes", "bastões",
        "imperatriz", "imperador", "papisa", "mago", "louco",
        "torre", "estrela", "lua", "sol", "julgamento", "mundo",
        "eremita", "roda", "forca", "força", "enforcado", "morte",
        "temperanca", "temperança", "diabo", "amantes", "carro",
        "justica", "justiça", "hierofante",
    ],
    "dados_nascimento": [
        r"\d{1,2}/\d{1,2}/\d{2,4}",  # DD/MM/AAAA ou DD/MM/AA
        r"\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",  # "15 de março de 1990"
        "nasceu", "nascimento", "data de nascimento", "signo",
        "ascendente", "mapa astral", "mapa natal", "carta natal",
    ],
    "informacoes_familiares": [
        "mae", "mãe", "pai", "filho", "filha", "irmao", "irmã",
        "irmão", "irma", "esposo", "esposa", "marido", "mulher",
        "namorado", "namorada", "ex", "sogra", "sogro", "neto", "neta",
        "avo", "avó", "avô", "familia", "família", "familiar",
        "casamento", "divorcio", "divórcio", "separacao", "separação",
        "gravidez", "gestacao", "gestação", "aborto", "luto",
    ],
    "elementos_alquimicos": [
        "nigredo", "albedo", "citrinitas", "rubedo",
        "chumbo", "ouro", "mercurio", "mercúrio", "enxofre", "sal",
        "sombra", "anima", "animus", "self", "persona", "ego",
        "inconsciente", "arquetipo", "arquétipo", "individuacao",
        "individuação", "transmutacao", "transmutação", "opus",
        "prima materia", "lapis", "pedra filosofal",
    ],
}

# Intervalo de turnos para pedir confirmacao do paciente
TURNOS_PARA_CONFIRMACAO = 5


# =============================================================================
# CLASSE PRINCIPAL: SESSAO DO PACIENTE
# =============================================================================

@dataclass
class SessaoPaciente:
    """
    Mantém os dados de uma sessao sobre um paciente especifico.
    Cada paciente tem sua propria sessao com dados isolados.
    """
    nome_paciente: str
    dados_coletados: dict = field(default_factory=lambda: {
        "sintomas": [],
        "florais": [],
        "cartas": [],
        "dados_nascimento": [],
        "informacoes_familiares": [],
        "elementos_alquimicos": [],
        "observacoes_livres": [],
    })
    diagnostico_parcial: str = ""
    turno: int = 0
    confirmado: bool = False
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat())
    ultima_interacao: str = field(default_factory=lambda: datetime.now().isoformat())

    def registrar_turno(self):
        """Incrementa o contador de turnos e atualiza timestamp."""
        self.turno += 1
        self.ultima_interacao = datetime.now().isoformat()

    def precisa_confirmacao(self) -> bool:
        """Verifica se esta na hora de confirmar que ainda falam do mesmo paciente."""
        return (
            self.turno > 0
            and self.turno % TURNOS_PARA_CONFIRMACAO == 0
            and self.confirmado  # So pede re-confirmacao se ja foi confirmado antes
        )

    def confirmar(self):
        """Marca o paciente como confirmado pelo terapeuta."""
        self.confirmado = True

    def resumo_dados(self) -> str:
        """Retorna um resumo legivel dos dados coletados ate agora."""
        partes = []
        partes.append(f"Paciente: {self.nome_paciente}")
        partes.append(f"Turnos de conversa: {self.turno}")

        for categoria, itens in self.dados_coletados.items():
            if itens:
                nome_formatado = categoria.replace("_", " ").title()
                # Remove duplicatas mantendo ordem
                unicos = list(dict.fromkeys(itens))
                partes.append(f"{nome_formatado}: {', '.join(unicos)}")

        if self.diagnostico_parcial:
            partes.append(f"Diagnostico parcial: {self.diagnostico_parcial}")

        return "\n".join(partes)

    def to_dict(self) -> dict:
        """Serializa a sessao para armazenamento."""
        return {
            "nome_paciente": self.nome_paciente,
            "dados_coletados": self.dados_coletados,
            "diagnostico_parcial": self.diagnostico_parcial,
            "turno": self.turno,
            "confirmado": self.confirmado,
            "criado_em": self.criado_em,
            "ultima_interacao": self.ultima_interacao,
        }

    @classmethod
    def from_dict(cls, dados: dict) -> "SessaoPaciente":
        """Reconstroi a sessao a partir de um dict."""
        return cls(
            nome_paciente=dados["nome_paciente"],
            dados_coletados=dados.get("dados_coletados", {}),
            diagnostico_parcial=dados.get("diagnostico_parcial", ""),
            turno=dados.get("turno", 0),
            confirmado=dados.get("confirmado", False),
            criado_em=dados.get("criado_em", datetime.now().isoformat()),
            ultima_interacao=dados.get("ultima_interacao", datetime.now().isoformat()),
        )


# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

def detectar_troca_paciente(mensagem: str, sessao_atual: Optional[SessaoPaciente]) -> bool:
    """
    Detecta se o terapeuta esta trocando de paciente.

    Retorna True se:
    - A mensagem contem palavras-chave de troca de paciente
    - Nao ha sessao atual (primeiro paciente)

    Args:
        mensagem: Texto da mensagem do terapeuta
        sessao_atual: Sessao do paciente atual (None se nao ha paciente)

    Returns:
        True se detectou troca de paciente, False se continua o mesmo caso
    """
    if sessao_atual is None:
        return True

    msg_lower = mensagem.lower().strip()

    # Verifica palavras-chave de troca
    for palavra in PALAVRAS_TROCA_PACIENTE:
        if palavra in msg_lower:
            logger.info(f"[PACIENTE] Troca detectada por palavra-chave: '{palavra}'")
            return True

    return False


def extrair_nome_paciente(mensagem: str) -> Optional[str]:
    """
    Tenta extrair o nome do paciente da mensagem.

    Args:
        mensagem: Texto da mensagem do terapeuta

    Returns:
        Nome do paciente se encontrado, None caso contrario
    """
    for padrao in PADROES_NOME_PACIENTE:
        match = re.search(padrao, mensagem)
        if match:
            nome = match.group(1).strip()
            # Filtrar nomes muito curtos ou palavras comuns
            if len(nome) >= 3 and nome.lower() not in [
                "que", "com", "uma", "tem", "ela", "ele", "isso",
                "aqui", "ali", "sim", "nao", "muito", "mais",
            ]:
                logger.info(f"[PACIENTE] Nome extraido: '{nome}'")
                return nome

    return None


def gerar_confirmacao_paciente(nome: str) -> str:
    """
    Gera mensagem pedindo confirmacao de que ainda falam do mesmo paciente.

    Args:
        nome: Nome do paciente atual

    Returns:
        Texto da mensagem de confirmacao
    """
    return (
        f"Ainda estamos falando sobre {nome}? "
        "Quero garantir que estou montando o diagnóstico certo."
    )


def gerar_pedido_nome_paciente() -> str:
    """
    Gera mensagem pedindo o nome do paciente quando nao consegue extrair.

    Returns:
        Texto da mensagem pedindo o nome
    """
    return (
        "Para organizar melhor o caso, como se chama esse paciente? "
        "Assim consigo manter o histórico separado certinho."
    )


def extrair_dados_caso(mensagem: str, dados_existentes: dict) -> dict:
    """
    Extrai dados clinicos de cada mensagem e acumula nos dados existentes.

    Analisa a mensagem buscando:
    - Sintomas mencionados
    - Florais mencionados
    - Cartas de taro mencionadas
    - Dados de nascimento
    - Informacoes familiares
    - Elementos alquimicos

    Args:
        mensagem: Texto da mensagem do terapeuta
        dados_existentes: Dict com dados ja coletados do paciente

    Returns:
        Dict atualizado com novos dados encontrados
    """
    msg_lower = mensagem.lower()

    for categoria, termos in CATEGORIAS_DADOS.items():
        if categoria not in dados_existentes:
            dados_existentes[categoria] = []

        for termo in termos:
            # Se o termo e um regex (dados_nascimento), usa re.search
            if termo.startswith(r"\d") or termo.startswith("r\""):
                try:
                    match = re.search(termo, mensagem, re.IGNORECASE)
                    if match:
                        valor = match.group(0)
                        if valor not in dados_existentes[categoria]:
                            dados_existentes[categoria].append(valor)
                            logger.debug(
                                f"[PACIENTE] Dado extraido [{categoria}]: '{valor}'"
                            )
                except re.error:
                    pass
            else:
                # Busca simples por substring
                if termo.lower() in msg_lower:
                    if termo.lower() not in [t.lower() for t in dados_existentes[categoria]]:
                        dados_existentes[categoria].append(termo)
                        logger.debug(
                            f"[PACIENTE] Dado extraido [{categoria}]: '{termo}'"
                        )

    return dados_existentes


def formatar_contexto_paciente(sessao: SessaoPaciente) -> str:
    """
    Formata os dados da sessao do paciente como contexto personalizado
    para ser passado ao generator (via contexto_personalizado).

    Args:
        sessao: Sessao do paciente atual

    Returns:
        Texto formatado com o contexto do paciente para o prompt
    """
    partes = []
    partes.append("=" * 50)
    partes.append("CONTEXTO DO PACIENTE ATUAL")
    partes.append("=" * 50)
    partes.append(f"Nome: {sessao.nome_paciente}")
    partes.append(f"Turno da conversa: {sessao.turno}")

    if not sessao.confirmado:
        partes.append("Status: AGUARDANDO CONFIRMACAO DO TERAPEUTA")

    # Dados coletados ate agora
    dados_preenchidos = False
    for categoria, itens in sessao.dados_coletados.items():
        if itens:
            dados_preenchidos = True
            nome_formatado = categoria.replace("_", " ").title()
            unicos = list(dict.fromkeys(itens))
            partes.append(f"\n{nome_formatado}:")
            for item in unicos:
                partes.append(f"  - {item}")

    if not dados_preenchidos:
        partes.append("\nFase: INVESTIGACAO INICIAL")
        partes.append(
            "Instrucao: Faca perguntas investigativas antes de sugerir qualquer tratamento."
        )
        partes.append(
            "Pergunte sobre sintomas, historico familiar, eventos recentes, "
            "e qualquer dado relevante antes de iniciar a analise."
        )
    else:
        partes.append(f"\nDiagnostico parcial: {sessao.diagnostico_parcial or 'Em construcao'}")
        if sessao.turno < 3:
            partes.append(
                "Instrucao: Continue investigando. Ha poucos dados ainda. "
                "Faca mais perguntas antes de sugerir tratamento."
            )

    partes.append("=" * 50)
    return "\n".join(partes)


# =============================================================================
# GERENCIADOR DE SESSOES (por sessao de chat)
# =============================================================================

class GerenciadorPacientes:
    """
    Gerencia as sessoes de pacientes para uma sessao de chat.
    Cada sessao de chat pode ter multiplos pacientes ao longo do tempo.
    """

    def __init__(self):
        # Paciente ativo por session_id
        self._sessoes_ativas: dict[str, SessaoPaciente] = {}
        # Historico de todos os pacientes por session_id
        self._historico_pacientes: dict[str, list[dict]] = {}

    def get_sessao_ativa(self, session_id: str) -> Optional[SessaoPaciente]:
        """Retorna a sessao ativa do paciente para esta sessao de chat."""
        return self._sessoes_ativas.get(session_id)

    def criar_sessao(self, session_id: str, nome_paciente: str) -> SessaoPaciente:
        """
        Cria nova sessao para um paciente, salvando a anterior no historico.

        Args:
            session_id: ID da sessao de chat
            nome_paciente: Nome do novo paciente

        Returns:
            Nova SessaoPaciente criada
        """
        # Salvar sessao anterior no historico
        sessao_anterior = self._sessoes_ativas.get(session_id)
        if sessao_anterior:
            self._salvar_no_historico(session_id, sessao_anterior)

        # Criar nova sessao
        nova_sessao = SessaoPaciente(nome_paciente=nome_paciente)
        self._sessoes_ativas[session_id] = nova_sessao
        logger.info(
            f"[PACIENTE] Nova sessao criada para '{nome_paciente}' "
            f"(session_id={session_id})"
        )
        return nova_sessao

    def _salvar_no_historico(self, session_id: str, sessao: SessaoPaciente):
        """Salva uma sessao encerrada no historico."""
        if session_id not in self._historico_pacientes:
            self._historico_pacientes[session_id] = []

        self._historico_pacientes[session_id].append(sessao.to_dict())
        logger.info(
            f"[PACIENTE] Sessao de '{sessao.nome_paciente}' salva no historico "
            f"(session_id={session_id}, turnos={sessao.turno})"
        )

    def get_historico_pacientes(self, session_id: str) -> list[dict]:
        """Retorna o historico de todos os pacientes da sessao."""
        return self._historico_pacientes.get(session_id, [])

    def limpar_sessao(self, session_id: str):
        """Limpa a sessao ativa e o historico de pacientes."""
        # Salvar sessao ativa antes de limpar
        sessao_ativa = self._sessoes_ativas.pop(session_id, None)
        if sessao_ativa:
            self._salvar_no_historico(session_id, sessao_ativa)

        # Manter historico, so limpa sessao ativa
        logger.info(f"[PACIENTE] Sessao limpa (session_id={session_id})")

    def processar_mensagem(
        self, session_id: str, mensagem: str
    ) -> tuple[SessaoPaciente, Optional[str]]:
        """
        Processa uma mensagem e retorna a sessao atualizada + mensagem de sistema (se houver).

        Logica:
        1. Se nao ha sessao ativa -> tenta criar uma
        2. Se detecta troca de paciente -> salva anterior, cria nova
        3. Se precisa confirmacao -> gera mensagem de confirmacao
        4. Sempre extrai dados da mensagem

        Args:
            session_id: ID da sessao de chat
            mensagem: Texto da mensagem do terapeuta

        Returns:
            Tupla (sessao_atualizada, mensagem_sistema_ou_None)
        """
        sessao_atual = self.get_sessao_ativa(session_id)
        mensagem_sistema = None

        # Detectar se e troca de paciente
        eh_troca = detectar_troca_paciente(mensagem, sessao_atual)

        if eh_troca:
            # Tentar extrair nome do paciente
            nome = extrair_nome_paciente(mensagem)

            if nome:
                sessao_atual = self.criar_sessao(session_id, nome)
                sessao_atual.confirmar()  # Nome foi extraido, considerar confirmado
            else:
                if sessao_atual is None:
                    # Primeira interacao, sem nome detectado
                    sessao_atual = self.criar_sessao(session_id, "Paciente (nome pendente)")
                    mensagem_sistema = gerar_pedido_nome_paciente()
                else:
                    # Troca detectada mas sem nome
                    sessao_atual = self.criar_sessao(session_id, "Paciente (nome pendente)")
                    mensagem_sistema = gerar_pedido_nome_paciente()

        # Se a mensagem parece ser uma resposta com o nome do paciente
        if sessao_atual and sessao_atual.nome_paciente == "Paciente (nome pendente)":
            nome = extrair_nome_paciente(mensagem)
            if not nome:
                # Tenta capturar nome simples (resposta direta com so o nome)
                msg_limpa = mensagem.strip()
                if (
                    len(msg_limpa.split()) <= 3
                    and msg_limpa[0:1].isupper()
                    and len(msg_limpa) >= 3
                ):
                    nome = msg_limpa.split()[0]

            if nome:
                sessao_atual.nome_paciente = nome
                sessao_atual.confirmar()
                logger.info(f"[PACIENTE] Nome atualizado para '{nome}'")
                mensagem_sistema = None  # Cancela pedido de nome

        # Extrair dados da mensagem
        if sessao_atual:
            sessao_atual.dados_coletados = extrair_dados_caso(
                mensagem, sessao_atual.dados_coletados
            )
            sessao_atual.registrar_turno()

            # Verificar se precisa confirmar paciente (a cada N turnos)
            if sessao_atual.precisa_confirmacao() and mensagem_sistema is None:
                mensagem_sistema = gerar_confirmacao_paciente(sessao_atual.nome_paciente)

        return sessao_atual, mensagem_sistema


# Instancia global do gerenciador (usada em teste.py e webhook.py)
gerenciador_pacientes = GerenciadorPacientes()
