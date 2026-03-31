-- ============================================================================
-- FIX: Corrigir tipo_mapa corrompido pela migração anterior
-- Problema: A migração migracao_tipo_mapa.sql usou heurística baseada em
--           mapa_json para reclassificar, mas o webhook salva o MESMO mapa_json
--           para ambos os tipos (Natal e Alquimico). Resultado: todos ficaram
--           como "Mapa Alquimico".
-- Solução: Para cada paciente que tem mapas duplicados com mesmo tipo_mapa,
--           reclassificar o mais antigo como "Mapa Natal" (o webhook salva
--           Alquimico primeiro e Natal depois, mas como a migração corrompeu,
--           usamos a lógica: se tem 2 registros, o segundo é Natal).
-- ============================================================================

-- 1. Primeiro, verificar quantos registros estão duplicados
-- SELECT terapeuta_id, numero_telefone, tipo_mapa, count(*)
-- FROM mapas_astrais
-- GROUP BY terapeuta_id, numero_telefone, tipo_mapa
-- HAVING count(*) > 1;

-- 2. Para pacientes com 2+ registros "Mapa Alquimico",
--    reclassificar o mais RECENTE como "Mapa Natal"
--    (webhook salva Alquimico com imagem_joel e Natal com imagem_trad)
--    O Natal geralmente é o que tem imagem circular tradicional
WITH duplicados AS (
    SELECT id, terapeuta_id, numero_telefone, tipo_mapa, criado_em,
           ROW_NUMBER() OVER (
               PARTITION BY terapeuta_id, numero_telefone
               ORDER BY criado_em ASC
           ) as rn
    FROM mapas_astrais
)
UPDATE mapas_astrais
SET tipo_mapa = 'Mapa Natal'
WHERE id IN (
    SELECT id FROM duplicados WHERE rn = 2
)
AND tipo_mapa = 'Mapa Alquimico';

-- 3. Se ainda existem pacientes com apenas 1 mapa e tipo "Mapa Alquimico",
--    verificar se a imagem_url parece ser o mapa tradicional (sem o homem)
--    (Nesse caso, manter como está — o segundo mapa será gerado pelo webhook)
