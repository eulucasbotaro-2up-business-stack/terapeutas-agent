# Proposta: Estrutura de Materiais — Escola de Alquimia Joel Aleixo

> **Autor:** Analise tecnica por IA (Claude)
> **Data:** 22/03/2026
> **Status:** PROPOSTA — aguardando aprovacao do Lucas para implementar

---

## 1. Diagnostico do Estado Atual

### O que temos hoje
- **21 PDFs** processados (materiais da escola)
- **29 transcricoes** do YouTube
- **~9.246 chunks** na tabela `embeddings` do Supabase pgvector
- Mapeamento de niveis em `prompts/metadata_materiais.md` (6 niveis)
- 8 apostilas na pasta `materiais/APOSTILAS/` (com prefixo M1-M4)
- 20 PDFs na pasta `materiais/material Joel Aleixo/`
- Busca puramente vetorial (cosine similarity) sem filtros por modulo/tag

### Problemas identificados

| # | Problema | Impacto |
|---|---|---|
| 1 | Chunks so tem `arquivo_fonte` e `pagina` no metadata | Impossivel filtrar por tema na busca |
| 2 | Busca vetorial pura traz chunks irrelevantes | "7 cores dos chakras" pode trazer algo sobre "cores dos elementos" |
| 3 | Sem campo de modulo/nivel na tabela | Impossivel vender por modulos ou restringir acesso |
| 4 | Nomes de arquivo genericos | "Material de Pesquisa.pdf" nao diz nada sobre o conteudo |
| 5 | Transcricoes do YouTube misturadas sem categorias | Sem como saber qual video fala sobre DNA vs Florais |
| 6 | Funcao `buscar_chunks` nao aceita filtros adicionais | Sempre retorna de toda a base do terapeuta |
| 7 | Metadata JSONB existe mas esta vazio `{}` no schema | Campo subutilizado |

---

## 2. Organizacao por Modulos (para venda)

### Proposta de 6 Modulos

Baseado no mapeamento existente (`metadata_materiais.md`), nos nomes das apostilas (M1-M4), e no conteudo dos PDFs.

---

### Modulo 1 — Fundamentos e Pesquisa
> **Preco sugerido:** Incluso no plano base (ou R$47/mes)
> **Publico:** Terapeuta iniciante na Escola de Alquimia

| PDF | Pasta | Tema |
|---|---|---|
| Material de Pesquisa.pdf | material Joel Aleixo | Base inicial de pesquisa |
| PESQUISA AVANCADA.pdf | material Joel Aleixo | Metodos avancados de pesquisa |
| PERGUNTAS FREQUENTES.pdf | material Joel Aleixo | FAQ geral da escola |
| PERGUNTAS FREQUENTES – 4 ELEMENTOS & PLETORA.pdf | material Joel Aleixo | FAQ sobre elementos |
| PRIMEIRO PASSO.docx | material Joel Aleixo | Guia de primeiro passo |
| M1.Apostila-Modulo-1.pdf | APOSTILAS | Apostila oficial do Modulo 1 |

**Transcricoes YouTube relacionadas:**
- A Escolha de Curar com Joel Aleixo Gabriela.txt
- A vida so muda quando escutamos o chamado da alma.txt
- Cure-se de quem nao e voce.txt
- Living by Alchemy Healing yourself and healing others.txt

---

### Modulo 2 — Elementos, Matrix e Campo
> **Preco sugerido:** R$97/mes (inclui Modulo 1)
> **Publico:** Terapeuta com base, pronta para diagnostico

| PDF | Pasta | Tema |
|---|---|---|
| QUATRO ELEMENTOS E PLETORA.pdf | material Joel Aleixo | 4 elementos e pletora |
| MATRIX E TRAUMAS.pdf | material Joel Aleixo | Matriz traumatica |
| Miasmas.pdf | material Joel Aleixo | Miasmas alquimicos |
| M2.Apostila - Phoenix-e-Pletora.pdf | APOSTILAS | Phoenix e Pletora |
| M2.Apostila -Trindade-e-Tartarus.pdf | APOSTILAS | Trindade e Tartarus |

