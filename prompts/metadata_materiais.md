# Mapeamento de Materiais por Nivel — Escola de Alquimia Joel Aleixo

Este documento mapeia cada PDF da escola para o nivel correspondente na Escala de Maturidade Diagnostica.
Usado pelo sistema de RAG para organizar chunks por nivel e orientar o agente.

---

## Nivel 1 — Observacao e Pesquisa
> Foco: Apenas observar, organizar e perguntar. Nao concluir.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| Material de Pesquisa.pdf | Base inicial de pesquisa alquimica | Primeiros passos, aprender a observar |
| PESQUISA AVANCADA.pdf | Aprofundamento em metodos de pesquisa | Refinar a observacao |
| PERGUNTAS FREQUENTES.pdf | Duvidas comuns sobre o metodo | Respostas rapidas para duvidas basicas |
| PERGUNTAS FREQUENTES – 4 ELEMENTOS & PLETORA.pdf | FAQ sobre 4 elementos e pletora | Duvidas especificas sobre elementos |

---

## Nivel 2 — Estrutura do Campo
> Foco: Diagnostico descritivo e educativo.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| QUATRO ELEMENTOS E PLETORA.pdf | Os 4 elementos e conceito de pletora | Entender a estrutura elemental do campo |
| MATRIX E TRAUMAS.pdf | Matriz traumatica e seus efeitos | Identificar traumas no campo |
| Miasmas.pdf | Estudo dos miasmas alquimicos | Reconhecer padroes miasmicos |

---

## Nivel 3 — DNA e Identidade
> Foco: Leituras estruturais e relacionais.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| DNA.pdf | DNA alquimico — estrutura e leitura | Leitura da identidade alquimica |
| REFERENCIA DO DNA.pdf | Referencia tecnica para leitura do DNA | Consulta e cruzamento de dados |

---

## Nivel 4 — Ciclos e Dissolucao
> Foco: Apenas com campo estabilizado. Processos de dissolucao.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| Apostila Trindade e Tartarus - Nigredo.pdf | Trindade, Tartarus e processo de Nigredo | Processos de dissolucao e sombra |
| Apostila Rubedo - 1a Edicao (1).pdf | Processo de Rubedo | Reconstrucao e integracao |

---

## Nivel 5 — Tempo e Consciencia
> Foco: Leituras astrais profundas e ciclos temporais.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| O Fluxus Continuum de John Dee PDF (1).pdf | Fluxus Continuum — tempo e consciencia | Leituras temporais profundas |
| ASTROLOGIA.pdf | Astrologia alquimica | Mapa astral alquimico |
| BIORRITIMOS.pdf | Biorritmos e ciclos naturais | Ciclos biologicos e energeticos |
| APROFUNDAMENTO NOS 7 CHACKRAS.pdf | Os 7 chakras em profundidade | Leitura energetica dos centros |

---

## Nivel 6 — Materializacao Terapeutica
> Foco: Somente apos diagnostico integrado e autorizacao do campo.

| Arquivo PDF | Descricao | Uso Principal |
|---|---|---|
| COMO USAR OS PROTOCOLOS.pdf | Guia de uso dos protocolos terapeuticos | Aplicacao pratica dos protocolos |
| SIGNIFICADO KITE PRIMUS.pdf | Significado e uso do Kit Primus | Ferramenta terapeutica central |
| A Aura das flores.pdf | Florais e suas propriedades | Indicacao de florais |
| Florais sutis.pdf | Florais sutis da escola | Indicacao de florais sutis (mencionado no doc original) |
| Anjos.pdf | Material sobre Anjos na alquimia | Trabalho com arcanos angelicos (mencionado no doc original) |
| Cosmeticos.pdf | Cosmeticos da escola | Indicacao de cosmeticos alquimicos (mencionado no doc original) |

> **NOTA**: Os 3 ultimos PDFs foram mencionados no documento original do Tony (agente_joel_aleixo.md, Nivel 6) mas ainda nao foram fornecidos. Adicionar assim que disponibilizados.

---

## Regras de Uso pelo Agente

1. **Respeitar a sequencia**: Nao pular niveis. Se a terapeuta pergunta algo de Nivel 4, verificar se ela ja tem base de Nivel 1-3.
2. **Citar sempre**: Toda informacao deve vir com `[Material: nome_do_pdf, Nivel X]`.
3. **Alertar quando necessario**: Se o chunk retornado e de nivel alto mas a pergunta e basica, orientar a terapeuta sobre o nivel adequado.
4. **Cruzar materiais**: O agente pode cruzar informacoes de multiplos niveis, desde que cite todos os materiais usados.
5. **Priorizar nivel mais baixo**: Na duvida, comece pelo nivel mais basico e va aprofundando conforme a terapeuta pede.

---

## Total: 21 PDFs distribuidos em 6 niveis

- Nivel 1: 4 PDFs (base, observacao)
- Nivel 2: 3 PDFs (estrutura, campo)
- Nivel 3: 2 PDFs (DNA, identidade)
- Nivel 4: 2 PDFs (ciclos, dissolucao)
- Nivel 5: 4 PDFs (tempo, consciencia)
- Nivel 6: 6 PDFs (protocolos, aplicacao, florais, cosmeticos)

> **NOTA**: 3 PDFs do Nivel 6 (Florais sutis, Anjos, Cosmeticos) estao pendentes de entrega pelo Tony.
