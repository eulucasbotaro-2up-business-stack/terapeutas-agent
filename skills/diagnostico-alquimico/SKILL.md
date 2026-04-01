---
name: diagnostico-alquimico
description: Gera diagnosticos alquimicos completos em 5 camadas (Elementos, Substancias, DNA, Nivel Floral, Cruzamento) para a Escola de Alquimia Joel Aleixo. Analisa pacientes por elementos, substancias, serpentes, setenios e mapa astral. Gera relatorios visuais HTML para o portal do terapeuta.
allowed-tools: Read Write Edit Bash
---

# Diagnostico Alquimico — Escola de Alquimia Joel Aleixo

## Descricao

Skill especializada para gerar diagnosticos alquimicos completos seguindo a metodologia da Escola de Alquimia Joel Aleixo. O diagnostico segue 5 camadas de analise, cruzando dados do paciente com materiais da escola.

## Quando Usar

Use esta skill quando:
- O terapeuta pedir um diagnostico completo de um paciente
- Precisar analisar elementos, substancias ou DNA alquimico
- Gerar relatorio visual do diagnostico para o portal
- Avaliar progresso/regressao de um paciente ao longo do tempo
- Detectar surtos ou desequilibrios criticos
- Cruzar dados do mapa astral com estado atual dos elementos

## Sistema de 5 Camadas

### CAMADA 1 — Elementos (Terra, Ar, Fogo, Agua)

Analise cada elemento separadamente:

**Terra** (marrom/verde)
- Excesso: possessividade, materialismo, rigidez, apego ao fisico
- Falta: instabilidade financeira, falta de base, desconexao com o corpo
- Tartaro de Terra: acumulacao doentia, obsessao material

**Ar** (azul claro)
- Excesso: falante demais, intelectualidade sem aplicacao pratica = tartaro de ar
- Falta: nao entende o que lhe dizem, confusao mental, dificuldade cognitiva
- Tartaro de Ar: inteligencia nao aplicada na vida, doenca cerebral

**Fogo** (vermelho)
- Excesso: agressividade, sexualidade descontrolada, inquietude na mesa
- Falta: apatia, falta de iniciativa, passividade
- ATENCAO: Excesso de fogo puxa todo o ar — paciente fica sem ar (sem inteligencia)

**Agua** (azul)
- Excesso: emocionalidade excessiva, choro facil, apego emocional
- Falta: frieza, secura emocional, falta de empatia

**Regra de Cruzamento**: Se o mapa astral mostra excesso de Terra mas o comportamento mostra excesso de Fogo, o fogo NAO e natal — e momentaneo. Investigar a causa.

### CAMADA 2 — Substancias (Enxofre, Sal, Mercurio)

**Enxofre** = Terra + Fogo
- Paciente sulfurico: agressivo, possessivo, dominador
- Quer controlar tudo e todos
- Manifestacao fisica: calor excessivo, inflamacoes

**Sal** = Substancia ponte (entre todos os elementos)
- Paciente salino: melancolico, sem identidade propria
- Facilmente influenciavel, assume personalidade dos outros
- Se alguem diz que o projeto e bom, ele concorda; se outro diz que e ruim, ele muda
- NAO TEM identidade propria — precisa revitalizar o sal

**Mercurio** = Ar + Agua
- Paciente mercurial: fluido, comunicativo, mutavel
- Pode ser positivo (adaptavel) ou negativo (instavel)
- Manifestacao: mudanca constante de opiniao e direcionamento

### CAMADA 3 — DNA Alquimico

**Serpente do Pai**
- Primeiro setenio (0-7 anos): base da personalidade
- Hormonios masculinos, troca de experiencias
- Pai ausente = base corrompida, falta do lado masculino
- Filho que segue profissao do pai por influencia hormonal, nao por vocacao
- Falta de troca de hormonios = problemas futuros

**Serpente da Mae**
- Energia nutridora, formacao emocional, feminino
- Mae rica em Ar e Agua = acolhimento, amor, inteligencia, sabedoria
- Mae guerreira (papel trocado) = passou pro filho a energia do pai
- Filho entre pai e mae iguais = confusao de identidade

**Setenios** (ciclos de 7 anos)
- Setenio 1 (0-7): Formacao base — Serpente do Pai
- Setenio 2 (7-14): Socializacao — influencia escolar
- Setenio 3 (14-21): Individuacao — busca de identidade
- Setenio 4 (21-28): Maturidade — primeiras escolhas adultas
- Setenio 5 (28-35): Crise — questionamento de rumo
- Setenio 6 (35-42): Meia-idade — reavaliacao profunda
- Setenio 7+ (42+): Integracao — sabedoria ou estagnacao

### CAMADA 4 — Nivel do Floral

Quando o paciente tira cartas das 99 essencias:

**Nivel 1** — Questao momentanea, passageira
- Exemplo: Manjericao = falta de fogo AGORA, mas vai passar
- Tratamento: intervencao pontual, sem urgencia

**Nivel 2** — Questao espiritual E material simultaneamente
- Precisa trabalhar as duas frentes com urgencia
- Tratamento: protocolo duplo (espiritual + material)

**Nivel 3** — Urgencia espiritual profunda
- Trabalho espiritual intenso necessario
- Tratamento: foco total na dimensao espiritual

**Cruzamento**: Se o floral nivel 1 indica falta de fogo, mas o mapa mostra excesso de fogo, e MOMENTANEO — nao e do mapa. Pressao passageira.

### CAMADA 5 — Cruzamento e Sintese

Cruzar TODAS as camadas:
1. Estado dos elementos vs mapa astral (natal vs momentaneo)
2. Substancia dominante vs comportamento observado
3. DNA alquimico vs padroes repetitivos
4. Nivel do floral vs gravidade real do caso
5. Progresso vs regressao (comparar com diagnosticos anteriores)

**Deteccao de Surto**: Se os elementos oscilam mais de 30% entre consultas, o paciente pode estar em surto. Alertar o terapeuta.

**Fluxo Continuo**: Verificar se o paciente esta conectado ao fluxo continuo ou desconectado. Paciente desconectado do fluxo escolhe ficar no mal.

## Formato de Saida

O diagnostico deve ser entregue de forma CONVERSACIONAL (WhatsApp) ou como relatorio visual (portal).

### Para WhatsApp
- Texto corrido, sem bullet points, sem headers
- Foco nos 2-3 conceitos mais relevantes para o caso
- Linguagem de colega para colega
- Maximo 1 pergunta por mensagem

### Para Portal (Relatorio HTML)
Gerar arquivo HTML com:
- Gauges coloridos dos 4 elementos com percentuais
- Cards das 3 substancias
- Secao de DNA Alquimico (Serpente Pai/Mae)
- Indicador de progresso/regressao
- Alertas visuais para surtos
- Cruzamento com mapa astral

## Fontes de Dados

Todos os dados devem vir EXCLUSIVAMENTE dos materiais da Escola de Alquimia Joel Aleixo:
- Apostila dos 4 Elementos e Pletora
- Material de DNA Alquimico
- Apostila Nigredo/Albedo/Rubedo
- Material do Fluxus Continuum
- Astrologia da Escola
- 99 Essencias e Florais Sutis

NUNCA misturar com abordagens externas (PNL, constelacao familiar, medicina chinesa, etc).

## Integracao

Esta skill integra com:
- **plano-tratamento**: Gera plano de tratamento a partir do diagnostico
- **relatorio-clinico**: Documenta o diagnostico em formato clinico
- **infograficos-terapia**: Cria visuais do diagnostico para o terapeuta
