-- ============================================================
-- Mapas Astrais — Cache permanente dos mapas natais gerados
-- Vincula terapeuta + paciente + dados de nascimento ao JSON
-- completo do Swiss Ephemeris (Kerykeion).
--
-- Benefícios:
--   • Evita recalcular o mesmo mapa múltiplas vezes
--   • Alimenta a galeria de mapas no Portal do Terapeuta
--   • Permite leituras follow-up sem re-envio dos dados
-- ============================================================

CREATE TABLE IF NOT EXISTS mapas_astrais (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id      UUID        NOT NULL REFERENCES terapeutas(id) ON DELETE CASCADE,
  numero_telefone   TEXT        NOT NULL,   -- número do paciente (ou do terapeuta no chat 1:1)
  nome              TEXT,                   -- nome do paciente capturado pelo LLM
  data_nascimento   TEXT        NOT NULL,   -- DD/MM/YYYY (mantido como texto para flexibilidade)
  hora_nascimento   TEXT        NOT NULL,   -- HH:MM
  cidade_nascimento TEXT,
  mapa_json         TEXT        NOT NULL,   -- saída completa do Swiss Ephemeris / Kerykeion
  imagem_url        TEXT,                   -- futuro: URL Supabase Storage (imagem do mapa)
  criado_em         TIMESTAMPTZ DEFAULT now(),
  atualizado_em     TIMESTAMPTZ DEFAULT now()
);

-- Unicidade: mesmo mapa para mesma data+hora do mesmo paciente não é gerado duas vezes
CREATE UNIQUE INDEX IF NOT EXISTS idx_mapas_unico
  ON mapas_astrais (terapeuta_id, numero_telefone, data_nascimento, hora_nascimento);

-- Busca por paciente (portal + webhook)
CREATE INDEX IF NOT EXISTS idx_mapas_numero
  ON mapas_astrais (numero_telefone);

-- Listagem do terapeuta ordenada por data (portal)
CREATE INDEX IF NOT EXISTS idx_mapas_terapeuta
  ON mapas_astrais (terapeuta_id, criado_em DESC);

-- RLS — service_role tem acesso total (FastAPI usa service_role)
ALTER TABLE mapas_astrais ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'mapas_astrais' AND policyname = 'service_role_mapas'
  ) THEN
    CREATE POLICY service_role_mapas ON mapas_astrais FOR ALL USING (true);
  END IF;
END $$;
