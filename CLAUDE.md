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
│   ├── pitch.md           ← pitch para terapeutas
│   └── vendas/            ← materiais de vendas
│       ├── pitch-tony.md
│       ├── one-pager.md
│       ├── objecoes.md
│       ├── roi-calculator.md
│       └── email-prospecao.md
├── prompts/
│   ├── system_prompt.md   ← prompt do agente terapeuta
│   ├── rag_template.md    ← template de RAG
│   └── onboarding.md      ← mensagens de onboarding
├── scripts/               ← scripts utilitários
├── skills/                ← skills do Claude Code para este projeto
│   ├── setup-backend/
│   ├── setup-evolution/
│   └── setup-supabase/
├── portal-vercel/         ← portal web (deploy Vercel)
│   ├── index.html         ← portal do terapeuta (app)
│   └── landing.html       ← landing page de vendas
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

---

## Skills Instaladas

### Desenvolvimento
- **superpowers** — TDD, debugging sistemático, planos de implementação, subagents paralelos, code review
- **claude-api** — Best practices para Claude API (prompt caching, streaming, tool use)
- **webapp-testing** — Testes automatizados com Playwright
- **frontend-design** — Design de interfaces profissionais
- **pdf** — Geração e manipulação de PDFs

### Marketing & Vendas
- **sales-enablement** — Materiais de venda para o Tony (pitch, one-pager, objeções)
- **pricing-strategy** — Validação e otimização de preços
- **cold-email** — Sequências de prospecção B2B
- **referral-program** — Programa de indicação entre terapeutas
- **churn-prevention** — Redução de cancelamentos
- **revops** — Lead scoring e roteamento

### UI/UX
- **ui-ux-pro-max** — Design system com 67 estilos, 161 regras de healthcare

---

## Fluxo de Desenvolvimento

### Antes de codar
1. Usar `/writing-plans` para planejar a implementação
2. Quebrar em tarefas de 2-5 minutos

### Durante o desenvolvimento
1. Usar TDD: RED → GREEN → REFACTOR
2. `/systematic-debugging` para bugs complexos
3. `/subagent-driven-development` para tarefas paralelas

### Antes de deploy
1. `/verification-before-completion` — verificar tudo
2. `/simplify` — revisar código por reuso e qualidade
3. Testar com `/webapp-testing`

---

## Materiais de Vendas
Arquivos em `docs/vendas/`:
- `pitch-tony.md` — Script do pitch deck (14 slides)
- `one-pager.md` — Documento resumo para deixar com terapeuta
- `objecoes.md` — Guia de objeções e respostas
- `roi-calculator.md` — Calculadora de ROI
- `email-prospecao.md` — 5 templates de email frio

---

## Páginas Web
- `portal-vercel/index.html` — Portal do terapeuta (app)
- `portal-vercel/landing.html` — Landing page de vendas
- Deploy: Vercel (portal-vercel-ten.vercel.app)
