---
name: relatorio-clinico
description: Gera relatorios clinicos profissionais para terapeutas alquimicos. Inclui relatorios de sessao (SOAP adaptado), relatorios de progresso, relatorios de encaminhamento e resumos de tratamento. Formato adaptado para alquimia terapeutica mantendo padrao clinico.
allowed-tools: Read Write Edit Bash
---

# Relatorio Clinico Alquimico

## Descricao

Gera documentacao clinica profissional adaptada para terapeutas alquimicos. Combina padroes de documentacao clinica (SOAP, H&P) com a terminologia e metodologia da Escola de Alquimia Joel Aleixo.

## Quando Usar

- Documentar sessoes de atendimento
- Gerar relatorio de progresso do paciente
- Criar resumo de tratamento para encaminhamento
- Documentar evolucao entre consultas
- Gerar relatorio para o portal do terapeuta

## Tipos de Relatorio

### 1. Nota de Sessao (SOAP Alquimico)

**S — Subjetivo (o que o paciente relata)**
- Queixa principal
- Como se sente emocionalmente
- Mudancas desde a ultima sessao
- Relacao com pai/mae (se relevante)

**O — Observacao (o que o terapeuta observa)**
- Comportamento fisico: inquieto vs cansado
- Comunicacao: falante vs calado
- Emocional: chorou, frio, agressivo
- Postura: arrogante vs humilde
- Cartas/florais tirados na sessao

**A — Analise Alquimica**
- Elementos identificados (% se possivel)
- Substancia dominante
- Serpentes ativas
- Setenio afetado
- Nivel do floral (1, 2 ou 3)
- Fase alquimica (Nigredo/Albedo/Rubedo)

**P — Plano**
- Protocolo definido
- Florais/kits prescritos
- Orientacoes para o paciente
- Data da proxima sessao
- Observacoes para a proxima consulta

### 2. Relatorio de Progresso

- Comparacao entre diagnosticos ao longo do tempo
- Evolucao dos elementos (grafico de tendencia)
- Serpentes resolvidas vs persistentes
- Status: progredindo / estavel / regredindo / surto
- Recomendacoes de ajuste

### 3. Resumo de Caso

- Dados demograficos (anonimizados)
- Historico de diagnosticos
- Protocolos utilizados
- Resultados obtidos
- Licoes aprendidas

## Formato de Saida

### Para WhatsApp
- Resumo conversacional em texto corrido
- Foco nos pontos mais importantes
- Sem formatacao markdown

### Para Portal (HTML)
- Formato estruturado com secoes
- Gauges visuais dos elementos
- Timeline de progresso
- Indicadores coloridos (verde=bom, amarelo=atencao, vermelho=critico)

### Para PDF (se solicitado)
- Formato profissional com cabecalho do terapeuta
- Dados do paciente anonimizados
- Assinatura do terapeuta

## Privacidade

- NUNCA incluir nome real do paciente em relatorios compartilhados
- Usar codigo ou iniciais
- Dados de nascimento: incluir apenas se necessario para mapa astral
- Telefone: NUNCA incluir em relatorios

## Integracao

- **diagnostico-alquimico**: Fonte dos dados clinicos
- **plano-tratamento**: Plano documentado no relatorio
- **infograficos-terapia**: Visuais para o relatorio
