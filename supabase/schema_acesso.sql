-- =============================================================
-- Migration: Controle de Acesso e Moderação de Conteúdo
-- Executar no Supabase SQL Editor APÓS schema.sql principal
-- =============================================================

-- =============================================================
-- Tabela: chat_estado
-- Rastreia o estado de cada número de telefone por terapeuta.
-- Estados: PENDENTE_CODIGO → ATIVO → BLOQUEADO
-- =============================================================
CREATE TABLE IF NOT EXISTS chat_estado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Multi-tenant: cada terapeuta tem seu próprio namespace
  terapeuta_id UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,

  -- Número do WhatsApp do usuário (formato internacional: 5511999999999)
  numero_telefone TEXT NOT NULL,

  -- Máquina de estados:
  -- PENDENTE_CODIGO: aguardando o código de liberação (estado inicial)
  -- ATIVO: acesso confirmado, chat normal
  -- BLOQUEADO: 3 violações de conteúdo, acesso suspenso
  estado TEXT NOT NULL DEFAULT 'PENDENTE_CODIGO'
    CHECK (estado IN ('PENDENTE_CODIGO', 'ATIVO', 'BLOQUEADO')),

  -- Nome que o usuário informou após desbloquear (NULL até ser coletado)
  nome_usuario TEXT,

  -- Código que foi usado para liberar o acesso (auditoria)
  codigo_usado TEXT,

  -- Contador de violações de conteúdo (0, 1, 2, 3+ → bloqueia)
  violacoes_conteudo INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Unicidade: um número tem apenas um estado por terapeuta
  UNIQUE (terapeuta_id, numero_telefone)
);

CREATE INDEX IF NOT EXISTS idx_chat_estado_lookup
  ON chat_estado (terapeuta_id, numero_telefone);

CREATE INDEX IF NOT EXISTS idx_chat_estado_estado
  ON chat_estado (estado);

-- =============================================================
-- Tabela: codigos_liberacao
-- Códigos de acesso cadastrados pelo terapeuta.
-- Suporta códigos reutilizáveis (turma) e de uso único (individual).
-- =============================================================
CREATE TABLE IF NOT EXISTS codigos_liberacao (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Multi-tenant
  terapeuta_id UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,

  -- O código em si (validação é case-insensitive)
  codigo TEXT NOT NULL,

  -- Descrição interna (ex: "Turma Janeiro 2026", "Cliente VIP - Ana")
  descricao TEXT,

  -- TRUE = ilimitado (compartilhado em turma); FALSE = uso único
  reutilizavel BOOLEAN NOT NULL DEFAULT true,

  -- Apenas relevante quando reutilizavel=FALSE
  usado BOOLEAN NOT NULL DEFAULT false,
  usado_por TEXT,       -- número que usou
  usado_em TIMESTAMPTZ, -- quando usou

  -- Permite desativar sem deletar
  ativo BOOLEAN NOT NULL DEFAULT true,

  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (terapeuta_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_codigos_liberacao_lookup
  ON codigos_liberacao (terapeuta_id, codigo, ativo);

-- =============================================================
-- Seed: Inserir código de teste para o terapeuta Joel Aleixo
-- ATENÇÃO: substituir o UUID pelo ID real do terapeuta em produção
-- O ID abaixo é o do Joel Aleixo conforme memory do projeto.
-- =============================================================
INSERT INTO codigos_liberacao (terapeuta_id, codigo, descricao, reutilizavel)
VALUES (
  '5085ff75-fe00-49fe-95f4-a5922a0cf179',
  'eu quero testar',
  'Código de teste universal (case-insensitive, reutilizável)',
  true
)
ON CONFLICT (terapeuta_id, codigo) DO NOTHING;

-- =============================================================
-- RLS (Row Level Security)
-- Backend usa service_role com acesso total
-- =============================================================
ALTER TABLE chat_estado ENABLE ROW LEVEL SECURITY;
ALTER TABLE codigos_liberacao ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'chat_estado' AND policyname = 'Service role full access'
  ) THEN
    CREATE POLICY "Service role full access" ON chat_estado FOR ALL USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'codigos_liberacao' AND policyname = 'Service role full access'
  ) THEN
    CREATE POLICY "Service role full access" ON codigos_liberacao FOR ALL USING (true);
  END IF;
END $$;