**Transcricoes YouTube relacionadas:**
- Da Historia da Arte a Arte de Curar.txt
- Dermatite pressao infertilidade E AGORA.txt
- PARE DE HERDAR O QUE NAO E SEU.txt
- Survival mechanisms in childhood.txt
- Limiting Beliefs Stories You Tell Yourself.txt

---

### Modulo 3 — DNA Alquimico
> **Preco sugerido:** R$147/mes (inclui Modulos 1-2)
> **Publico:** Terapeuta pronta para leituras de identidade

| PDF | Pasta | Tema |
|---|---|---|
| DNA.pdf | material Joel Aleixo | DNA alquimico completo |
| REFERENCIA DO DNA.pdf | material Joel Aleixo | Tabela de referencia do DNA |
| M3.Apostila Modulo 3.pdf | APOSTILAS | Apostila oficial Modulo 3 |

**Transcricoes YouTube relacionadas:**
- QUANDO A VOZ CALA O CORPO GRITA.txt
- Every cancer patient I have treated.txt
- How to awaken the spiritual self and expand consciousness.txt

---

### Modulo 4 — Transmutacao (Nigredo, Rubedo, Alquimia Avancada)
> **Preco sugerido:** R$197/mes (inclui Modulos 1-3)
> **Publico:** Terapeuta com campo estabilizado

| PDF | Pasta | Tema |
|---|---|---|
| Apostila Trindade e Tartarus - Nigredo.pdf | material Joel Aleixo | Nigredo — dissolucao e sombra |
| Apostila Rubedo - 1a Edicao (1).pdf | material Joel Aleixo | Rubedo — reconstrucao |
| M4.Apostila - Alquimia Avancada.pdf | APOSTILAS | Alquimia avancada |
| M4.Apostila Aliastrum.pdf | APOSTILAS | Aliastrum |
| M4.Apostila Matrix.pdf | APOSTILAS | Matrix avancada |
| M4.apostila_guia_vitriol_torus_06.05.16.pdf | APOSTILAS | Vitriol e Torus |

**Transcricoes YouTube relacionadas:**
- Do Bournout a Cura.txt
- QUANDO VOCE MUDA TUDO MUDA.txt
- Quando nada preenche.txt
- The liberating power of forgiveness.txt
- O Encontro Que Fechou Um Ciclo de 30 Anos.txt

---

### Modulo 5 — Astrologia, Ciclos e Chakras
> **Preco sugerido:** R$247/mes (inclui Modulos 1-4)
> **Publico:** Terapeuta avancada — leituras temporais

| PDF | Pasta | Tema |
|---|---|---|
| ASTROLOGIA.pdf | material Joel Aleixo | Astrologia alquimica |
| BIORRITIMOS.pdf | material Joel Aleixo | Biorritmos e ciclos |
| APROFUNDAMENTO NOS 7 CHACKRAS.pdf | material Joel Aleixo | 7 chakras em profundidade |
| O Fluxus Continuum de John Dee PDF (1).pdf | material Joel Aleixo | Fluxus Continuum |
| O Fluxus Continuum de John Dee PDF.pdf | material Joel Aleixo | Versao atualizada |

**Transcricoes YouTube relacionadas:**
- A Cura no mundo dos numeros.txt
- De Volta a Si O Caminho do Feminino Vivo.txt
- Gerar Vida Gerar Cura Gerar Oportunidades.txt
- Tem dores que nao pedem cura Pedem consciencia.txt

---

### Modulo 6 — Protocolos e Aplicacao Terapeutica
> **Preco sugerido:** R$297/mes (acesso total)
> **Publico:** Terapeuta formada — aplicacao pratica

