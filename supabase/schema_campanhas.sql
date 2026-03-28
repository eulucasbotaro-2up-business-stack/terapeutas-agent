-- =============================================================================
-- CAMPANHAS DE RENOVAÇÃO E REENGAJAMENTO
-- Criado para o sistema multi-agente CEO + Renovação + Reengajamento
-- =============================================================================

-- Tabela de campanhas de renovação (15 dias antes do vencimento)
CREATE TABLE IF NOT EXISTS campanhas_renovacao (
  id                   UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  codigo_id            UUID    REFERENCES codigos_liberacao(id) ON DELETE CASCADE,
  terapeuta_id         UUID    NOT NULL,
  numero_telefone      TEXT    NOT NULL,
  nome_usuario         TEXT,
  plano                TEXT    DEFAULT 'terapeuta', -- praticante | terapeuta | alquimista
  data_expiracao       DATE    NOT NULL,
  dias_para_vencer     INT,    -- calculado no momento da criação da campanha
  etapa_atual          TEXT    DEFAULT 'd15',  -- d15 | d10 | d7 | d3 | d1 | d0_venceu
  status               TEXT    DEFAULT 'ativa', -- ativa | renovada | suspensa | cancelada
  ultima_mensagem_em   TIMESTAMPTZ,
  proxima_mensagem_em  TIMESTAMPTZ,
  mensagens_enviadas   INT     DEFAULT 0,
  link_renovacao       TEXT,   -- link Asaas para renovar
  created_at           TIMESTAMPTZ DEFAULT now(),
  updated_at           TIMESTAMPTZ DEFAULT now()
);

-- Tabela de campanhas de reengajamento (após suspensão/expiração)
CREATE TABLE IF NOT EXISTS campanhas_reengajamento (
  id                        UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  codigo_id                 UUID    REFERENCES codigos_liberacao(id) ON DELETE CASCADE,
  terapeuta_id              UUID    NOT NULL,
  numero_telefone           TEXT    NOT NULL,
  nome_usuario              TEXT,
  plano_anterior            TEXT    DEFAULT 'terapeuta',
  motivo_suspensao          TEXT,   -- PAGAMENTO_FALHOU | ASSINATURA_EXPIRADA | CANCELADO
  data_suspensao            DATE    NOT NULL,
  etapa_atual               TEXT    DEFAULT 'd0',  -- d0 | d2 | d5 | d7 | d14 | d30
  status                    TEXT    DEFAULT 'ativa', -- ativa | reconvertida | abandonada
  ultima_mensagem_em        TIMESTAMPTZ,
  proxima_mensagem_em       TIMESTAMPTZ,
  mensagens_enviadas        INT     DEFAULT 0,
  oferta_desconto_enviada   BOOLEAN DEFAULT false,
  desconto_oferecido        INT     DEFAULT 0,  -- % de desconto oferecido (ex: 20)
  link_reativacao           TEXT,
  created_at                TIMESTAMPTZ DEFAULT now(),
  updated_at                TIMESTAMPTZ DEFAULT now()
);

-- Tabela de leads da landing page (formulários de interesse)
CREATE TABLE IF NOT EXISTS leads_landing (
  id             UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  nome           TEXT    NOT NULL,
  email          TEXT    NOT NULL,
  telefone       TEXT,
  plano_interesse TEXT   DEFAULT 'terapeuta',
  origem         TEXT    DEFAULT 'landing', -- landing | indicacao | tony
  utm_source     TEXT,
  utm_medium     TEXT,
  utm_campaign   TEXT,
  status         TEXT    DEFAULT 'novo', -- novo | contactado | convertido | perdido
  notas          TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- Tabela de log de mensagens automáticas enviadas
CREATE TABLE IF NOT EXISTS log_mensagens_automaticas (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  tipo_campanha   TEXT    NOT NULL, -- renovacao | reengajamento | boas_vindas
  campanha_id     UUID,
  numero_telefone TEXT    NOT NULL,
  etapa           TEXT,
  mensagem        TEXT,
  status_envio    TEXT    DEFAULT 'enviado', -- enviado | falhou
  erro            TEXT,
  enviado_em      TIMESTAMPTZ DEFAULT now()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_campanhas_renovacao_status
  ON campanhas_renovacao(status, proxima_mensagem_em);

CREATE INDEX IF NOT EXISTS idx_campanhas_renovacao_numero
  ON campanhas_renovacao(numero_telefone);

CREATE INDEX IF NOT EXISTS idx_campanhas_reengajamento_status
  ON campanhas_reengajamento(status, proxima_mensagem_em);

CREATE INDEX IF NOT EXISTS idx_leads_landing_email
  ON leads_landing(email);

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_campanhas_renovacao_updated_at
  BEFORE UPDATE ON campanhas_renovacao
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at();

CREATE TRIGGER update_campanhas_reengajamento_updated_at
  BEFORE UPDATE ON campanhas_reengajamento
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at();

-- Função para buscar assinaturas expirando em X dias
CREATE OR REPLACE FUNCTION buscar_expirando_em(p_dias INT)
RETURNS TABLE (
  codigo_id            UUID,
  terapeuta_id         UUID,
  numero_ativo         TEXT,
  codigo               TEXT,
  data_expiracao       TIMESTAMPTZ,
  dias_restantes       INT,
  status_assinatura    TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    cl.id              AS codigo_id,
    cl.terapeuta_id,
    cl.numero_ativo,
    cl.codigo,
    cl.data_expiracao,
    EXTRACT(DAY FROM cl.data_expiracao - now())::INT AS dias_restantes,
    cl.status_assinatura
  FROM codigos_liberacao cl
  WHERE cl.status_assinatura = 'ativo'
    AND cl.numero_ativo IS NOT NULL
    AND cl.data_expiracao IS NOT NULL
    AND cl.data_expiracao > now()
    AND cl.data_expiracao <= now() + (p_dias || ' days')::INTERVAL
  ORDER BY cl.data_expiracao ASC;
END;
$$ LANGUAGE plpgsql;
