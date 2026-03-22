# PROMPT PARA INICIAR O PROJETO

Cole isso quando abrir o Claude Code nesta pasta:

---

```
Você é um engenheiro sênior especializado em IA, RAG e WhatsApp bots.

Estamos construindo um SaaS chamado "Terapeutas Agent": um agente WhatsApp com base de conhecimento em PDF para terapeutas venderem para seus pacientes.

Leia o CLAUDE.md para entender o projeto completo antes de qualquer ação.

Stack: Python + FastAPI + LangChain + Supabase pgvector + Evolution API + Claude API

Objetivo do MVP: em 2 semanas ter 1 terapeuta funcionando, com upload de PDF, RAG funcionando e WhatsApp respondendo.

Comece pelo setup do ambiente: crie o requirements.txt, estrutura de pastas src/, e o arquivo .env.example com todas as variáveis necessárias.
```

---

## Ordem recomendada de desenvolvimento

1. `setup` — ambiente Python, requirements, estrutura de pastas
2. `supabase` — criar tabelas e função de busca vetorial
3. `rag-pipeline` — processar PDF → chunks → embeddings → supabase
4. `evolution-api` — conectar WhatsApp, enviar/receber mensagens
5. `webhook` — FastAPI recebendo mensagens do WhatsApp
6. `resposta-ia` — RAG + Claude gerando respostas
7. `painel-web` — interface para terapeuta subir PDFs
8. `deploy` — Railway + variáveis de ambiente