| PDF | Pasta | Tema |
|---|---|---|
| COMO USAR OS PROTOCOLOS.pdf | material Joel Aleixo | Guia de protocolos |
| SIGNIFICADO KITE PRIMUS.pdf | material Joel Aleixo | Kit Primus |
| A Aura das flores.pdf | material Joel Aleixo | Florais e propriedades |
| Florais sutis.pdf | PENDENTE | Florais sutis |
| Anjos.pdf | PENDENTE | Arcanos angelicos |
| Cosmeticos.pdf | PENDENTE | Cosmeticos alquimicos |

**Transcricoes YouTube relacionadas:**
- Joel why cant I find every floral you mention here in the store.txt
- Self-Therapist Taking flower essences is a lifestyle.txt
- Floral Alchemy The soul of plants healing the human soul.txt
- Alchemy is practiced with Alchemical Flowers.txt
- Where do alchemical flowers act.txt
- Taking alchemical flowers is finding yourself.txt
- LIDERES TAMBEM ADOECEM.txt
- Dont underestimate the power of doing the basics.txt

---

## 3. Sistema de Tags para Busca Precisa

### Problema
Busca vetorial pura: "7 cores dos chakras" pode trazer chunks sobre "4 elementos" porque a semantica e proxima.

### Solucao: Tags hierarquicas + busca hibrida

#### Taxonomia de Tags proposta

```
NIVEL 1 — Categorias (amplas)
  fundamentos, elementos, matrix, dna, transmutacao, astrologia, chakra,
  biorritmo, fluxus, protocolo, floral, miasma, vitriol, torus

NIVEL 2 — Sub-categorias (especificas)
  # DNA
  dna_cor_vermelha, dna_cor_laranja, dna_cor_amarela, dna_cor_verde,
  dna_cor_azul, dna_cor_indigo, dna_cor_violeta, dna_leitura, dna_referencia

  # Elementos
  elemento_terra, elemento_agua, elemento_fogo, elemento_ar, pletora, phoenix

  # Chakras
  chakra_base, chakra_sacral, chakra_plexo, chakra_cardiaco,
  chakra_laringeo, chakra_frontal, chakra_coronario

  # Transmutacao
  nigredo, rubedo, albedo, aliastrum, tartarus, trindade

  # Matrix
  matrix_trauma, matrix_padrao, matrix_heranca, matrix_campo

  # Astrologia
  astro_mapa, astro_ciclo, astro_regente, astro_casa

  # Protocolos
  protocolo_uso, kit_primus, floral_sutil, floral_aura, cosmetico

  # Florais
  floral_planta, floral_cor, floral_indicacao, floral_mineral

  # Conceitos gerais
  pesquisa, faq, conceito_basico, definicao
```

#### Como as tags melhoram a busca

**Antes (so vetorial):**
```
Pergunta: "Quais sao as 7 cores do DNA?"
→ Busca vetorial retorna 5 chunks, 2 sao sobre chakras (semantica proxima)
```

**Depois (vetorial + filtro por tag):**
```
Pergunta: "Quais sao as 7 cores do DNA?"
→ Agente detecta intencao: tags = ["dna"]
→ Busca vetorial COM filtro WHERE tags @> '["dna"]'
→ Retorna 5 chunks, todos sobre DNA
```

---

## 4. Transcricao Estruturada (Chunks com Hierarquia)

### Problema
Hoje os chunks sao "fatias cegas" do texto — sem saber em que secao do PDF estamos.

### Solucao: Metadata hierarquica no chunk

Em vez de:
```json
{
  "conteudo": "O vermelho é a cor da base, da presença...",
  "metadata": {"arquivo_fonte": "DNA.pdf", "pagina": 4}
}
```

Proposta:
```json
{
  "conteudo": "O vermelho é a cor da base, da presença...",
  "metadata": {
    "arquivo_fonte": "DNA.pdf",
    "pagina": 4,
    "modulo": 3,
    "modulo_nome": "DNA Alquímico",
    "tags": ["dna", "dna_cor_vermelha", "chakra_base"],
    "secao": "DNA > Cores > Vermelho > Significado",
    "titulo_secao": "Cor Vermelha — Base e Presença",
    "fonte_tipo": "pdf"
  }
}
```

