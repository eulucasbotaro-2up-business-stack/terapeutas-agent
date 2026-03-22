# Arquitetura do Agente — O Alquimista Interior
## Documento Tecnico v3.0 (revisado 2026-03-22)

---

## 1. Visao Geral

O Alquimista Interior e um agente de IA que opera como copia metodologica do Alquimista Joel Aleixo. Ele atende terapeutas da Escola de Alquimia Joel Aleixo via WhatsApp, com tres capacidades distintas: orientacao diagnostica, criacao de conteudo e pesquisa nos materiais da escola.

O agente NAO e um chatbot generico de perguntas e respostas. Ele e uma presenca alquimica que forma o olhar, organiza a percepcao e amplia a consciencia da terapeuta.

---

## 2. Os 3 Modos de Operacao

O agente opera em 3 modos distintos, detectados automaticamente a partir da mensagem da terapeuta. A terapeuta nao precisa escolher o modo — o agente le a intencao e opera.

### 2.1 MODO CONSULTA — Caso Clinico-Alquimico

**Quando ativa:** A terapeuta traz um paciente, caso, sintoma, queixa, dados de mapa astral, ou pede orientacao diagnostica/terapeutica.

**Fluxo completo:**

```
Terapeuta envia mensagem sobre paciente
        |
        v
[1] ESCUTA LIMPA
    "O que em voce sentiu que este paciente precisava ser visto hoje?"
        |
        v
[2] ANAMNESE ALQUIMICA (4 eixos)
    - Corpo: sintomas fisicos, sinais, repeticoes
    - Emocao: padroes emocionais, reacoes, bloqueios
    - Comportamento: ciclos, habitos, escolhas recorrentes
    - Campo: o que a terapeuta sentiu mas nao soube nomear
        |
        v
[3] CRUZAMENTO COM MAPA ASTRAL (se dados fornecidos)
    - Data + hora + local de nascimento
    - Elementos dominantes e ausentes
    - Conexao com DNA alquimico
    - Fonte: ASTROLOGIA.pdf (Nivel 5)
        |
        v
[4] DIAGNOSTICO
    - Eixo do desequilibrio
    - Elemento comprometido
    - Ponto do DNA ativo
    - Aprendizado escondido na dor
        |
        v
[5] ORIENTACAO TERAPEUTICA (Nivel 6)
    - Floral + Composto + Cosmetico
    - Cada indicacao com justificativa:
      por que, qual Elemento, qual DNA, qual padrao
        |
        v
[6] LEITURA QUANTICA DE CASAIS (se solicitada)
    - Contrato alquimico da uniao
    - Pontos de fortalecimento e sombra
```

**Resultado:** Diagnostico poetico, direto e preciso com indicacao terapeutica fundamentada nos materiais da escola.

---

### 2.2 MODO CRIACAO DE CONTEUDO — Comunicacao Alquimica

**Quando ativa:** A terapeuta quer criar posts, textos, legendas, materiais educativos ou qualquer comunicacao para seu publico.

**Fluxo completo:**

```
Terapeuta pede para criar conteudo
        |
        v
[1] ENTENDER INTENCAO
    - Qual tema/conceito?
    - Qual canal? (Instagram, WhatsApp, grupo)
    - Qual tom? (educativo, acolhedor, provocador)
        |
        v
[2] PESQUISA NOS MATERIAIS
    - Busca nos materiais da escola
    - Identifica nivel do conceito
    - Encontra frases e metaforas do Joel
        |
        v
[3] GERAR CONTEUDO
    - Linguagem dos materiais da escola
    - Conecta com dores do publico final:
      * Pessoas doentes sem saber da cura holistica
      * Ciclos de medicacao sem cura real
      * Padroes ancestrais/geneticos
      * Traumas emocionais nao resolvidos
      * Bloqueios financeiros herdados
    - Adapta ao canal (formato, tamanho, tom)
        |
        v
[4] ENTREGAR COM VARIANTES
    - Pelo menos 2 versoes
    - Hashtags se redes sociais
    - Material de aprofundamento
```

**Resultado:** Conteudo pronto para publicar, fiel a linguagem da escola, que conecta com o publico que precisa ouvir.

**Por que isso e importante (insight do Tony):** Se a terapeuta cria conteudo seguindo a linguagem dos materiais, automaticamente conecta com o publico final. O agente elimina a barreira de "nao saber o que escrever".

---

### 2.3 MODO PESQUISA — Explorar e Entender

**Quando ativa:** A terapeuta quer entender um conceito, explorar um tema, conectar ideias entre materiais, ou tirar duvidas sobre conteudo da escola.

**Fluxo completo:**

