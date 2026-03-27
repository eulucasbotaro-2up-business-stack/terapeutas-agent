-- Alterações na tabela codigos_liberacao (já existe)
ALTER TABLE codigos_liberacao
  ADD COLUMN IF NOT EXISTS numero_ativo TEXT,           -- número do WhatsApp que está usando este código (1 código = 1 usuário)
  ADD COLUMN IF NOT EXISTS data_expiracao TIMESTAMPTZ,  -- quando o acesso expira (NULL = sem expiração, ex: teste)
  ADD COLUMN IF NOT EXISTS meses_contratados INTEGER DEFAULT 1, -- quantos meses foram comprados (1-12)
  ADD COLUMN IF NOT EXISTS asaas_subscription_id TEXT,  -- ID da assinatura no Asaas
  ADD COLUMN IF NOT EXISTS asaas_customer_id TEXT,      -- ID do cliente no Asaas
  ADD COLUMN IF NOT EXISTS asaas_payment_status TEXT DEFAULT 'pendente', -- ultimo status do pagamento no Asaas
  ADD COLUMN IF NOT EXISTS status_assinatura TEXT DEFAULT 'disponivel'   -- disponivel | ativo | expirado | suspenso_pagamento | cancelado
    CHECK (status_assinatura IN ('disponivel', 'ativo', 'expirado', 'suspenso_pagamento', 'cancelado'));

-- Alterações na tabela chat_estado (já existe)
ALTER TABLE chat_estado
  ADD COLUMN IF NOT EXISTS motivo_bloqueio TEXT; -- 'VIOLACAO' | 'ASSINATURA_EXPIRADA' | 'PAGAMENTO_FALHOU' | 'CANCELADO' | 'ADMIN'

-- Adicionar estado SUSPENSO à tabela chat_estado
-- Atualizar o CHECK constraint (precisa recriar)
ALTER TABLE chat_estado DROP CONSTRAINT IF EXISTS chat_estado_estado_check;
ALTER TABLE chat_estado ADD CONSTRAINT chat_estado_estado_check
  CHECK (estado IN ('PENDENTE_CODIGO', 'ATIVO', 'BLOQUEADO'));

-- Índices extras
CREATE INDEX IF NOT EXISTS idx_codigos_asaas_subscription
  ON codigos_liberacao (asaas_subscription_id) WHERE asaas_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_codigos_expiracao
  ON codigos_liberacao (data_expiracao) WHERE data_expiracao IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_codigos_numero_ativo
  ON codigos_liberacao (numero_ativo) WHERE numero_ativo IS NOT NULL;
