# Terapeutas Agent — IA no WhatsApp com Base de Conhecimento

## Visão do Produto
SaaS B2B para terapeutas e profissionais de saúde mental.
Cada terapeuta tem um **agente WhatsApp próprio** que responde perguntas dos pacientes com base nos PDFs/materiais que o terapeuta sobe (protocolos, técnicas, guias, conteúdos).

**Parceiro comercial:** Tony (Liberato Produtora) — tem base de terapeutas prontos para oferecer.
**Dono do projeto:** Lucas Botaro (2UP Business)

---

## Stack Técnica

| Camada | Tecnologia | Motivo |
|---|---|---|
| WhatsApp | Evolution API (self-hosted) | Open source, gratuito, multidevice |
| Backend | Python + FastAPI | Rápido de desenvolver, bom para IA |
| IA / LLM | Claude API (claude-sonnet-4-6) | Melhor custo-benefício para RAG |
| Embeddings | OpenAI text-embedding-3-small | Mais barato do mercado |
| Vector DB | Supabase pgvector | Já usado no stack 2UP |
| PDF Processing | PyMuPDF + LangChain | Chunking e indexação |
| Orquestração | n8n (Railway) | Já existe no stack 2UP |
| Storage PDFs | Supabase Storage | Centralizado |
| Banco de dados | Supabase PostgreSQL | Multi-tenant por terapeuta |
| Deploy | Railway | Já usado no stack |

---

## Arquitetura do Sistema

```
[Terapeuta] → Upload PDF → Supabase Storage
                              ↓
                    [Processamento PDF]
                    PyMuPDF → chunks de 500 tokens
                              ↓
                    [Embedding] OpenAI
                              ↓
                    [Supabase pgvector] armazena por terapeuta_id

[Paciente] → WhatsApp → Evolution API → Webhook → FastAPI
                                                      ↓
                                           Busca vetorial (top 5 chunks)
                                                      ↓
                                           Monta prompt com contexto
                                                      ↓
                                           Claude API → resposta
                                                      ↓
                                           Evolution API → WhatsApp ← [Paciente]
```

---

## Multi-tenancy
Cada terapeuta tem:
- `terapeuta_id` único (UUID)
- Número WhatsApp próprio conectado à Evolution API
- Namespace isolado no pgvector
- PDFs próprios no Supabase Storage
- Configurações do agente (nome, personalidade, limites de resposta)

---

## Modelo de Negócio
- **Preço:** R$197-297/mês por terapeuta
- **Trial:** 7 dias grátis
- **Cobrança:** Asaas (recorrência)
- **Comissão Tony:** 30% do MRR dos clientes que ele trouxer

---

## Fluxo de Onboarding do Terapeuta
1. Cadastro no painel web
2. Conecta o número WhatsApp (QR code via Evolution API)
3. Faz upload dos PDFs (protocolos, materiais, técnicas)
4. Configura o agente (nome, tom de voz, horário de atendimento)
5. Testa e ativa

---

## Arquivos do Projeto
```
terapeutas-agent/
├── CLAUDE.md              ← este arquivo (contexto principal)
├── docs/
│   ├── arquitetura.md     ← detalhes técnicos
│   ├── roadmap.md         ← fases do produto
│   └── pitch.md           ← pitch para terapeutas
├── prompts/
│   ├── system_prompt.md   ← prompt do agente terapeuta
│   ├── rag_template.md    ← template de RAG
│   └── onboarding.md      ← mensagens de onboarding
├── skills/                ← skills do Claude Code para este projeto
│   ├── setup-backend/
│   ├── setup-evolution/
│   └── setup-supabase/
├── arquitetura/
│   └── diagramas.md
└── src/                   ← código (criado durante dev)
    ├── api/
    ├── rag/
    ├── whatsapp/
    └── web/
```

---

## Variáveis de Ambiente Necessárias
```env
# Claude API
ANTHROPIC_API_KEY=

# OpenAI (embeddings)
OPENAI_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Evolution API
EVOLUTION_API_URL=
EVOLUTION_API_KEY=

# Asaas (cobrança)
ASAAS_API_KEY=

# App
SECRET_KEY=
DATABASE_URL=
```

---

## Modo de Operação do Claude Neste Projeto
- Atuar como **engenheiro sênior de IA especializado em RAG e WhatsApp bots**
- Stack preferida: Python + FastAPI + LangChain + Supabase
- Sempre pensar em **multi-tenancy** (isolamento por terapeuta)
- Priorizar **MVP rápido** — lançar em 2 semanas, iterar depois
- Código limpo, comentado em português
- Sempre criar `.env.example` junto com qualquer `.env`
