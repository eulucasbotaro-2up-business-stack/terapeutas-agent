-- ============================================================================
-- MIGRAÇÃO: Memória Persistente por Paciente
-- Data: 2026-03-29
-- Descrição: Adiciona campos e tabelas para memória de longo prazo,
--            cruzamento entre sessões e evolução do paciente.
-- ============================================================================

-- 1. Adicionar campos ao resumos_sessao para capturar dados clínicos
-- ============================================================================

-- Campo para temas/diagnósticos chave extraídos da sessão
ALTER TABLE resumos_sessao
    ADD COLUMN IF NOT EXISTS temas_chave text[] DEFAULT '{}';

-- Campo para pontos em aberto (questões não resolvidas)
ALTER TABLE resumos_sessao
    ADD COLUMN IF NOT EXISTS pontos_abertos text DEFAULT NULL;

-- Campo para humor/estado emocional percebido na sessão
ALTER TABLE resumos_sessao
    ADD COLUMN IF NOT EXISTS humor_percebido text DEFAULT NULL;

-- Campo para nível de engajamento (1-5) avaliado pelo LLM
ALTER TABLE resumos_sessao
    ADD COLUMN IF NOT EXISTS nivel_engajamento int DEFAULT NULL;


-- 2. Adicionar campos ao perfil_usuario para evolução
-- ============================================================================

-- Resumo acumulado de evolução (atualizado a cada N sessões)
ALTER TABLE perfil_usuario
    ADD COLUMN IF NOT EXISTS resumo_evolucao text DEFAULT NULL;

-- Última vez que o resumo de evolução foi atualizado
ALTER TABLE perfil_usuario
    ADD COLUMN IF NOT EXISTS evolucao_atualizada_em timestamptz DEFAULT NULL;

-- Diagnósticos/condições mencionados pelo paciente ao longo do tempo
ALTER TABLE perfil_usuario
    ADD COLUMN IF NOT EXISTS condicoes_mencionadas text[] DEFAULT '{}';

-- Pontos recorrentes que aparecem em múltiplas sessões
ALTER TABLE perfil_usuario
    ADD COLUMN IF NOT EXISTS pontos_recorrentes text[] DEFAULT '{}';


-- 3. Índice para busca eficiente de resumos por paciente
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_resumos_sessao_paciente
    ON resumos_sessao (terapeuta_id, numero_telefone, sessao_inicio DESC);

CREATE INDEX IF NOT EXISTS idx_perfil_usuario_paciente
    ON perfil_usuario (terapeuta_id, numero_telefone);

CREATE INDEX IF NOT EXISTS idx_conversas_paciente_data
    ON conversas (terapeuta_id, paciente_numero, criado_em DESC);


-- 4. Verificar que as tabelas base existem (segurança)
-- ============================================================================

-- Se resumos_sessao não existir, criar
CREATE TABLE IF NOT EXISTS resumos_sessao (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    terapeuta_id uuid NOT NULL,
    numero_telefone text NOT NULL,
    sessao_inicio timestamptz NOT NULL,
    sessao_fim timestamptz,
    resumo text NOT NULL,
    total_mensagens int DEFAULT 0,
    temas_chave text[] DEFAULT '{}',
    pontos_abertos text,
    humor_percebido text,
    nivel_engajamento int,
    criado_em timestamptz DEFAULT now()
);

-- Se perfil_usuario não existir, criar
CREATE TABLE IF NOT EXISTS perfil_usuario (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    terapeuta_id uuid NOT NULL,
    numero_telefone text NOT NULL,
    nome text,
    total_sessoes int DEFAULT 0,
    total_mensagens int DEFAULT 0,
    temas_principais jsonb DEFAULT '[]',
    preferencias jsonb DEFAULT '{}',
    ultima_sessao_em timestamptz,
    resumo_evolucao text,
    evolucao_atualizada_em timestamptz,
    condicoes_mencionadas text[] DEFAULT '{}',
    pontos_recorrentes text[] DEFAULT '{}',
    criado_em timestamptz DEFAULT now(),
    atualizado_em timestamptz DEFAULT now(),
    UNIQUE(terapeuta_id, numero_telefone)
);