```
Terapeuta pergunta sobre conceito/tema
        |
        v
[1] IDENTIFICAR CONCEITO
    - Qual tema?
    - Em qual nivel da escala de maturidade?
        |
        v
[2] BUSCAR NOS MATERIAIS
    - Todos os trechos relevantes
    - Organizar por nivel (basico → avancado)
    - Identificar conexoes entre materiais
        |
        v
[3] EXPLICAR COM PROFUNDIDADE
    - Linguagem do Joel (clara, profunda)
    - Conectar conceitos entre niveis
    - Citar fontes: [Material: nome, Nivel X]
    - Mostrar evolucao do conceito entre niveis
        |
        v
[4] ORIENTAR APROFUNDAMENTO
    - Material recomendado para revisar
    - Se falta base, sugerir niveis anteriores
```

**Resultado:** Compreensao profunda e conectada dos conceitos da escola, com caminhos claros para aprofundamento.

---

## 3. Deteccao Automatica de Modo

### 3.1 Como Funciona

A funcao `detectar_modo()` em `src/core/prompts.py` analisa a mensagem da terapeuta usando um sistema de pontuacao por palavras-chave.

**Ordem de prioridade:**
1. **EMERGENCIA** — Verificada primeiro (prioridade maxima, seguranca da pessoa)
2. **SAUDACAO** — Verificada em mensagens curtas (ate 4 palavras), desde que nao contenham palavras de outros modos
3. **Modos principais** — Pontuacao por palavras-chave:
   - Cada palavra-chave encontrada soma 1 ponto ao modo correspondente
   - Frases compostas (mais de uma palavra) ganham bonus de +1 ponto
   - O modo com maior pontuacao vence
4. **Heuristica de fallback** — Se nenhum match claro:
   - Mensagem com `?` → PESQUISA
   - Sem indicacao clara → PESQUISA (modo mais seguro)

### 3.2 Exemplos de Deteccao

| Mensagem | Modo Detectado | Por que |
|---|---|---|
| "Tenho uma paciente com dor cronica" | CONSULTA | "paciente" |
| "Cria um post sobre os 4 elementos" | CRIACAO_CONTEUDO | "cria" + "post" |
| "O que e o Nigredo?" | PESQUISA | "o que e" |
| "Bom dia!" | SAUDACAO | Curta + saudacao |
| "Paciente com ideacao suicida" | EMERGENCIA | "suicida" |
| "Meu paciente precisa de conteudo sobre traumas" | CONSULTA | "meu paciente" pontua mais que "conteudo" |

### 3.3 Override Manual

A funcao `montar_prompt()` aceita o parametro `modo_override` para forcar um modo especifico, util em cenarios onde a deteccao automatica pode nao ser suficiente (ex: fluxos de conversa continuados).

---

## 4. Escala de Maturidade Diagnostica — 6 Niveis

### 4.1 Estrutura

O conhecimento da escola esta organizado em 6 niveis progressivos. O agente respeita esta hierarquia em todos os modos de operacao.

```
Nivel 1: Observacao e Pesquisa
    ↓  (base construida)
Nivel 2: Estrutura do Campo
    ↓  (campo mapeado)
Nivel 3: DNA e Identidade
    ↓  (identidade reconhecida)
Nivel 4: Ciclos e Dissolucao
    ↓  (campo estabilizado)
Nivel 5: Tempo e Consciencia
    ↓  (consciencia ampliada)
Nivel 6: Materializacao Terapeutica
```

### 4.2 Como os Niveis sao Respeitados

1. **Classificacao da pergunta:** A funcao `classificar_nivel_pergunta()` identifica o nivel da pergunta por palavras-chave
2. **Classificacao dos chunks:** A funcao `identificar_nivel_chunk()` classifica cada chunk retornado pelo RAG pelo nome do arquivo fonte
3. **Organizacao por nivel:** A funcao `formatar_contexto_por_nivel()` agrupa chunks por nivel em ordem crescente
4. **Instrucao no prompt:** O prompt inclui os niveis presentes e o nivel estimado da pergunta, orientando o agente a respeitar a sequencia
5. **Alertas de nivel:** Em niveis 4 e 6, o prompt instrui o agente a verificar pre-requisitos antes de responder

### 4.3 Materiais por Nivel

| Nivel | Materiais | Total PDFs |
|---|---|---|
| 1 | Material de Pesquisa, Pesquisa Avancada, Perguntas Frequentes, 4 Elementos & Pletora | 4 |
| 2 | Quatro Elementos e Pletora, Matrix e Traumas, Miasmas | 3 |
| 3 | DNA, Referencia do DNA | 2 |
| 4 | Trindade e Tartarus - Nigredo, Rubedo | 2 |
| 5 | Fluxus Continuum, Astrologia, Biorritmos, Chakras | 4 |
| 6 | Protocolos, Kit Primus, Aura das Flores | 3 |
| **Total** | | **18 PDFs** |

---

## 5. Rastreamento de Fontes

### 5.1 Principio

Toda informacao fornecida pelo agente DEVE ser rastreavel ate um material especifico da escola. Isso e critico para:
- Evitar delirios (hallucinations) da IA
- Permitir que a terapeuta aprofunde nos materiais originais
- Manter fidelidade ao metodo do Joel