### Beneficios da hierarquia

1. **Busca precisa**: Filtrar por `secao LIKE 'DNA > Cores%'` para encontrar todas as cores do DNA
2. **Venda por modulo**: `WHERE modulo = 3` para restringir ao modulo pago
3. **Citacao rica**: Agente pode dizer "Segundo DNA.pdf, secao Cor Vermelha..."
4. **Navegacao**: Terapeuta pode pedir "me mostra todas as secoes do DNA" e receber um indice

---

## 5. Implementacao Pratica

### 5A. SQL — Novas colunas na tabela embeddings

```sql
-- Adicionar colunas para modulo, tags e secao
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS modulo INT;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS modulo_nome TEXT;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS secao TEXT;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS titulo_secao TEXT;
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS fonte_tipo TEXT DEFAULT 'pdf';

-- Indice GIN para busca por tags (array)
CREATE INDEX IF NOT EXISTS idx_embeddings_tags ON embeddings USING GIN (tags);

-- Indice para filtro por modulo
CREATE INDEX IF NOT EXISTS idx_embeddings_modulo ON embeddings (modulo);

-- Indice para filtro por fonte_tipo
CREATE INDEX IF NOT EXISTS idx_embeddings_fonte_tipo ON embeddings (fonte_tipo);
```

### 5B. SQL — Nova funcao de busca com filtros

```sql
-- Substituir a funcao buscar_chunks por uma versao com filtros opcionais
CREATE OR REPLACE FUNCTION buscar_chunks_v2(
  query_embedding vector(1536),
  p_terapeuta_id UUID,
  match_count INT DEFAULT 5,
  p_modulo INT DEFAULT NULL,
  p_tags TEXT[] DEFAULT NULL,
  p_fonte_tipo TEXT DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  conteudo TEXT,
  similaridade FLOAT,
  documento_id UUID,
  chunk_index INT,
  modulo INT,
  modulo_nome TEXT,
  tags TEXT[],
  secao TEXT,
  titulo_secao TEXT,
  fonte_tipo TEXT
)
LANGUAGE SQL STABLE
AS $$
  SELECT
    e.id,
    e.conteudo,
    1 - (e.embedding <=> query_embedding) AS similaridade,
    e.documento_id,
    e.chunk_index,
    e.modulo,
    e.modulo_nome,
    e.tags,
    e.secao,
    e.titulo_secao,
    e.fonte_tipo
  FROM embeddings e
  WHERE e.terapeuta_id = p_terapeuta_id
    AND (p_modulo IS NULL OR e.modulo = p_modulo)
    AND (p_tags IS NULL OR e.tags && p_tags)        -- overlap: qualquer tag em comum
    AND (p_fonte_tipo IS NULL OR e.fonte_tipo = p_fonte_tipo)
  ORDER BY e.embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### 5C. Script Python — Re-taguear chunks existentes

```python
"""
Script para adicionar modulo, tags e secao aos chunks existentes.
Baseado no mapeamento arquivo_fonte -> modulo/tags.
"""

