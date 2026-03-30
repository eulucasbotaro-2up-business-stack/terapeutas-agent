-- ============================================================================
-- MIGRAÇÃO: Segmentação de Conversas por Paciente
-- Data: 2026-03-29
-- Descrição: Adiciona coluna paciente_vinculado_id à tabela conversas para
--            permitir vincular conversas do terapeuta a pacientes específicos.
--            A IA detecta automaticamente quando o terapeuta está discutindo
--            um paciente específico e vincula a conversa ao prontuário dele.
-- ============================================================================

-- 1. Adicionar coluna paciente_vinculado_id (nullable — nem toda conversa é sobre um paciente)
ALTER TABLE conversas
  ADD COLUMN IF NOT EXISTS paciente_vinculado_id UUID REFERENCES pacientes(id) ON DELETE SET NULL;

-- 2. Criar índice para busca rápida de conversas vinculadas a um paciente
CREATE INDEX IF NOT EXISTS idx_conversas_paciente_vinculado
  ON conversas (terapeuta_id, paciente_vinculado_id)
  WHERE paciente_vinculado_id IS NOT NULL;

-- 3. Índice para consultas de timeline e prontuário
CREATE INDEX IF NOT EXISTS idx_conversas_vinculado_data
  ON conversas (paciente_vinculado_id, criado_em DESC)
  WHERE paciente_vinculado_id IS NOT NULL;
