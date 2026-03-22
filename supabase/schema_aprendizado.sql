-- =============================================================
-- Schema de Aprendizado Continuo — Terapeutas Agent
-- Executar no Supabase SQL Editor APOS o schema.sql principal
-- =============================================================

-- Tabela de feedback: terapeuta avalia respostas do agente
CREATE TABLE feedback_respostas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  conversa_id UUID REFERENCES conversas(id),
  avaliacao INT CHECK (avaliacao BETWEEN 1 AND 5), -- 1=ruim, 5=excelente
  comentario TEXT, -- feedback livre da terapeuta
  tipo TEXT CHECK (tipo IN ('consulta', 'conteudo', 'pesquisa')),
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- Tabela de padroes aprendidos: o sistema detecta padroes de uso
CREATE TABLE padroes_terapeuta (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL, -- 'pergunta_frequente', 'tema_recorrente', 'estilo_preferido', 'floral_mais_indicado'
  chave TEXT NOT NULL, -- o padrao em si (ex: "ansiedade", "elemento fogo")
  valor TEXT, -- detalhes
  frequencia INT DEFAULT 1, -- quantas vezes apareceu
  ultima_ocorrencia TIMESTAMPTZ DEFAULT now(),
  criado_em TIMESTAMPTZ DEFAULT now(),
  UNIQUE(terapeuta_id, tipo, chave)
);

-- Tabela de contexto acumulado: memoria de longo prazo por terapeuta
CREATE TABLE contexto_terapeuta (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL, -- 'especialidade', 'publico_alvo', 'tom_preferido', 'temas_dominados', 'nivel_maturidade'
  conteudo TEXT NOT NULL,
  atualizado_em TIMESTAMPTZ DEFAULT now(),
  UNIQUE(terapeuta_id, tipo)
);

-- =============================================================
-- Indices para performance
-- =============================================================
CREATE INDEX idx_feedback_terapeuta ON feedback_respostas(terapeuta_id);
CREATE INDEX idx_feedback_conversa ON feedback_respostas(conversa_id);
CREATE INDEX idx_padroes_terapeuta ON padroes_terapeuta(terapeuta_id);
CREATE INDEX idx_padroes_tipo_chave ON padroes_terapeuta(terapeuta_id, tipo, chave);
CREATE INDEX idx_contexto_terapeuta ON contexto_terapeuta(terapeuta_id);

-- =============================================================
-- Row Level Security (RLS)
-- Backend usa service_role com acesso total
-- =============================================================
ALTER TABLE feedback_respostas ENABLE ROW LEVEL SECURITY;
ALTER TABLE padroes_terapeuta ENABLE ROW LEVEL SECURITY;
ALTER TABLE contexto_terapeuta ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON feedback_respostas FOR ALL USING (true);
CREATE POLICY "Service role full access" ON padroes_terapeuta FOR ALL USING (true);
CREATE POLICY "Service role full access" ON contexto_terapeuta FOR ALL USING (true);