# Mapeamento: nome_arquivo -> (modulo, modulo_nome, tags, fonte_tipo)
MAPEAMENTO_ARQUIVOS = {
    # --- Modulo 1: Fundamentos ---
    "Material de Pesquisa.pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "pesquisa", "conceito_basico"], "pdf"),
    "PESQUISA AVANCADA.pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "pesquisa"], "pdf"),
    "PESQUISA AVANÇADA.pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "pesquisa"], "pdf"),
    "PERGUNTAS FREQUENTES.pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "faq"], "pdf"),
    "PERGUNTAS FREQUENTES – 4 ELEMENTOS & PLETORA.pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "faq", "elementos", "pletora"], "pdf"),
    "M1.Apostila-Modulo-1 .pdf": (1, "Fundamentos e Pesquisa", ["fundamentos", "conceito_basico"], "pdf"),

    # --- Modulo 2: Elementos, Matrix e Campo ---
    "QUATRO ELEMENTOS E PLETORA.pdf": (2, "Elementos, Matrix e Campo", ["elementos", "pletora", "elemento_terra", "elemento_agua", "elemento_fogo", "elemento_ar"], "pdf"),
    "MATRIX E TRAUMAS.pdf": (2, "Elementos, Matrix e Campo", ["matrix", "matrix_trauma", "matrix_padrao"], "pdf"),
    "Miasmas.pdf": (2, "Elementos, Matrix e Campo", ["miasma", "matrix_heranca"], "pdf"),
    "M2.Apostila - Phoenix-e-Pletora .pdf": (2, "Elementos, Matrix e Campo", ["elementos", "pletora", "phoenix"], "pdf"),
    "M2.Apostila -Trindade-e-Tartarus.pdf": (2, "Elementos, Matrix e Campo", ["transmutacao", "trindade", "tartarus"], "pdf"),

    # --- Modulo 3: DNA Alquimico ---
    "DNA.pdf": (3, "DNA Alquimico", ["dna", "dna_leitura"], "pdf"),
    "REFERENCIA DO DNA.pdf": (3, "DNA Alquimico", ["dna", "dna_referencia"], "pdf"),
    "REFERÊNCIA DO DNA.pdf": (3, "DNA Alquimico", ["dna", "dna_referencia"], "pdf"),
    "M3.Apostila Módulo 3.pdf": (3, "DNA Alquimico", ["dna"], "pdf"),

    # --- Modulo 4: Transmutacao ---
    "Apostila Trindade e Tartarus - Nigredo.pdf": (4, "Transmutacao", ["transmutacao", "nigredo", "trindade", "tartarus"], "pdf"),
    "Apostila Rubedo - 1ª Edição (1).pdf": (4, "Transmutacao", ["transmutacao", "rubedo"], "pdf"),
    "Apostila Rubedo - 1a Edicao (1).pdf": (4, "Transmutacao", ["transmutacao", "rubedo"], "pdf"),
    "M4.Apostila - Alquimia Avançada.pdf": (4, "Transmutacao", ["transmutacao", "aliastrum"], "pdf"),
    "M4.Apostila - Alquimia Avancada.pdf": (4, "Transmutacao", ["transmutacao", "aliastrum"], "pdf"),
    "M4.Apostila Aliastrum.pdf": (4, "Transmutacao", ["transmutacao", "aliastrum"], "pdf"),
    "M4.Apostila Matrix.pdf": (4, "Transmutacao", ["matrix", "matrix_campo"], "pdf"),
    "M4.apostila_guia_vitriol_torus_06.05.16 - Logo Escola de Alquimia (1).pdf": (4, "Transmutacao", ["vitriol", "torus"], "pdf"),

    # --- Modulo 5: Astrologia e Ciclos ---
    "ASTROLOGIA.pdf": (5, "Astrologia, Ciclos e Chakras", ["astrologia", "astro_mapa", "astro_ciclo"], "pdf"),
    "BIORRITIMOS.pdf": (5, "Astrologia, Ciclos e Chakras", ["biorritmo", "astro_ciclo"], "pdf"),
    "APROFUNDAMENTO NOS 7 CHACKRAS.pdf": (5, "Astrologia, Ciclos e Chakras", ["chakra", "chakra_base", "chakra_sacral", "chakra_plexo", "chakra_cardiaco", "chakra_laringeo", "chakra_frontal", "chakra_coronario"], "pdf"),
    "O Fluxus Continuum de John Dee PDF (1).pdf": (5, "Astrologia, Ciclos e Chakras", ["fluxus", "astro_ciclo"], "pdf"),
    "O Fluxus Continuum de John Dee PDF.pdf": (5, "Astrologia, Ciclos e Chakras", ["fluxus", "astro_ciclo"], "pdf"),

    # --- Modulo 6: Protocolos ---
    "COMO USAR OS PROTOCOLOS.pdf": (6, "Protocolos e Aplicacao", ["protocolo", "protocolo_uso"], "pdf"),
    "SIGNIFICADO KITE PRIMUS.pdf": (6, "Protocolos e Aplicacao", ["protocolo", "kit_primus"], "pdf"),
    "SIGNIFICADO KITE PRIMUS.pdf": (6, "Protocolos e Aplicacao", ["protocolo", "kit_primus"], "pdf"),
    "A Aura das flores.pdf": (6, "Protocolos e Aplicacao", ["floral", "floral_aura", "floral_planta"], "pdf"),
}

