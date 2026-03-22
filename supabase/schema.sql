-- =============================================================
-- Schema do banco de dados — Terapeutas Agent
-- Executar diretamente no Supabase SQL Editor
-- =============================================================

-- Extensão pgvector para busca vetorial
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================
-- Tabela: terapeutas (multi-tenant — cada terapeuta é um tenant)
-- =============================================================
CREATE TABLE terapeutas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  telefone TEXT,                                    -- código Python usa 'telefone' (não 'telefone_whatsapp')
  especialidade TEXT,
  nome_agente TEXT DEFAULT 'Assistente',            -- nome do agente no WhatsApp (schemas.py / terapeutas.py)
  contato_agendamento TEXT,
  horario_atendimento TEXT DEFAULT '09:00-18:00',
  evolution_instance TEXT,
  tom_de_voz TEXT DEFAULT 'profissional e acolhedor', -- valor padrão alinhado com schemas.py
  whatsapp_conectado BOOLEAN DEFAULT false,         -- flag de conexão WhatsApp (terapeutas.py insere)
  ativo BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now(),
  atualizado_em TIMESTAMPTZ DEFAULT now()
);

-- =============================================================
-- Tabela: documentos (PDFs e materiais do terapeuta)
-- =============================================================
CREATE TABLE documentos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  nome_arquivo TEXT NOT NULL,
  tipo TEXT DEFAULT 'pdf',                          -- tipo do arquivo (documentos.py insere 'pdf')
  tamanho_bytes BIGINT DEFAULT 0,                   -- tamanho em bytes (documentos.py insere)
  storage_path TEXT,
  total_chunks INT DEFAULT 0,
  processado BOOLEAN DEFAULT false,                 -- documentos.py insere processado=False
  status TEXT DEFAULT 'processando' CHECK (status IN ('processando', 'ativo', 'erro')), -- processor.py atualiza status
  erro_processamento TEXT,                          -- processor.py usa 'erro_processamento' (não 'erro_detalhe')
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- =============================================================
-- Tabela: embeddings (chunks vetoriais dos documentos)
-- =============================================================
CREATE TABLE embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  documento_id UUID REFERENCES documentos(id) ON DELETE CASCADE,
  conteudo TEXT NOT NULL,
  embedding vector(1536),
  chunk_index INT DEFAULT 0,                        -- índice sequencial do chunk no documento (processor.py insere)
  metadata JSONB DEFAULT '{}',
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- =============================================================
-- Tabela: conversas (histórico de mensagens WhatsApp)
-- =============================================================
CREATE TABLE conversas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  paciente_numero TEXT NOT NULL,
  mensagem_paciente TEXT,
  resposta_agente TEXT,
  intencao TEXT,
  chunks_usados JSONB DEFAULT '[]',
  tempo_resposta_ms INT,
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- =============================================================
-- Índices para performance
-- =============================================================

-- Índice vetorial (busca por similaridade de cosseno)
CREATE INDEX idx_embeddings_vector ON embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Índices por terapeuta (isolamento multi-tenant)
CREATE INDEX idx_embeddings_terapeuta ON embeddings(terapeuta_id);
CREATE INDEX idx_documentos_terapeuta ON documentos(terapeuta_id);
CREATE INDEX idx_conversas_terapeuta ON conversas(terapeuta_id);

-- =============================================================
-- Função de busca vetorial (RAG)
-- Retorna os N chunks mais similares para um terapeuta
-- =============================================================
CREATE OR REPLACE FUNCTION buscar_chunks(
  query_embedding vector(1536),
  p_terapeuta_id UUID,                              -- retriever.py passa 'p_terapeuta_id' (não 'terapeuta_uuid')
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  conteudo TEXT,
  similaridade FLOAT,                               -- retriever.py espera 'similaridade' (não 'similarity')
  documento_id UUID,                                -- retriever.py lê chunk["documento_id"]
  chunk_index INT                                   -- retriever.py lê chunk["chunk_index"]
)
LANGUAGE SQL STABLE
AS $$
  SELECT
    e.id,
    e.conteudo,
    1 - (e.embedding <=> query_embedding) AS similaridade,
    e.documento_id,
    e.chunk_index
  FROM embeddings e
  WHERE e.terapeuta_id = p_terapeuta_id
  ORDER BY e.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- =============================================================
-- Row Level Security (RLS)
-- Backend usa service_role com acesso total
-- =============================================================
ALTER TABLE terapeutas ENABLE ROW LEVEL SECURITY;
ALTER TABLE documentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversas ENABLE ROW LEVEL SECURITY;

-- Políticas: service_role tem acesso total (usado pelo backend FastAPI)
CREATE POLICY "Service role full access" ON terapeutas FOR ALL USING (true);
CREATE POLICY "Service role full access" ON documentos FOR ALL USING (true);
CREATE POLICY "Service role full access" ON embeddings FOR ALL USING (true);
CREATE POLICY "Service role full access" ON conversas FOR ALL USING (true);
