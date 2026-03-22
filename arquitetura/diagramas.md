# Arquitetura Técnica Detalhada

## Fluxo Completo

### 1. Ingestão de PDF (quando terapeuta sobe material)
```
Terapeuta faz upload do PDF
        ↓
Supabase Storage (salva arquivo)
        ↓
Trigger n8n ou FastAPI
        ↓
PyMuPDF (extrai texto)
        ↓
LangChain TextSplitter
(chunks de 500 tokens, overlap 50)
        ↓
OpenAI text-embedding-3-small
(1536 dimensões por chunk)
        ↓
Supabase pgvector
(tabela: embeddings, filtro por terapeuta_id)
```

### 2. Resposta de Mensagem (paciente manda mensagem)
```
Paciente → WhatsApp
        ↓
Evolution API (webhook)
        ↓
FastAPI /webhook
        ↓
Classificar intenção (Claude Haiku — barato)
        ↓
┌─────────────────────────────────────┐
│ URGENCIA → mensagem de crise + contato
│ AGENDAMENTO → link/contato direto
│ SAUDACAO → boas vindas
│ DUVIDA_GERAL → RAG pipeline ↓
└─────────────────────────────────────┘
        ↓ (DUVIDA_GERAL)
Embedding da pergunta (OpenAI)
        ↓
Busca vetorial Supabase
(top 5 chunks mais similares do terapeuta_id)
        ↓
Montar prompt com system_prompt + chunks + pergunta
        ↓
Claude Sonnet (resposta final)
        ↓
Evolution API → WhatsApp → Paciente
```

---

## Schema do Banco de Dados (Supabase)

```sql
-- Terapeutas (multi-tenant)
CREATE TABLE terapeutas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  telefone_whatsapp TEXT,
  especialidade TEXT,
  contato_agendamento TEXT,
  horario_atendimento TEXT,
  evolution_instance TEXT,  -- nome da instância na Evolution API
  ativo BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- PDFs / Documentos
CREATE TABLE documentos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id),
  nome_arquivo TEXT,
  storage_path TEXT,
  status TEXT DEFAULT 'processando', -- processando | ativo | erro
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- Embeddings (RAG)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id),
  documento_id UUID REFERENCES documentos(id),
  conteudo TEXT,
  embedding vector(1536),
  metadata JSONB,
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- Índice para busca vetorial
CREATE INDEX ON embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Conversas / Histórico
CREATE TABLE conversas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id),
  paciente_numero TEXT,
  mensagem_paciente TEXT,
  resposta_agente TEXT,
  intencao TEXT,
  chunks_usados JSONB,
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- Função de busca vetorial
CREATE OR REPLACE FUNCTION buscar_chunks(
  query_embedding vector(1536),
  terapeuta_uuid UUID,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  conteudo TEXT,
  similarity FLOAT
)
LANGUAGE SQL STABLE
AS $$
  SELECT
    id,
    conteudo,
    1 - (embedding <=> query_embedding) AS similarity
  FROM embeddings
  WHERE terapeuta_id = terapeuta_uuid
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

---

## Estrutura FastAPI

```
src/
├── main.py              # app FastAPI, rotas principais
├── api/
│   ├── webhook.py       # recebe mensagens Evolution API
│   ├── terapeutas.py    # CRUD terapeutas
│   └── documentos.py    # upload e gestão de PDFs
├── rag/
│   ├── processor.py     # processa PDF → chunks → embeddings
│   ├── retriever.py     # busca vetorial no Supabase
│   └── generator.py     # monta prompt + chama Claude
├── whatsapp/
│   ├── evolution.py     # cliente Evolution API
│   └── messages.py      # formata e envia mensagens
├── models/
│   └── schemas.py       # Pydantic models
└── core/
    ├── config.py        # variáveis de ambiente
    ├── supabase.py      # cliente Supabase
    └── prompts.py       # templates de prompt
```

---

## Custo Estimado por Terapeuta/Mês

| Item | Custo |
|---|---|
| Claude Sonnet (500 msgs/mês) | ~R$3 |
| OpenAI Embeddings (10 PDFs) | ~R$0,50 |
| Evolution API (self-hosted Railway) | ~R$15 dividido por terapeutas |
| Supabase (Storage + DB) | ~R$5 |
| **Total por terapeuta** | **~R$8-10** |
| **Preço cobrado** | **R$197** |
| **Margem** | **~95%** |