# Para cada chunk existente:
# 1. Ler metadata.arquivo_fonte
# 2. Lookup no MAPEAMENTO_ARQUIVOS
# 3. UPDATE embeddings SET modulo=X, modulo_nome=Y, tags=Z WHERE id=chunk_id
```

### 5D. Mudanca no Retriever (busca hibrida)

Atualizar `src/rag/retriever.py` para:

1. **Detectar intencao da pergunta** (com Claude ou regras simples)
2. **Extrair tags relevantes** da pergunta
3. **Chamar `buscar_chunks_v2`** com filtros de modulo e tags
4. **Fallback**: se a busca filtrada retornar poucos resultados, buscar sem filtro

Exemplo de fluxo:
```
Pergunta: "O que significa a cor vermelha no DNA?"
→ Tags detectadas: ["dna", "dna_cor_vermelha"]
→ buscar_chunks_v2(embedding, terapeuta_id, 5, modulo=3, tags=["dna"])
→ 5 chunks todos sobre DNA, altamente relevantes
```

### 5E. Controle de acesso por modulo

```python
# No webhook handler, antes de buscar chunks:
async def verificar_acesso_modulo(terapeuta_id: str, modulo: int) -> bool:
    """Verifica se o terapeuta tem acesso ao modulo solicitado."""
    # Consulta a tabela de assinaturas/modulos do terapeuta
    resultado = supabase.table("terapeuta_modulos") \
        .select("modulo") \
        .eq("terapeuta_id", terapeuta_id) \
        .eq("modulo", modulo) \
        .eq("ativo", True) \
        .execute()
    return len(resultado.data) > 0
```

Nova tabela necessaria:
```sql
CREATE TABLE terapeuta_modulos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  terapeuta_id UUID REFERENCES terapeutas(id) ON DELETE CASCADE,
  modulo INT NOT NULL CHECK (modulo BETWEEN 1 AND 6),
  ativo BOOLEAN DEFAULT true,
  data_inicio TIMESTAMPTZ DEFAULT now(),
  data_fim TIMESTAMPTZ,
  UNIQUE(terapeuta_id, modulo)
);

