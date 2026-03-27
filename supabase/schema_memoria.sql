-- =============================================================================
-- Schema de Memória do Usuário — Terapeutas Agent
-- =============================================================================
-- Execute este arquivo no SQL Editor do Supabase APÓS schema_assinatura.sql
--
-- Cria:
--   1. perfil_usuario       — perfil acumulado por número de telefone
--   2. resumos_sessao       — resumos compactados de sessões anteriores
-- Altera:
--   3. chat_estado          — campos de sessão e confirmação de tópico
-- =============================================================================


-- =============================================================================
-- 1. PERFIL DO USUÁRIO
-- Acumula temas, casos, estilo e histórico de cada número de telefone.
-- =============================================================================

CREATE TABLE IF NOT EXISTS perfil_usuario (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    terapeuta_id        UUID NOT NULL,
    numero_telefone     TEXT NOT NULL,

    -- Dados básicos
    nome                TEXT,
    total_sessoes       INTEGER DEFAULT 0,
    total_mensagens     INTEGER DEFAULT 0,

    -- Temas mais discutidos: [{tema: "ansiedade", frequencia: 5}, ...]
    temas_principais    JSONB DEFAULT '[]'::JSONB,

    -- Casos em andamento: [{descricao: "...", criado_em: "..."}]
    casos_ativos        JSONB DEFAULT '[]'::JSONB,

    -- Preferências detectadas: {estilo: "direto", modo_principal: "CONSULTA"}
    preferencias        JSONB DEFAULT '{}'::JSONB,

    -- Timestamps
    ultima_sessao_em    TIMESTAMPTZ,
    criado_em           TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(terapeuta_id, numero_telefone)
);

CREATE INDEX IF NOT EXISTS idx_perfil_usuario_terapeuta
    ON perfil_usuario(terapeuta_id);

CREATE INDEX IF NOT EXISTS idx_perfil_usuario_numero
    ON perfil_usuario(numero_telefone);

COMMENT ON TABLE perfil_usuario IS
    'Perfil acumulado de cada usuário (número de WhatsApp) por terapeuta. '
    'Alimentado após cada interação. Base para personalização crescente.';


-- =============================================================================
-- 2. RESUMOS DE SESSÃO
-- Cada sessão (bloco de conversa separado por > 3h de inatividade) é resumida
-- pelo Claude Haiku e salva aqui para injeção em sessões futuras.
-- =============================================================================

CREATE TABLE IF NOT EXISTS resumos_sessao (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    terapeuta_id        UUID NOT NULL,
    numero_telefone     TEXT NOT NULL,

    -- Janela da sessão
    sessao_inicio       TIMESTAMPTZ NOT NULL,
    sessao_fim          TIMESTAMPTZ,

    -- Resumo gerado pelo Claude Haiku (max ~300 chars)
    resumo              TEXT NOT NULL,

    -- Temas detectados nesta sessão
    temas               JSONB DEFAULT '[]'::JSONB,

    -- Quantidade de mensagens na sessão
    total_mensagens     INTEGER DEFAULT 0,

    criado_em           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumos_sessao_usuario
    ON resumos_sessao(terapeuta_id, numero_telefone, sessao_inicio DESC);

COMMENT ON TABLE resumos_sessao IS
    'Resumos compactos de sessões anteriores. Injetados no system prompt '
    'para dar ao agente memória de longo prazo sem sobrecarregar o contexto.';


-- =============================================================================
-- 3. ALTERAÇÕES EM chat_estado
-- Adiciona campos para controle de sessão e confirmação de mudança de tópico.
-- =============================================================================

-- Timestamp da última mensagem recebida (base para detectar nova sessão)
ALTER TABLE chat_estado
    ADD COLUMN IF NOT EXISTS ultima_mensagem_em TIMESTAMPTZ DEFAULT NOW();

-- Início da sessão atual (para saber o range ao gerar o resumo)
ALTER TABLE chat_estado
    ADD COLUMN IF NOT EXISTS sessao_atual_inicio TIMESTAMPTZ DEFAULT NOW();

-- Flag: estamos aguardando confirmação do usuário sobre mudança de assunto?
ALTER TABLE chat_estado
    ADD COLUMN IF NOT EXISTS aguardando_confirmacao_topico BOOLEAN DEFAULT FALSE;

-- Mensagem pendente enquanto aguarda confirmação de mudança de tópico
ALTER TABLE chat_estado
    ADD COLUMN IF NOT EXISTS mensagem_pendente_topico TEXT;

-- Tópico anterior (usado na mensagem de confirmação: "quer sair de [topico]?")
ALTER TABLE chat_estado
    ADD COLUMN IF NOT EXISTS topico_anterior TEXT;

-- Índice para queries de usuários com confirmação pendente
CREATE INDEX IF NOT EXISTS idx_chat_estado_confirmacao
    ON chat_estado(terapeuta_id, aguardando_confirmacao_topico)
    WHERE aguardando_confirmacao_topico = TRUE;

COMMENT ON COLUMN chat_estado.ultima_mensagem_em IS
    'Atualizado em cada mensagem recebida. Usado para detectar gap de sessão (> 3h = nova sessão).';

COMMENT ON COLUMN chat_estado.aguardando_confirmacao_topico IS
    'TRUE quando o agente pediu confirmação sobre mudança de assunto e aguarda resposta.';

COMMENT ON COLUMN chat_estado.mensagem_pendente_topico IS
    'Mensagem que disparou a detecção de mudança de tópico. Processada após confirmação.';
