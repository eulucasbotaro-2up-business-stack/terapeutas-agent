# RAG Knowledge Base Audit — Escola de Alquimia Joel Aleixo
**Gerado em**: 2026-03-28
**Terapeuta ID**: 5085ff75-fe00-49fe-95f4-a5922a0cf179

---

## Problema Identificado

A IA sabia as informações mas não conseguia encontrá-las via busca semântica.
**Causa raiz**: distância vocabular entre termos do terapeuta ("florais do Kit Primus para o chakra umbilical") e texto das apostilas ("Presente Solar Umbilical"), baixa similaridade cosine → chunks corretos não eram retornados.

**Solução**: indexar documentos estruturados densos em keywords que fazem a ponte entre os dois vocabulários.

---

## Fase 1 — Executada (2026-03-28)

### Documentos indexados (16 docs, 115 chunks):
- Kit Primus: todos os 7 chakras × 7 polaridades
- Rescue Florais: todos os 7 rescues com indicações
- Bálsamos por chakra
- DNA Alquímico, Serpentes, Setenios, Elementos, Protocolo Clínico, Mapa Natal, Visão Geral

### Resultado validado:
- top-1 similarity 0.48–0.72 em todas as queries críticas
- buscar_chunks_v2 com tags ativas retorna NEW docs em 100% das queries testadas

---

## Gaps Identificados — Fases Seguintes

### FASE 2 — Alta Prioridade

#### Kits Avançados (faltam na base estruturada)
| Kit | Keywords | Conteúdo necessário |
|---|---|---|
| Corpus Celestes | corpus celestes, 12 archetypes, florais astrológicos, áries, leão | 12 florais astrológicos + arquétipo correspondente |
| Kit Matrix/Materlux | matrix, materlux, 8º chakra, infertilidade, traumas intrauterinos | Matrix, traumas uterinos, linhagem feminina |
| Kit Torus | torus, metabolismo, atrair parcerias, sincronicidade | Torus, força metabólica, alinhamento pensar-sentir-fazer |
| Alliastrum | alliastrum, minerais, pedras, 3,5 anos, ouro prata diamante | Preparação 3,5 anos, minerais, arquétipos minerais |
| Vitriol | vitriol, V.I.T.R.I.O.L., carbono siberiano, desobediência espiritual | Definição, indicação, mecanismo alquímico |
| Fluxus Continuum | fluxus continuum | Definição, uso (pesquisar) |
| Phoenix | phoenix, fênix, renascimento, morte simbólica | Renascimento alquímico, ciclo morte-renascimento |
| Pletora | pletora, excesso substâncias | Excesso/falta de substâncias alquímicas |

#### Estágios Alquímicos
| Estágio | Keywords | Conteúdo |
|---|---|---|
| Nigredo | nigredo, obra negra, desintoxicação, sonhos sujeira | Fase de limpeza, sinais clínicos, o que dizer ao paciente |
| Albedo | albedo, obra branca, clareza, despertar espiritual | Fase de clareza, missão, trabalho astrológico intensifica |
| Rubedo | rubedo, obra vermelha, potenciais, virtudes, sonhos revelatórios | Fase avançada, sonhos do inconsciente |

#### Padrões Ancestrais Detalhados
| Tema | Keywords |
|---|---|
| Serpente do Pai (detalhada) | serpente pai, lado direito corpo, autoridade, financeiro, pai ausente, pai autoritário |
| Serpente da Mãe (detalhada) | serpente mãe, lado esquerdo corpo, afeto, nutrição, mãe superprotetora |
| Eclipse Lunar | eclipse lunar, pai autoritário, suprime mãe |
| Eclipse Solar | eclipse solar, mãe suprime referência paterna |

### FASE 3 — Prioridade Média

#### Mapeamento Sintomas → Causas
| Sintoma | Causa Alquímica |
|---|---|
| Dor nas pernas / insegurança | Fogo+Terra deficiente, Serpente do Pai, pai ausente |
| Infertilidade | Matrix danificada, traumas intrauterinos, linhagem feminina |
| Bloqueio financeiro | Terra deficiente, pai que não cobrava, crenças de merecimento |
| Depressão | Fogo deficiente ou Água em excesso, Serpente da Mãe |
| Ansiedade | Ar/Fogo em excesso, desconexão da missão |
| Dor nas costas / estrutural | Peso ancestral carregado, Terra deficiente |
| Pele / alergias | Rejeição intrauterina, sentimentos reprimidos |

#### Anamnese Alquímica
- 5 perguntas centrais do Joel
- Mapeamento respostas → setenios/serpentes
- Workflow diagnóstico completo

#### Miasmas
- Definição, origem (até 5 gerações)
- Manifestações (doenças crônicas, padrões repetitivos)
- Protocolo de limpeza

### FASE 4 — Menor Prioridade

- Dinâmica de casais alquímicos (contratos, análise dual)
- Crianças e famílias (tratar pai/mãe, não a criança)
- Casos clínicos paradigmáticos (infertilidade 10 anos → livros → concepção; 11 carcinomas → nódulos benignos)
- Dosagem e posologia completa (9/15/21 gotas, 9h/15h/21h, 28 dias)

---

## Arquitetura de Tags — Sistema Atual

Tags disponíveis no sistema (retriever.py `MAPA_TERMOS_TAGS`):
```
dna, dna_leitura, dna_referencia
chakra, chakra_base, chakra_sacral, chakra_plexo, chakra_cardiaco, chakra_laringeo, chakra_frontal, chakra_coronario
elementos, elemento_terra, elemento_agua, elemento_fogo, elemento_ar, pletora, phoenix
transmutacao, nigredo, rubedo, albedo, aliastrum, trindade, tartarus
matrix, matrix_trauma, matrix_padrao, matrix_heranca, miasma
astrologia, astro_mapa, astro_ciclo, astro_regente, astro_casa
biorritmo, fluxus
floral, kit_primus, floral_aura
protocolo
vitriol, torus
fundamentos, pesquisa, conceito_basico
```

**Ação**: ao criar novos documentos, mapear para as tags acima.

---

## Script de Indexação

Arquivo: `scripts/indexar_conhecimento_estruturado.py`
Executar após adicionar novos documentos ao dict `DOCS`:
```bash
cd terapeutas-agent
source .env
.venv/Scripts/python.exe scripts/indexar_conhecimento_estruturado.py
```
