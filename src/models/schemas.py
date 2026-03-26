"""
Schemas Pydantic para validação de dados em toda a aplicação.
Inclui modelos para terapeutas, documentos, mensagens WhatsApp e RAG.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, EmailStr


# =============================================
# TERAPEUTA
# =============================================

class TerapeutaCreate(BaseModel):
    """Dados para criar um novo terapeuta."""
    nome: str = Field(..., min_length=2, max_length=200, description="Nome completo do terapeuta")
    email: EmailStr = Field(..., description="Email do terapeuta")
    telefone: str = Field(..., min_length=10, max_length=20, description="Telefone com DDD")
    especialidade: str | None = Field(None, max_length=200, description="Especialidade (ex: TCC, Psicanálise)")
    # Configurações do agente
    nome_agente: str = Field(default="Assistente", max_length=100, description="Nome do agente no WhatsApp")
    tom_de_voz: str = Field(
        default="profissional e acolhedor",
        max_length=500,
        description="Tom de voz do agente nas respostas",
    )


class TerapeutaResponse(BaseModel):
    """Dados retornados ao consultar um terapeuta."""
    id: UUID
    nome: str
    email: str
    telefone: str
    especialidade: str | None = None
    nome_agente: str
    tom_de_voz: str
    whatsapp_conectado: bool = False
    nivel_acesso: int = 1
    ativo: bool = True
    criado_em: datetime
    atualizado_em: datetime


# =============================================
# DOCUMENTO (PDFs e materiais do terapeuta)
# =============================================

class DocumentoCreate(BaseModel):
    """Dados para registrar um novo documento enviado pelo terapeuta."""
    terapeuta_id: UUID = Field(..., description="ID do terapeuta dono do documento")
    nome_arquivo: str = Field(..., max_length=500, description="Nome original do arquivo")
    tipo: str = Field(default="pdf", max_length=50, description="Tipo do arquivo (pdf, txt, etc)")
    tamanho_bytes: int = Field(..., ge=0, description="Tamanho do arquivo em bytes")
    storage_path: str = Field(..., description="Caminho no Supabase Storage")


class DocumentoResponse(BaseModel):
    """Dados retornados ao consultar um documento."""
    id: UUID
    terapeuta_id: UUID
    nome_arquivo: str
    tipo: str
    tamanho_bytes: int
    storage_path: str
    total_chunks: int = 0
    status: str = "pendente"
    criado_em: datetime


# =============================================
# MENSAGEM WHATSAPP (webhook da Evolution API)
# =============================================

class MensagemWhatsAppKey(BaseModel):
    """Chave identificadora da mensagem na Evolution API."""
    remoteJid: str = Field(..., description="JID do remetente (numero@s.whatsapp.net)")
    fromMe: bool = Field(default=False, description="Se a mensagem foi enviada por nós")
    id: str = Field(..., description="ID único da mensagem")


class MensagemWhatsAppData(BaseModel):
    """Dados da mensagem recebida pela Evolution API."""
    key: MensagemWhatsAppKey
    pushName: str | None = Field(None, description="Nome do contato no WhatsApp")
    message: dict = Field(default_factory=dict, description="Conteúdo da mensagem (varia por tipo)")
    messageType: str | None = Field(None, description="Tipo da mensagem (conversation, extendedTextMessage, etc)")
    messageTimestamp: int | None = Field(None, description="Timestamp Unix da mensagem")


class MensagemWhatsApp(BaseModel):
    """
    Payload completo do webhook da Evolution API.
    Recebido quando uma mensagem chega no WhatsApp conectado.
    """
    event: str = Field(..., description="Tipo do evento (messages.upsert, etc)")
    instance: str = Field(..., description="Nome da instância Evolution API")
    data: MensagemWhatsAppData
    destination: str | None = Field(None, description="Número destino")
    server_url: str | None = Field(None, description="URL do servidor Evolution")


# =============================================
# RAG (Retrieval-Augmented Generation)
# =============================================

class ChunkEmbedding(BaseModel):
    """Chunk de texto com seu embedding para armazenar no pgvector."""
    id: UUID = Field(default_factory=uuid4, description="ID único do chunk")
    terapeuta_id: UUID = Field(..., description="ID do terapeuta dono do conteúdo")
    documento_id: UUID = Field(..., description="ID do documento de origem")
    conteudo: str = Field(..., description="Texto do chunk")
    embedding: list[float] = Field(..., description="Vetor de embedding (1536 dimensões)")
    metadata: dict = Field(default_factory=dict, description="Metadados adicionais (página, posição, etc)")


class RespostaAgente(BaseModel):
    """Resposta gerada pelo agente para enviar ao paciente."""
    terapeuta_id: UUID = Field(..., description="ID do terapeuta cujo agente respondeu")
    paciente_telefone: str = Field(..., description="Telefone do paciente")
    pergunta: str = Field(..., description="Pergunta original do paciente")
    resposta: str = Field(..., description="Resposta gerada pelo agente")
    chunks_usados: list[str] = Field(default_factory=list, description="IDs dos chunks usados como contexto")
    confianca: float = Field(default=0.0, ge=0.0, le=1.0, description="Score de confiança da resposta")
    modelo_usado: str = Field(default="claude-sonnet-4-6", description="Modelo de IA utilizado")
    tokens_entrada: int = Field(default=0, description="Tokens consumidos no prompt")
    tokens_saida: int = Field(default=0, description="Tokens consumidos na resposta")
    criado_em: datetime = Field(default_factory=datetime.utcnow, description="Timestamp da resposta")
