-- ============================================================================
-- MIGRAÇÃO: Tipo de Mapa — Limite de 2 mapas por paciente
-- Data: 2026-03-29
-- Descrição: Adiciona coluna tipo_mapa à tabela mapas_astrais para distinguir
--            entre "Mapa Natal" e "Mapa Alquimico". Cada paciente pode ter
--            no máximo 2 mapas (1 de cada tipo). Se já existir, atualiza.
-- ============================================================================

-- 1. Adicionar coluna tipo_mapa (default 'Mapa Natal' para registros legados)
ALTER TABLE mapas_astrais
  ADD COLUMN IF NOT EXISTS tipo_mapa TEXT DEFAULT 'Mapa Natal';

-- 2. Preencher registros existentes que não têm tipo_mapa
UPDATE mapas_astrais
  SET tipo_mapa = 'Mapa Natal'
  WHERE tipo_mapa IS NULL;

-- 3. Identificar e tratar registros Alquimicos existentes (pelo conteúdo do mapa_json)
-- Mapas com "Mapa Alquimico" no JSON ou com hora_nascimento diferente do original
-- são reclassificados
UPDATE mapas_astrais
  SET tipo_mapa = 'Mapa Alquimico'
  WHERE mapa_json LIKE '%Mapa Alquimico%'
    OR mapa_json LIKE '%elemento_dominante%'
    OR mapa_json LIKE '%dna_comprometido%'
    OR mapa_json LIKE '%serpentes_ativas%';

-- 4. Remover índice UNIQUE antigo (será substituído pelo novo)
DROP INDEX IF EXISTS idx_mapas_unico;

-- 5. Criar novo índice UNIQUE por (terapeuta, telefone, tipo_mapa)
-- Garante máximo 1 mapa de cada tipo por paciente
CREATE UNIQUE INDEX IF NOT EXISTS idx_mapas_tipo_unico
  ON mapas_astrais (terapeuta_id, numero_telefone, tipo_mapa);

-- 6. Recriar índice antigo como não-unique para compatibilidade de queries
CREATE INDEX IF NOT EXISTS idx_mapas_legado
  ON mapas_astrais (terapeuta_id, numero_telefone, data_nascimento, hora_nascimento);

-- ============================================================================
-- MIGRAÇÃO: hora_prevista em acompanhamentos
-- ============================================================================

-- 7. Adicionar coluna hora_prevista para horário das atividades
ALTER TABLE acompanhamentos
  ADD COLUMN IF NOT EXISTS hora_prevista TEXT;