CREATE INDEX idx_terapeuta_modulos ON terapeuta_modulos(terapeuta_id, modulo);
```

---

## 6. Estimativa de Esforco

| Tarefa | Horas | Prioridade |
|---|---|---|
| SQL: adicionar colunas e indices | 0.5h | P0 |
| SQL: funcao buscar_chunks_v2 | 0.5h | P0 |
| Python: script de re-tagueamento dos 9.246 chunks | 2h | P0 |
| Python: atualizar retriever com busca hibrida | 2h | P0 |
| SQL: tabela terapeuta_modulos | 0.5h | P1 |
| Python: logica de controle de acesso | 1h | P1 |
| Python: deteccao de intencao (tags da pergunta) | 3h | P1 |
| Transcricao estruturada dos PDFs (secoes/titulos) | 4h | P2 |
| Testes e ajustes | 2h | P0 |
| **TOTAL** | **~16h** | |

### Fases sugeridas

**Fase A (rapida, 1 dia):** SQL + re-tagueamento + retriever atualizado
- Colunas novas, indices, funcao v2, script de tags, retriever hibrido
- Resultado: busca ja fica mais precisa com filtros por modulo e tags

**Fase B (2-3 dias):** Controle de acesso e deteccao de intencao
- Tabela terapeuta_modulos, logica de acesso, deteccao de tags na pergunta
- Resultado: venda por modulos funcionando

**Fase C (quando houver tempo):** Transcricao estruturada
- Re-processar PDFs extraindo titulos/secoes
- Atualizar metadata dos chunks com hierarquia (secao, titulo_secao)
- Resultado: buscas ultra-precisas e citacoes ricas

---

## 7. Riscos e Consideracoes

1. **Re-tagueamento NAO exige re-embeddar**: so atualiza colunas de metadata, nao muda o embedding. Custo zero em API.

2. **Tags manuais vs automaticas**: O mapeamento por arquivo_fonte cobre 100% dos chunks existentes. Tags mais granulares (ex: `dna_cor_vermelha` dentro do PDF `DNA.pdf`) precisariam de analise do conteudo do chunk — possivel com Claude classificando cada chunk, mas com custo de API.

3. **Busca hibrida pode ser mais lenta**: Filtro por tag + ordenacao vetorial. Mitigacao: indice GIN nas tags + indice ivfflat no embedding ja existem.

4. **3 PDFs pendentes** (Florais sutis, Anjos, Cosmeticos): Quando chegarem, ja entram com tags e modulo desde o processamento.

5. **Transcricoes do YouTube**: Atualmente nao estao na tabela embeddings. Se forem adicionadas, usar `fonte_tipo = 'youtube'` e as mesmas tags.

---

## 8. Inventario Completo dos Materiais

### PDFs — Pasta `materiais/material Joel Aleixo/` (20 arquivos)

| # | Arquivo | Modulo | Tags Primarias |
|---|---|---|---|
| 1 | Material de Pesquisa.pdf | 1 | fundamentos, pesquisa |
| 2 | PESQUISA AVANCADA.pdf | 1 | fundamentos, pesquisa |
| 3 | PERGUNTAS FREQUENTES.pdf | 1 | fundamentos, faq |
| 4 | PERGUNTAS FREQUENTES – 4 ELEMENTOS & PLETORA.pdf | 1 | fundamentos, faq, elementos |
| 5 | PRIMEIRO PASSO.docx | 1 | fundamentos |
| 6 | QUATRO ELEMENTOS E PLETORA.pdf | 2 | elementos, pletora |
| 7 | MATRIX E TRAUMAS.pdf | 2 | matrix, matrix_trauma |
| 8 | Miasmas.pdf | 2 | miasma |
| 9 | DNA.pdf | 3 | dna, dna_leitura |
| 10 | REFERENCIA DO DNA.pdf | 3 | dna, dna_referencia |
| 11 | Apostila Trindade e Tartarus - Nigredo.pdf | 4 | nigredo, trindade, tartarus |
| 12 | Apostila Rubedo - 1a Edicao (1).pdf | 4 | rubedo |
| 13 | ASTROLOGIA.pdf | 5 | astrologia |
| 14 | BIORRITIMOS.pdf | 5 | biorritmo |
| 15 | APROFUNDAMENTO NOS 7 CHACKRAS.pdf | 5 | chakra |
| 16 | O Fluxus Continuum de John Dee PDF (1).pdf | 5 | fluxus |
| 17 | O Fluxus Continuum de John Dee PDF.pdf | 5 | fluxus |
| 18 | COMO USAR OS PROTOCOLOS.pdf | 6 | protocolo |
| 19 | SIGNIFICADO KITE PRIMUS.pdf | 6 | kit_primus |
| 20 | A Aura das flores.pdf | 6 | floral, floral_aura |

### PDFs — Pasta `materiais/APOSTILAS/` (8 arquivos)

| # | Arquivo | Modulo | Tags Primarias |
|---|---|---|---|
| 1 | M1.Apostila-Modulo-1.pdf | 1 | fundamentos |
| 2 | M2.Apostila - Phoenix-e-Pletora.pdf | 2 | elementos, phoenix, pletora |
| 3 | M2.Apostila -Trindade-e-Tartarus.pdf | 2 | trindade, tartarus |
| 4 | M3.Apostila Modulo 3.pdf | 3 | dna |
| 5 | M4.Apostila - Alquimia Avancada.pdf | 4 | transmutacao |
| 6 | M4.Apostila Aliastrum.pdf | 4 | aliastrum |
| 7 | M4.Apostila Matrix.pdf | 4 | matrix |
| 8 | M4.apostila_guia_vitriol_torus.pdf | 4 | vitriol, torus |

### Transcricoes YouTube (29 arquivos)

| # | Transcricao | Modulo Sugerido | Tags Primarias |
|---|---|---|---|
| 1 | A Cura no mundo dos numeros.txt | 5 | biorritmo, astrologia |
| 2 | A Escolha de Curar.txt | 1 | fundamentos |
| 3 | A vida so muda quando escutamos o chamado da alma.txt | 1 | fundamentos |
| 4 | Alchemy is practiced with Alchemical Flowers.txt | 6 | floral |
| 5 | Cure-se de quem nao e voce.txt | 1 | fundamentos, matrix_padrao |
| 6 | Da Historia da Arte a Arte de Curar.txt | 2 | elementos |
| 7 | De Volta a Si O Caminho do Feminino Vivo.txt | 5 | chakra, biorritmo |
| 8 | Dermatite pressao infertilidade E AGORA.txt | 2 | miasma, matrix_trauma |
| 9 | Do Bournout a Cura.txt | 4 | transmutacao, matrix_trauma |
| 10 | Dont underestimate the power of doing the basics.txt | 6 | protocolo |
| 11 | Every cancer patient I have treated.txt | 3 | dna, matrix_heranca |
| 12 | Floral Alchemy The soul of plants.txt | 6 | floral |
| 13 | Gerar Vida Gerar Cura Gerar Oportunidades.txt | 5 | biorritmo |
| 14 | How to awaken the spiritual self.txt | 3 | dna, chakra |
| 15 | Joel why cant I find every floral.txt | 6 | floral, protocolo |
| 16 | Limiting Beliefs Stories You Tell Yourself.txt | 2 | matrix_padrao |
| 17 | Living by Alchemy.txt | 1 | fundamentos |
| 18 | LIDERES TAMBEM ADOECEM.txt | 6 | protocolo, matrix_trauma |
| 19 | O Encontro Que Fechou Um Ciclo de 30 Anos.txt | 4 | transmutacao |
| 20 | PARE DE HERDAR O QUE NAO E SEU.txt | 2 | matrix_heranca, miasma |
| 21 | QUANDO A VOZ CALA O CORPO GRITA.txt | 3 | dna, matrix_trauma |
| 22 | QUANDO VOCE MUDA TUDO MUDA.txt | 4 | transmutacao |
| 23 | Quando nada preenche.txt | 4 | transmutacao, matrix_padrao |
| 24 | Self-Therapist Taking flower essences.txt | 6 | floral, protocolo |
| 25 | Survival mechanisms in childhood.txt | 2 | matrix_heranca |
| 26 | Taking alchemical flowers is finding yourself.txt | 6 | floral |
| 27 | Tem dores que nao pedem cura.txt | 5 | chakra |
| 28 | The liberating power of forgiveness.txt | 4 | transmutacao |
| 29 | Where do alchemical flowers act.txt | 6 | floral |

---

## 9. Diagrama Resumo

```
ANTES:
  [Pergunta] → embedding → busca cosine → top 5 chunks (qualquer tema)

DEPOIS:
  [Pergunta] → detectar tags → embedding → busca cosine COM filtro
                                            ↓
                                   WHERE modulo IN (modulos_pagos)
                                   AND tags && tags_detectadas
                                            ↓
                                   top 5 chunks (tema preciso, modulo autorizado)
```

---

> **Proximos passos:** Lucas decide quais fases implementar e em que ordem.
> Recomendacao: comecar pela Fase A (SQL + re-tagueamento) — resultado imediato em 1 dia.
