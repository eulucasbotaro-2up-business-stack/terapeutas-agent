# Roadmap — Terapeutas Agent

## Fase 1 — MVP (2 semanas) 🎯
**Objetivo:** 1 terapeuta funcionando, vendável ao Tony

### Semana 1
- [ ] Setup Supabase (tabelas, pgvector, storage)
- [ ] Pipeline de PDF: upload → chunks → embeddings → vector DB
- [ ] FastAPI: endpoint de webhook WhatsApp
- [ ] Integração Evolution API (conectar número)
- [ ] RAG básico funcionando (pergunta → busca → resposta)

### Semana 2
- [ ] System prompt refinado com testes reais
- [ ] Painel web mínimo (upload PDFs, configurar agente)
- [ ] Multi-tenant básico (2 terapeutas isolados)
- [ ] Deploy Railway
- [ ] Cobrança Asaas (link de pagamento manual por enquanto)

**Entregável:** Tony consegue vender para 3-5 terapeutas da base dele

---

## Fase 2 — Produto (mês 2) 🚀
- [ ] Painel web completo (onboarding self-service)
- [ ] Histórico de conversas por paciente
- [ ] Relatório semanal para o terapeuta (perguntas mais frequentes)
- [ ] Cobrança recorrente automatizada (Asaas)
- [ ] Suporte a múltiplos números por terapeuta
- [ ] Agendamento integrado (Calendly ou nativo)

---

## Fase 3 — Escala (mês 3+) 📈
- [ ] App mobile para terapeuta gerenciar
- [ ] Integração com prontuário eletrônico
- [ ] Módulo de grupos (WhatsApp group bot)
- [ ] White-label (terapeuta com marca própria no bot)
- [ ] Afiliados (modelo Tony escalado)

---

## Métricas de Sucesso
- Semana 2: 1 terapeuta testando
- Mês 1: 5 terapeutas pagantes (~R$1.000 MRR)
- Mês 3: 30 terapeutas (~R$7.000 MRR)
- Mês 6: 100 terapeutas (~R$25.000 MRR)