### 5.2 Como Funciona

1. **No RAG:** Cada chunk retornado carrega metadata com `arquivo_fonte` (nome do PDF de origem)
2. **No prompt:** Chunks sao apresentados com anotacao `[Material: nome.pdf, Nivel X]`
3. **Na resposta:** O agente e instruido a citar fontes no formato `[Material: nome, Nivel X]`
4. **Pos-resposta:** A funcao `extrair_fontes_resposta()` gera um rodape com todas as fontes utilizadas

### 5.3 Regra de Ouro

Se a informacao NAO esta nos materiais retornados pelo RAG, o agente responde:
> "O campo ainda pede observacao. Nao encontrei essa informacao nos materiais da escola. Consulte diretamente o Joel ou revise as apostilas de [nivel sugerido]."

---

## 6. Fluxo Tecnico Completo

```
[Terapeuta] → WhatsApp → Evolution API → Webhook → FastAPI
                                                       |
                                                       v
                                              [1] Receber mensagem
                                                       |
                                                       v
                                              [2] detectar_modo(mensagem)
                                                  → CONSULTA / CRIACAO_CONTEUDO / PESQUISA
                                                       |
                                                       v
                                              [3] Busca vetorial no Supabase pgvector
                                                  (top 5-10 chunks, filtrado por terapeuta_id)
                                                       |
                                                       v
                                              [4] formatar_contexto_por_nivel(chunks)
                                                  → chunks organizados por nivel
                                                       |
                                                       v
                                              [5] montar_prompt(terapeuta, chunks, mensagem)
                                                  → prompt completo com modo + niveis + contexto
                                                       |
                                                       v
                                              [6] Claude API (claude-sonnet-4-6, temperature=0)
                                                       |
                                                       v
                                              [7] extrair_fontes_resposta(chunks)
                                                  → rodape com fontes
                                                       |
                                                       v
                                              [8] Resposta + fontes → Evolution API → WhatsApp
                                                       |
                                                       v
                                                  [Terapeuta]
```

---

## 7. Regras Anti-Delirio — Implementacao Tecnica

| Regra | Implementacao |
|---|---|
| Temperature 0 | Configurado na chamada ao Claude API |
| Nunca inventar | Prompt exige que responda APENAS com base no CONHECIMENTO DISPONIVEL |
| Nunca usar fontes externas | Prompt proibe explicitamente conhecimento externo |
| Sempre citar fonte | Formato obrigatorio: [Material: nome, Nivel X] |
| Fallback honesto | Frase padrao quando nao encontra informacao nos materiais |
| Nao misturar abordagens | Proibicao explicita de PNL, constelacao, psicanalise, reiki, ayurveda, etc. |
| Respeitar niveis | Alertas em niveis 4 e 6 sobre pre-requisitos |
| Astrologia restrita | Proibicao de astrologia generica/signos solares — apenas sistema da escola |
| Regra 80/20 | Se 80% certeza mas 20% duvida, perguntar em vez de afirmar |
| Historico de conversa | Ultimas 10 mensagens injetadas no prompt para continuidade (anamnese) |
| Max tokens adaptativo | 2048 para CONSULTA/CONTEUDO, 1536 para PESQUISA, 256 para SAUDACAO |

---

## 8. Funcionalidades Especiais

### 8.1 Leitura Quantica de Casais
- Ativada quando a terapeuta menciona "casal", "casais", "leitura quantica"
- Requer dados de ambos (nomes, datas, contexto do relacionamento)
- Investiga: contrato alquimico, pontos de fortalecimento, sombras ativadas
- Usa materiais de multiplos niveis para cruzamento

### 8.2 Cruzamento de Mapa Astral
- Ativado quando a terapeuta fornece data + hora + local de nascimento
- Usa EXCLUSIVAMENTE conceitos de [Material: ASTROLOGIA.pdf, Nivel 5]
- Identifica Elementos dominantes/ausentes e conecta com DNA alquimico
- NAO faz astrologia generica — apenas o sistema da escola

### 8.3 Indicacao Terapeutica Fundamentada
- Somente no Nivel 6, apos diagnostico integrado
- Cada indicacao (floral, composto, cosmetico) vem com:
  - Por que e eficaz
  - Qual Elemento reorganiza
  - Qual ponto do DNA toca
  - Qual padrao dissolve ou fortalece
- Fontes obrigatorias dos materiais de Nivel 6

---

## 9. Arquivos Relevantes

| Arquivo | Funcao |
|---|---|
| `prompts/system_prompt_alquimia.md` | System prompt completo com 3 modos (documentacao) |
| `prompts/agente_joel_aleixo.md` | Documento original da identidade do agente |
| `prompts/metadata_materiais.md` | Mapeamento dos 18 PDFs por nivel |
| `src/core/prompts.py` | Modulo Python com deteccao de modo, montagem de prompt, formatacao |
| `docs/transcricoes_tony.md` | Transcricoes dos audios do Tony (contexto de negocio) |
