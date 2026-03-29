-- ============================================================
-- Portal do Terapeuta — Schema
-- Tabelas para o ecossistema web de gestão da prática clínica
-- ============================================================

-- ── 1. AUTENTICAÇÃO DO PORTAL ─────────────────────────────
CREATE TABLE IF NOT EXISTS portal_auth (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id      UUID NOT NULL UNIQUE REFERENCES terapeutas(id) ON DELETE CASCADE,
  senha_hash        TEXT NOT NULL,
  ultimo_login      TIMESTAMPTZ,
  tentativas_falhas INT DEFAULT 0,
  bloqueado_ate     TIMESTAMPTZ,
  token_reset       TEXT,
  token_reset_exp   TIMESTAMPTZ,
  primeiro_login    BOOLEAN DEFAULT true,
  criado_em         TIMESTAMPTZ DEFAULT now(),
  atualizado_em     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_portal_auth_terapeuta ON portal_auth(terapeuta_id);

-- ── 2. PACIENTES ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pacientes (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id                UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,
  numero_telefone             TEXT NOT NULL,
  nome                        TEXT NOT NULL,
  email                       TEXT,
  data_nascimento             DATE,
  hora_nascimento             TIME,
  cidade_nascimento           TEXT,
  genero                      TEXT,
  foto_url                    TEXT,
  status                      TEXT NOT NULL DEFAULT 'ativo'
                              CHECK (status IN ('ativo', 'inativo', 'arquivado')),
  tags                        TEXT[] DEFAULT '{}',
  notas_gerais                TEXT,
  data_inicio_acompanhamento  DATE,
  ultima_sessao_em            TIMESTAMPTZ,
  criado_em                   TIMESTAMPTZ DEFAULT now(),
  atualizado_em               TIMESTAMPTZ DEFAULT now(),
  UNIQUE (terapeuta_id, numero_telefone)
);

CREATE INDEX IF NOT EXISTS idx_pacientes_terapeuta    ON pacientes(terapeuta_id);
CREATE INDEX IF NOT EXISTS idx_pacientes_status       ON pacientes(terapeuta_id, status);
CREATE INDEX IF NOT EXISTS idx_pacientes_tags         ON pacientes USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_pacientes_nome         ON pacientes(terapeuta_id, nome);

-- ── 3. DIAGNÓSTICOS ALQUÍMICOS ────────────────────────────
CREATE TABLE IF NOT EXISTS diagnosticos_alquimicos (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id          UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,
  paciente_id           UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,

  -- Elementos
  elemento_dominante    TEXT,
  elemento_carente      TEXT,
  elementos_detalhes    JSONB DEFAULT '{}',

  -- DNA Alquímico
  dna_comprometido      TEXT[] DEFAULT '{}',
  dna_descricao         TEXT,

  -- Serpentes
  serpentes_ativas      TEXT[] DEFAULT '{}',
  serpentes_descricao   TEXT,

  -- Setenio
  setenio_atual         INT CHECK (setenio_atual BETWEEN 1 AND 9),
  setenio_descricao     TEXT,

  -- Protocolo terapêutico
  florais_prescritos    TEXT[] DEFAULT '{}',
  protocolo_texto       TEXT,

  -- Metadados
  sessao_data           DATE NOT NULL DEFAULT CURRENT_DATE,
  fonte                 TEXT DEFAULT 'manual'
                        CHECK (fonte IN ('manual', 'whatsapp_auto')),
  conversa_origem_id    UUID,
  status                TEXT DEFAULT 'rascunho'
                        CHECK (status IN ('rascunho', 'finalizado', 'arquivado')),
  criado_em             TIMESTAMPTZ DEFAULT now(),
  atualizado_em         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_diagnosticos_paciente  ON diagnosticos_alquimicos(paciente_id);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_terapeuta ON diagnosticos_alquimicos(terapeuta_id, sessao_data DESC);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_status    ON diagnosticos_alquimicos(terapeuta_id, status);

-- ── 4. ANOTAÇÕES DO PRONTUÁRIO ────────────────────────────
CREATE TABLE IF NOT EXISTS anotacoes_prontuario (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id    UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,
  paciente_id     UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
  tipo            TEXT DEFAULT 'sessao'
                  CHECK (tipo IN ('sessao', 'observacao', 'tarefa', 'lembrete', 'evolucao')),
  titulo          TEXT,
  conteudo        TEXT NOT NULL,
  data_anotacao   DATE NOT NULL DEFAULT CURRENT_DATE,
  proxima_sessao  DATE,
  privada         BOOLEAN DEFAULT false,
  criado_em       TIMESTAMPTZ DEFAULT now(),
  atualizado_em   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_anotacoes_paciente  ON anotacoes_prontuario(paciente_id, data_anotacao DESC);
CREATE INDEX IF NOT EXISTS idx_anotacoes_terapeuta ON anotacoes_prontuario(terapeuta_id);

-- ── 5. ACOMPANHAMENTOS ────────────────────────────────────
CREATE TABLE IF NOT EXISTS acompanhamentos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id    UUID NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,
  paciente_id     UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
  tipo            TEXT DEFAULT 'retorno'
                  CHECK (tipo IN ('retorno', 'floral', 'tarefa', 'contato', 'marco')),
  descricao       TEXT NOT NULL,
  data_prevista   DATE,
  data_realizado  DATE,
  status          TEXT DEFAULT 'pendente'
                  CHECK (status IN ('pendente', 'realizado', 'cancelado', 'adiado')),
  prioridade      INT DEFAULT 2 CHECK (prioridade IN (1, 2, 3)),
  criado_em       TIMESTAMPTZ DEFAULT now(),
  atualizado_em   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_acompanhamentos_pendentes ON acompanhamentos(terapeuta_id, status, data_prevista);
CREATE INDEX IF NOT EXISTS idx_acompanhamentos_paciente  ON acompanhamentos(paciente_id);

-- ── RLS ───────────────────────────────────────────────────
ALTER TABLE portal_auth          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pacientes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosticos_alquimicos ENABLE ROW LEVEL SECURITY;
ALTER TABLE anotacoes_prontuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE acompanhamentos      ENABLE ROW LEVEL SECURITY;

-- service_role tem acesso total (FastAPI usa service_role)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='portal_auth' AND policyname='service_role_portal_auth') THEN
    CREATE POLICY service_role_portal_auth ON portal_auth FOR ALL USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='pacientes' AND policyname='service_role_pacientes') THEN
    CREATE POLICY service_role_pacientes ON pacientes FOR ALL USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='diagnosticos_alquimicos' AND policyname='service_role_diagnosticos') THEN
    CREATE POLICY service_role_diagnosticos ON diagnosticos_alquimicos FOR ALL USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='anotacoes_prontuario' AND policyname='service_role_anotacoes') THEN
    CREATE POLICY service_role_anotacoes ON anotacoes_prontuario FOR ALL USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='acompanhamentos' AND policyname='service_role_acompanhamentos') THEN
    CREATE POLICY service_role_acompanhamentos ON acompanhamentos FOR ALL USING (true);
  END IF;
END $$;
