"""
Fase 2 — Indexação de documentos de conhecimento estruturado.

Cobre os gaps identificados na auditoria:
- Kits avançados: Corpus Celestes, Kit Matrix, Kit Torus, Alliastrum, Vitriol
- Estágios alquímicos: Nigredo, Albedo, Rubedo
- Padrões ancestrais: Serpente do Pai/Mãe detalhadas, Eclipses
- Mapeamento sintomas → causas alquímicas
- Anamnese alquímica procedural
- Miasmas
"""

import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.rag.processor import dividir_em_chunks, gerar_embeddings, salvar_chunks_no_supabase

TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"


def criar_documento_no_banco(titulo: str) -> str:
    supabase = get_supabase()
    doc_id = str(uuid.uuid4())
    supabase.table("documentos").insert({
        "id": doc_id,
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": titulo,
        "tipo": "pdf",
        "tamanho_bytes": 0,
        "storage_path": f"knowledge/{doc_id}.txt",
        "total_chunks": 0,
        "processado": True,
    }).execute()
    print(f"  [+] Criado: {doc_id} — {titulo}")
    return doc_id


def remover_antigo(titulo: str) -> None:
    supabase = get_supabase()
    resultado = supabase.table("documentos").select("id").eq("terapeuta_id", TERAPEUTA_ID).eq("nome_arquivo", titulo).execute()
    for doc in resultado.data:
        supabase.table("embeddings").delete().eq("documento_id", doc["id"]).execute()
        supabase.table("documentos").delete().eq("id", doc["id"]).execute()
        print(f"  [-] Removido antigo: {doc['id']}")


async def indexar(titulo: str, conteudo: str, tags: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"Indexando: {titulo}")
    print(f"{'='*60}")
    remover_antigo(titulo)
    doc_id = criar_documento_no_banco(titulo)
    chunks = dividir_em_chunks(conteudo)
    print(f"  [+] {len(chunks)} chunks")
    embeddings = await gerar_embeddings(chunks)
    supabase = get_supabase()
    registros = [
        {
            "terapeuta_id": TERAPEUTA_ID,
            "documento_id": doc_id,
            "conteudo": chunk,
            "embedding": embedding,
            "chunk_index": idx,
            "tags": tags,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    for i in range(0, len(registros), 50):
        supabase.table("embeddings").insert(registros[i:i+50]).execute()
    print(f"  [+] {len(registros)} chunks salvos com tags={tags}")


DOCS = {}
TAGS = {}

# ===========================================================================
# CORPUS CELESTES — 12 FLORAIS ASTROLÓGICOS
# ===========================================================================
DOCS["Corpus Celestes — 12 Florais Astrológicos do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — CORPUS CELESTES
Keywords: corpus celestes, florais astrológicos, 12 archetypes, doze arquétipos, signos florais, áries floral, touro floral, gêmeos floral, câncer floral, leão floral, virgem floral, libra floral, escorpião floral, sagitário floral, capricórnio floral, aquário floral, peixes floral

Os Corpus Celestes são os 12 florais astrológicos do método Joel Aleixo.
Cada floral ativa um arquétipo interior específico, conectando a pessoa ao seu propósito de vida.
NÃO são Florais de Bach — são florais alquímicos exclusivos do método Joel Aleixo.

OS 12 CORPUS CELESTES:

1. ÁRIES (Corpus Celestes Áries)
Arquétipo: O Guerreiro, o Pioneiro, o Corajoso
Indicação: Falta de coragem, iniciativa bloqueada, dificuldade de começar, passividade.
Quando usar: Paciente que não age, não arrisca, fica na zona de conforto.
Chakra correspondente: Basal
Elemento: Fogo

2. TOURO (Corpus Celestes Touro)
Arquétipo: O Construtor, o Próspero, o Persistente
Indicação: Dificuldade de sustentar projetos, falta de paciência, bloqueios de prosperidade material.
Quando usar: Paciente que começa mas não termina, insegurança financeira crônica.
Chakra correspondente: Basal/Umbilical
Elemento: Terra

3. GÊMEOS (Corpus Celestes Gêmeos)
Arquétipo: O Comunicador, o Mediador, o Curioso
Indicação: Dificuldade de comunicação, dualidade interna, excesso de mentalizações.
Quando usar: Paciente que fala demais mas não age, ou que pensa mas não expressa.
Chakra correspondente: Laríngeo
Elemento: Ar

4. CÂNCER (Corpus Celestes Câncer)
Arquétipo: O Nutridor, o Protetor, o Sensível
Indicação: Dificuldade de cuidar sem se perder, limites no cuidado, hipersensibilidade.
Quando usar: Síndrome do cuidador, dificuldade de receber cuidado.
Chakra correspondente: Cardíaco/Umbilical
Elemento: Água

5. LEÃO (Corpus Celestes Leão)
Arquétipo: O Rei/Rainha, o Criativo, o Amor-Próprio
Indicação: Baixa autoestima, necessidade excessiva de aprovação, dificuldade de brilhar.
Quando usar: Paciente que se apaga para os outros, não se valoriza.
Chakra correspondente: Plexo Solar/Cardíaco
Elemento: Fogo

6. VIRGEM (Corpus Celestes Virgem)
Arquétipo: O Servidor, o Perfeccionista, o Analítico
Indicação: Perfeccionismo paralisante, crítica excessiva a si mesmo, dificuldade de servir com alegria.
Quando usar: Paciente muito autocrítico, nunca satisfeito com o próprio trabalho.
Chakra correspondente: Plexo Solar/Laríngeo
Elemento: Terra

7. LIBRA (Corpus Celestes Libra)
Arquétipo: O Mediador, o Justo, o Harmonizador
Indicação: Dificuldade de tomar decisões, conflitos em relacionamentos, desequilíbrio.
Quando usar: Paciente indeciso, sempre tentando agradar todos, sem posicionamento próprio.
Chakra correspondente: Cardíaco
Elemento: Ar

8. ESCORPIÃO (Corpus Celestes Escorpião)
Arquétipo: O Transformador, o Detetive, o Renascido
Indicação: Resistência à transformação, padrões obsessivos, apego ao que deve morrer.
Quando usar: Paciente que se recusa a mudar, ciúme extremo, controle obsessivo.
Chakra correspondente: Umbilical/Basal
Elemento: Água

9. SAGITÁRIO (Corpus Celestes Sagitário)
Arquétipo: O Filósofo, o Aventureiro, o Expansivo
Indicação: Falta de fé e propósito, visão limitada, medo do futuro.
Quando usar: Paciente sem esperança, cynismo, falta de visão de futuro.
Chakra correspondente: Coronário/Frontal
Elemento: Fogo

10. CAPRICÓRNIO (Corpus Celestes Capricórnio)
Arquétipo: O Mestre, o Realizado, o Estruturado
Indicação: Dificuldade de estruturar projetos, falta de disciplina, imaturidade emocional.
Quando usar: Paciente que não termina nada, dificuldade de comprometimento.
Chakra correspondente: Basal
Elemento: Terra

11. AQUÁRIO (Corpus Celestes Aquário)
Arquétipo: O Visionário, o Revolucionário, o Inovador
Indicação: Rigidez mental, resistência ao novo, isolamento, negação da intuição.
Quando usar: Paciente preso em velhos padrões, não aceita novas perspectivas.
Chakra correspondente: Frontal/Coronário
Elemento: Ar

12. PEIXES (Corpus Celestes Peixes)
Arquétipo: O Místico, o Compaixão, o Transcendente
Indicação: Dificuldade de conexão espiritual, materialismo excessivo, falta de empatia.
Quando usar: Paciente desconectado da espiritualidade, sem compaixão por si mesmo.
Chakra correspondente: Coronário
Elemento: Água

COMO USAR OS CORPUS CELESTES:
- Prescrever o arquétipo que o paciente mais PRECISA desenvolver (não o que já tem)
- Combinar com florais do Kit Primus do chakra correspondente
- Podem ser usados em conjunto com o mapa natal (planeta regente do signo comprometido)
- Geralmente prescritos na fase de Rubedo (estágio avançado do tratamento)
"""
TAGS["Corpus Celestes — 12 Florais Astrológicos do Método Joel Aleixo"] = ["floral", "kit_primus", "astrologia", "corpus_celestes", "protocolo", "fundamentos"]

# ===========================================================================
# KIT MATRIX / MATERLUX
# ===========================================================================
DOCS["Kit Matrix (Materlux) — Portal Feminino e Traumas Intrauterinos"] = """
CONHECIMENTO ESTRUTURADO — KIT MATRIX / MATERLUX
Keywords: kit matrix, materlux, 8º chakra, oitavo chakra, portal feminino, traumas intrauterinos, infertilidade, miomas, linhagem feminina, gravidez, gestação, 9 meses

O Kit Matrix (também chamado Materlux) trabalha o 8º chakra sutil localizado acima da cabeça da mulher.
É o portal criativo feminino — onde o espírito entra para criar vida e expressar criatividade.

O QUE É A MATRIX:
A Matrix é o grande chakra sutil da mulher, acima do chakra coronário.
Função: portal de conexão com o ecossistema feminino e com a capacidade criativa.
Quando a Matrix está saudável: a mulher flui em criatividade, fertilidade, conexão com a natureza.
Quando a Matrix está danificada: infertilidade, miomas, bloqueio criativo, desconexão do feminino.

CAUSAS DE DANO À MATRIX:
1. Traumas intrauterinos: durante os 9 meses de gestação, o bebê absorve emocionalmente as ondas de medo, insegurança e rejeição da mãe. A placenta não consegue filtrar essas ondas emocionais. O espírito do bebê comprime esses traumas em partículas (carvões) depositados na estrutura óssea em formação.
2. Traumas da linhagem feminina: avós, bisavós que carregaram traumas femininos (abortos forçados, violência, supressão da sexualidade).
3. Desconexão do ecossistema feminino: quando a mulher nega ou suprime o feminino (muito foco no masculino, negação da maternidade/criatividade).

MANIFESTAÇÕES CLÍNICAS DE MATRIX DANIFICADA:
- Infertilidade idiopática (sem causa médica aparente)
- Miomas, cistos, endometriose
- Bloqueio criativo severo (não consegue criar nada)
- Dificuldade de conectar-se com outras mulheres
- Abortos de repetição
- Dificuldade de receber e dar amor materno

CASO CLÍNICO PARADIGMÁTICO:
Professora de robótica, infértil há 10 anos, tentou todos os tratamentos médicos sem sucesso.
Tratamento alquímico: Kit Matrix + limpeza de traumas intrauterinos.
Resultado inesperado: criatividade bloqueada foi liberada → escreveu 10 livros em 6 meses.
Resultado final: ao aceitar que sua vida já estava completa (os livros eram sua criação), engravidou naturalmente.
Lição: infertilidade frequentemente é bloqueio criativo disfarçado.

TRATAMENTO COM KIT MATRIX:
1. Kit Matrix (Materlux): restaura o portal criativo feminino
2. Kit Traumas Intrauterinos: limpa os carvões depositados na estrutura óssea desde a gestação
3. Serpente da Mãe: se há trauma da linhagem materna
4. Corpus Celestes (Câncer ou Peixes): para reconexão com o feminino sagrado

PERGUNTAS DIAGNÓSTICAS:
- "Como foi a gravidez da sua mãe com você?" (traumas intrauterinos)
- "Sua mãe ou avó teve dificuldades com gravidez?" (herança de linhagem)
- "O que você sempre quis criar mas nunca criou?" (bloqueio criativo Matrix)
- "Como é sua relação com outras mulheres?" (ecossistema feminino)
"""
TAGS["Kit Matrix (Materlux) — Portal Feminino e Traumas Intrauterinos"] = ["matrix", "matrix_trauma", "matrix_heranca", "floral", "protocolo", "fundamentos"]

# ===========================================================================
# KIT TORUS
# ===========================================================================
DOCS["Kit Torus — Força Metabólica e Alinhamento Pensar-Sentir-Fazer"] = """
CONHECIMENTO ESTRUTURADO — KIT TORUS
Keywords: kit torus, torus, força metabólica, metabolismo, atrair parcerias, parceiro errado, lugar errado, sincronicidade, estar no lugar certo, alinhamento, pensar sentir fazer

O Kit Torus trabalha a força metabólica do indivíduo.
Promove o alinhamento entre o que a pessoa PENSA, SENTE e FAZ.

O QUE É O TORUS:
O Torus é a forma energética que circunda e permeia todos os seres vivos.
Quando equilibrado: a pessoa está no lugar certo, na hora certa, com as pessoas certas.
Quando desequilibrado: a pessoa fica atraindo sócios, parceiros e situações erradas.

INDICAÇÕES DO KIT TORUS:
- Paciente que sempre atrai o mesmo tipo de parceiro amoroso (padrão repetitivo)
- Sócios que sempre dão errado (traições, incompatibilidades, conflitos)
- Sensação de estar no lugar errado o tempo todo
- Dificuldade de realizar o que pensa e planeja
- Projetos que não saem do papel apesar do esforço
- Sincronicidades ausentes — a vida "não flui"
- Pensamentos, emoções e ações em direções opostas

MECANISMO ALQUÍMICO:
O Torus regula o campo metabólico que emite a frequência de atração.
Se o campo está desalinhado, a pessoa emite uma frequência que atrai o oposto do que deseja.
O tratamento reajusta o campo → a pessoa começa a atrair o que realmente ressoa com sua missão.

COMO IDENTIFICAR NECESSIDADE DO TORUS:
1. Perguntar: "Você sempre atrai o mesmo tipo de pessoa em relacionamentos?"
2. Perguntar: "Seus projetos costumam travar na mesma fase?"
3. Perguntar: "Você sente que as coisas que você quer estão sempre fora do seu alcance?"
4. Observar padrões repetitivos de sócios/parceiros/situações

COMBINAÇÃO COM OUTROS FLORAIS:
- Torus + Serpente do Pai: quando o padrão de atração vem da linhagem paterna
- Torus + Kit DNA: quando o padrão de atração é ancestral (várias gerações)
- Torus + Corpus Celestes Libra: quando há dificuldade de escolher parceiros saudáveis
"""
TAGS["Kit Torus — Força Metabólica e Alinhamento Pensar-Sentir-Fazer"] = ["torus", "floral", "protocolo", "fundamentos"]

# ===========================================================================
# VITRIOL
# ===========================================================================
DOCS["Vitriol — Carbono Siberiano e Desobediência Civil ao Espírito"] = """
CONHECIMENTO ESTRUTURADO — VITRIOL / V.I.T.R.I.O.L.
Keywords: vitriol, V.I.T.R.I.O.L., carbono siberiano, desobediência espiritual, desobediência civil ao espírito, descarbonização, missão negada, propósito bloqueado, reconnect spirit

O Vitriol (também escrito V.I.T.R.I.O.L.) é um dos florais mais avançados do método Joel Aleixo.
Base: carbono siberiano — mineral de origem espacial, altamente ordenado energeticamente.

O QUE É DESOBEDIÊNCIA CIVIL AO ESPÍRITO:
Quando a pessoa persiste em negar sua missão de vida, em viver de forma contrária ao seu propósito espiritual, ela acumula "carbonização" — uma espécie de escuridão energética que bloqueia toda e qualquer transformação.
Sinais de carbonização espiritual:
- Já tentou de tudo e nada funciona
- Tratamentos não surtem efeito duradouro
- Vida estagna em todas as frentes simultaneamente
- Paciente que sabe o que deveria fazer mas não faz
- Recusa sistemática de seu próprio potencial
- Doença da alma: quando o problema não é físico nem emocional, mas espiritual

QUANDO USAR O VITRIOL:
- Pacientes que já fizeram terapia, tratamentos alternativos e convencionais sem resultado
- Vida estagnada há muitos anos sem causa aparente
- Negação intensa do próprio potencial e dons
- Paciente que se autossabota em todas as áreas
- Casos onde os florais do Kit Primus e DNA não estão surtindo efeito
- "Doença da alma" — quando o corpo adoece porque a alma não está sendo obedecida

MECANISMO ALQUÍMICO DO VITRIOL:
O carbono siberiano atua como descarbonizador espiritual.
Dissolve as camadas de resistência acumuladas pela desobediência ao propósito.
Cria clareza e receptividade para os demais tratamentos agirem.
Geralmente prescrito ANTES dos outros florais em casos severos de estagnação.

DISTINÇÃO IMPORTANTE — CRENÇA vs CONVICÇÃO:
- Crença (limitante): padrão herdado, instalado por outros ("você não consegue", "dinheiro é sujo")
- Convicção: certeza baseada em experiência própria, nascida de dentro
O Vitriol atua especificamente sobre as CRENÇAS limitantes que bloqueiam a convicção e o propósito.

POSOLOGIA TÍPICA DO VITRIOL:
Geralmente usado em ciclos curtos (7-14 dias) como "abridor de caminho" antes de protocolos mais longos.
Combinado com: Kit DNA (padrões ancestrais) + Kit Primus do chakra mais comprometido.
"""
TAGS["Vitriol — Carbono Siberiano e Desobediência Civil ao Espírito"] = ["vitriol", "floral", "protocolo", "fundamentos", "transmutacao"]

# ===========================================================================
# ALLIASTRUM
# ===========================================================================
DOCS["Alliastrum — Florais Minerais de 3,5 Anos do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — ALLIASTRUM
Keywords: alliastrum, florais minerais, pedras, cristais, minerais, ouro prata diamante safira esmeralda, 3,5 anos processamento, 3 anos e meio, virtudes interiores, arquétipos minerais

O Alliastrum é uma linha de florais avançados do método Joel Aleixo feitos com minerais e pedras preciosas.
Característica única: minerais triturados e processados por 3 anos e meio em equipamento especial para se combinarem com a molécula da água.

O QUE É O ALLIASTRUM:
Diferente dos florais de flores, o Alliastrum usa o poder de minerais e pedras.
Cada mineral possui uma frequência específica que desperta uma virtude interior correspondente.
O processo de 3,5 anos de preparação garante que a memória mineral seja completamente transferida para a água.

MINERAIS E SUAS CORRESPONDÊNCIAS:

Ouro (Alliastrum Ouro)
Virtude: Soberania, realeza interior, autoestima máxima
Indicação: Paciente que se coloca em posição inferior, não reconhece seu próprio valor
Arquétipo: Leão (Rei/Rainha)

Prata (Alliastrum Prata)
Virtude: Intuição, receptividade lunar, feminino sagrado
Indicação: Intuição bloqueada, desconexão do feminino, dificuldade de receber
Arquétipo: Câncer (Nutridor)

Diamante (Alliastrum Diamante)
Virtude: Clareza absoluta, pureza, invulnerabilidade espiritual
Indicação: Confusão mental severa, vulnerabilidade energética extrema, limpeza profunda
Arquétipo: Frontal/Coronário

Ferro (Alliastrum Ferro)
Virtude: Coragem, força guerreira, determinação
Indicação: Falta de determinação extrema, medo paralisante, fraqueza de vontade
Arquétipo: Áries (Guerreiro)

Esmeralda (Alliastrum Esmeralda)
Virtude: Prosperidade, fertilidade, crescimento abundante
Indicação: Bloqueios de prosperidade crônicos, infertilidade (combinado com Matrix)
Arquétipo: Touro (Construtor)

Safira (Alliastrum Safira)
Virtude: Sabedoria, verdade, claridade espiritual
Indicação: Confusão espiritual, busca de propósito em fase avançada do tratamento
Arquétipo: Sagitário

QUANDO PRESCREVER ALLIASTRUM:
- Casos avançados onde os florais de flores não estão sendo suficientes
- Pacientes em estágio de Rubedo (obra vermelha — fase avançada)
- Quando é necessário trabalhar virtudes específicas que o paciente precisa desenvolver
- Em combinação com o Corpus Celestes do arquétipo correspondente

COMO SE DIFERENCIA DO KIT PRIMUS:
- Kit Primus: trabalha situações emocionais e padrões comportamentais do cotidiano
- Alliastrum: trabalha virtudes arquetípicas profundas e essência espiritual
- Alliastrum geralmente prescrito na fase 3 do tratamento, após Kit Primus + DNA já atuarem
"""
TAGS["Alliastrum — Florais Minerais de 3,5 Anos do Método Joel Aleixo"] = ["floral", "alliastrum", "protocolo", "transmutacao", "fundamentos"]

# ===========================================================================
# NIGREDO / ALBEDO / RUBEDO
# ===========================================================================
DOCS["Estágios Alquímicos — Nigredo, Albedo e Rubedo no Tratamento"] = """
CONHECIMENTO ESTRUTURADO — NIGREDO, ALBEDO, RUBEDO
Keywords: nigredo, albedo, rubedo, obra negra, obra branca, obra vermelha, estágios alquímicos, fases do tratamento, limpeza alquímica, crise de cura, transmutação alquímica

Os três grandes estágios alquímicos indicam em que fase do tratamento o paciente se encontra.
Identificar o estágio correto é essencial para ajustar o protocolo terapêutico.

NIGREDO — A Obra Negra (Fase de Limpeza)

O que é: Fase de desintoxicação e limpeza. O organismo começa a expulsar traumas, crenças e padrões acumulados.

SINAIS CLÍNICOS DO NIGREDO:
- Sensação de peso, cansaço excessivo (sem causa física aparente)
- Sonhos com sujeira, lixo, lugares escuros ou sujos
- Choro sem motivo aparente
- Sintomas físicos temporários que parecem piora (é limpeza, não piora)
- Emoções antigas surgindo à tona (raiva, tristeza de coisas passadas)
- "Tudo saindo para fora" — como se a vida viesse à tona

O QUE FAZER NO NIGREDO:
- Tranquilizar o paciente: "Isso é o tratamento funcionando"
- Manter o protocolo de florais — não mudar prematuramente
- Incentivar sono e repouso (limpeza acontece no sono)
- Aumentar ingesta de água pura
- Evitar adicionar novos florais até a limpeza se completar
- Duração típica: 14-28 dias de sintomas de limpeza

FRASE PARA O PACIENTE: "O que você está sentindo são os carvões sendo liberados. Quando a fumaça sai, é porque o fogo está ativo."

---

ALBEDO — A Obra Branca (Fase de Clareza)

O que é: Fase de iluminação e clareza emergente. O paciente começa a ver padrões que antes eram invisíveis.

SINAIS CLÍNICOS DO ALBEDO:
- Clareza mental crescente
- Insights sobre padrões familiares ("agora eu entendo por que meu pai era assim")
- Interesse em espiritualidade, astrologia, propósito de vida
- Sonhos com luz, água limpa, coisas brancas ou prateadas
- Sensação de leveza física após período pesado
- Começa a "ver" suas próprias sombras com curiosidade, não com julgamento

O QUE FAZER NO ALBEDO:
- Intensificar trabalho com mapa natal alquímico
- Introduzir Corpus Celestes para conexão com arquétipos
- Aprofundar as perguntas diagnósticas sobre missão e propósito
- O paciente está receptivo para entender o método — pode ensinar mais
- Florais de clareza frontal/coronária ganham força nessa fase

---

RUBEDO — A Obra Vermelha (Fase Avançada)

O que é: Fase de integração e expressão dos potenciais. O paciente começa a viver seu propósito.

SINAIS CLÍNICOS DO RUBEDO:
- Sonhos reveladores sobre o futuro e a missão
- Ações alinhadas com o propósito de vida começam naturalmente
- Criatividade florescendo em novas formas
- Relacionamentos se transformam ou se depuram
- Sincronicidades aumentam significativamente
- O paciente "toma as rédeas" da própria cura

O QUE FAZER NO RUBEDO:
- Introduzir Alliastrum (minerais) para fortalecer virtudes
- Prescrever Corpus Celestes do arquétipo de missão
- Trabalhar V.I.T.R.I.O.L. (Vitriol) se ainda houver resistência ao propósito
- Reduzir florais de limpeza, aumentar florais de expansão
- O terapeuta se torna mais facilitador e menos condutor

SEQUÊNCIA TÍPICA DO TRATAMENTO:
Nigredo (28-56 dias) → Albedo (28-56 dias) → Rubedo (contínuo)

ERROS COMUNS:
- Parar o tratamento no Nigredo por achar que está piorando (é limpeza!)
- Introduzir Alliastrum antes do Nigredo se completar
- Não reconhecer que o paciente avançou para Albedo/Rubedo e manter protocolo de limpeza
"""
TAGS["Estágios Alquímicos — Nigredo, Albedo e Rubedo no Tratamento"] = ["transmutacao", "nigredo", "rubedo", "albedo", "protocolo", "fundamentos", "conceito_basico"]

# ===========================================================================
# SERPENTE DO PAI — DETALHADA
# ===========================================================================
DOCS["Serpente do Pai — Padrões Paternos e Lado Direito do Corpo"] = """
CONHECIMENTO ESTRUTURADO — SERPENTE DO PAI
Keywords: serpente do pai, serpente paterna, lado direito corpo, autoridade paterna, pai ausente, pai autoritário, dinheiro pai, herança paterna, linhagem masculina, bloqueio financeiro pai, pernas direitas, braço direito, padrão paterno

A Serpente do Pai é o conjunto de padrões energéticos, emocionais e comportamentais herdados da linhagem paterna.

LOCALIZAÇÃO NO CORPO:
A Serpente do Pai governa o LADO DIREITO do corpo.
Sintomas físicos no lado direito indicam padrões paternos ativos:
- Dor no ombro direito: peso da responsabilidade paterna
- Dor no joelho direito: submissão a autoridades masculinas
- Problemas no fígado (lado direito): raiva paterna reprimida
- Dor no braço direito: ação bloqueada pelo pai

TIPOS DE SERPENTE DO PAI COMPROMETIDA:

1. PAI AUSENTE:
O pai físico ou emocionalmente ausente cria:
- Dificuldade de enraizamento (chakra basal comprometido)
- Insegurança financeira crônica (não houve modelo de provedor)
- Dificuldade de agir no mundo (Fogo deficiente)
- Medo de autoridades e estruturas
- Nas filhas: dificuldade com homens, atração por homens ausentes

2. PAI AUTORITÁRIO/CONTROLADOR:
O pai excessivamente controlador cria:
- Paralisia do poder pessoal (plexo solar comprometido)
- Medo de se destacar
- Dificuldade de exercer autoridade própria
- Tendência a obedecer figuras de autoridade mesmo quando erradas
- Nas filhas: relacionamento com homens controladores

3. PAI FINANCEIRAMENTE BLOQUEADO:
O pai que não sabia cobrar, que tinha crenças limitantes sobre dinheiro:
- Crenças herdadas: "dinheiro é sujo", "ricos são maus", "não mereço"
- Bloqueios financeiros crônicos sem causa aparente
- Dificuldade de precificar o próprio trabalho
- Dificuldade de COBRAR por serviços prestados

4. PAI QUE NÃO SE AUTORIZOU:
O pai que tinha um sonho mas não viveu:
- Transmite ao filho/filha o sonho não vivido
- Filho sente pressão de realizar o sonho do pai
- OU filho repete o padrão de não se autorizar

ECLIPSE LUNAR (padrão específico):
Quando o pai foi autoritário ao ponto de SUPRIMIR a mãe — anular a voz e presença materna.
Resultado: filho cresceu sem referência equilibrada do feminino.
Manifesta como: dificuldade de integrar masculino e feminino, extremismo, falta de receptividade.
Tratamento: Eclipse Lunar específico no Kit Primus + trabalho com Serpente do Pai.

PERGUNTAS DIAGNÓSTICAS PARA SERPENTE DO PAI:
- "Como era seu pai?" (presente/ausente, autoritário/gentil, provedor/não provedor)
- "Qual era a relação do seu pai com dinheiro?"
- "Você repete algum padrão do seu pai que não quer repetir?"
- "Seu pai tinha um sonho que não viveu?"
- "Você tem dores ou problemas no lado direito do corpo?"

TRATAMENTO:
- Florais Passado Solar (chakra comprometido) — linhagem paterna
- Kit DNA: quando o padrão é multigeracional
- Corpus Celestes Áries: para restaurar coragem paterna saudável
- Corpus Celestes Capricórnio: para restaurar estrutura e disciplina paterna
"""
TAGS["Serpente do Pai — Padrões Paternos e Lado Direito do Corpo"] = ["matrix_padrao", "matrix_heranca", "floral", "protocolo", "fundamentos", "conceito_basico"]

# ===========================================================================
# SERPENTE DA MÃE — DETALHADA
# ===========================================================================
DOCS["Serpente da Mãe — Padrões Maternos e Lado Esquerdo do Corpo"] = """
CONHECIMENTO ESTRUTURADO — SERPENTE DA MÃE
Keywords: serpente da mãe, serpente materna, lado esquerdo corpo, mãe superprotetora, mãe ausente, mãe controladora, herança materna, linhagem feminina, padrão materno, carência afetiva, ombro esquerdo, joelho esquerdo

A Serpente da Mãe é o conjunto de padrões energéticos, emocionais e comportamentais herdados da linhagem materna.

LOCALIZAÇÃO NO CORPO:
A Serpente da Mãe governa o LADO ESQUERDO do corpo.
Sintomas físicos no lado esquerdo indicam padrões maternos ativos:
- Dor no ombro esquerdo: peso do cuidado materno
- Dor no joelho esquerdo: submissão emocional materna
- Problemas no coração (lado esquerdo): feridas de amor materno
- Dor no braço esquerdo: carência afetiva materna

TIPOS DE SERPENTE DA MÃE COMPROMETIDA:

1. MÃE AUSENTE (física ou emocionalmente):
- Carência afetiva profunda
- Dificuldade de receber amor
- Relacionamentos com pessoas emocionalmente indisponíveis
- Dependência afetiva excessiva
- Dificuldade de se nutrir (comer emocionalmente, ou não se nutrir)

2. MÃE SUPERPROTETORA:
- Infantilização → dificuldade de autonomia
- Medo de errar (mãe sempre salvava)
- Dificuldade de tomar decisões próprias
- Relacionamentos de dependência
- Nas mulheres: tendência a ser mãe superprotetora também (repetição)

3. MÃE QUE SOFREU DEMAIS:
- Filho absorve a dor materna como responsabilidade sua
- Culpa por sentir alegria ("minha mãe sofreu tanto, não mereço ser feliz")
- Depressão como herança materna
- Tendência ao sacrifício e autoanulação

4. MÃE QUE SUPRIMIU SEUS SONHOS:
- Filha herda o sonho materno não vivido
- OU repete o padrão de não viver os próprios sonhos

ECLIPSE SOLAR (padrão específico):
Quando a mãe foi tão dominante que SUPRIMIU a referência paterna na família.
Resultado: filho cresceu sem modelo paterno equilibrado.
Manifesta como: dificuldade de estabelecer estrutura, limites, autoridade própria.
Tratamento: Eclipse Solar específico + trabalho com Serpente da Mãe.

PERGUNTAS DIAGNÓSTICAS PARA SERPENTE DA MÃE:
- "Como era sua mãe?" (presente/ausente, protetora/negligente, alegre/sofrida)
- "Qual era a relação da sua mãe com amor e relacionamentos?"
- "Você sente que absorve a dor dos outros?"
- "Você repete algum padrão da sua mãe que não quer repetir?"
- "Você tem dores ou problemas no lado esquerdo do corpo?"

TRATAMENTO:
- Florais Passado Lunar (chakra comprometido) — linhagem materna
- Kit DNA: quando o padrão é multigeracional
- Kit Matrix: quando há trauma da linhagem feminina
- Corpus Celestes Câncer: para restaurar o nutridor saudável
- Corpus Celestes Escorpião: para transformar padrões maternos profundos
"""
TAGS["Serpente da Mãe — Padrões Maternos e Lado Esquerdo do Corpo"] = ["matrix_padrao", "matrix_heranca", "floral", "protocolo", "fundamentos", "conceito_basico"]

# ===========================================================================
# MAPEAMENTO SINTOMAS → CAUSAS
# ===========================================================================
DOCS["Mapeamento Sintomas para Causas Alquímicas — Diagnóstico Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — SINTOMAS E CAUSAS ALQUÍMICAS
Keywords: sintomas causas alquímicas, diagnóstico, infertilidade, bloqueio financeiro, depressão, ansiedade, dor nas pernas, insegurança, dor nas costas, câncer, tumor, pele alergia, relacionamento problema, crise financeira

GUIA DE MAPEAMENTO SINTOMA → CAUSA ALQUÍMICA → TRATAMENTO

DORES NAS PERNAS / INSEGURANÇA DE CAMINHAR:
Causa alquímica: Desequilíbrio Fogo + Terra (falta de ação e base segura)
Raiz ancestral: Serpente do Pai — pai ausente criando insegurança na jornada, ou pai autoritário paralisando o movimento
Chakras afetados: Basal (1º) — raiz do movimento e segurança
Perguntas diagnósticas: "Seu pai estava presente para te apoiar nos primeiros passos da vida?" "Você sente segurança de avançar?"
Tratamento: Passado Solar Basal + Kit DNA (segurança) + Corpus Celestes Áries (coragem de caminhar)

BLOQUEIOS FINANCEIROS CRÔNICOS:
Causa alquímica: Deficiência de Terra (sustentação material) + deficiência de Fogo (coragem de cobrar/agir)
Raiz ancestral: Serpente do Pai — pai que não sabia cobrar, crenças limitantes de merecimento, pai ausente como modelo de provedor
Chakras afetados: Basal (enraizamento) + Plexo Solar (poder de ação)
Perguntas diagnósticas: "Qual era a relação do seu pai com dinheiro?" "Você tem dificuldade de cobrar pelo seu trabalho?"
Tratamento: Passado Solar Basal + Passado Solar Plexo Solar + Vitriol (desobediência espiritual ao merecimento) + Kit DNA

INFERTILIDADE IDIOPÁTICA:
Causa alquímica: Matrix danificada — portal criativo feminino bloqueado
Raiz ancestral: Traumas intrauterinos (9 meses gestação) + linhagem feminina comprometida
Chakras afetados: Matrix (8º chakra) + Umbilical + Basal
Perguntas diagnósticas: "Como foi a gravidez da sua mãe com você?" "O que você sempre quis criar mas nunca criou?"
Tratamento: Kit Matrix (Materlux) + Kit Traumas Intrauterinos + Serpente da Mãe
Nota: frequentemente a criatividade bloqueada se manifesta como infertilidade — liberá-la pode resolver ambos

DEPRESSÃO:
Causa alquímica: Deficiência de Fogo (ausência de alegria e motivação) OU excesso de Água (choro e tristeza em loop)
Raiz ancestral: Serpente da Mãe — repetição da tristeza materna, criança ferida afetivamente
Chakras afetados: Plexo Solar (Fogo) + Cardíaco (amor)
Perguntas diagnósticas: "Sua mãe ou avó tinha tendência à tristeza/depressão?" "O que a sua raiva faz quando não é expressa?"
Tratamento: Equilíbrio dos 4 Elementos (especialmente Fogo) + Serpente da Mãe + Passado Lunar Cardíaco

ANSIEDADE:
Causa alquímica: Excesso de Ar (mente acelerada) OU excesso de Fogo (hiperatividade reativa) + desconexão da missão espiritual
Raiz ancestral: Tanto Serpente do Pai (hipervigilância por pai imprevisível) quanto Serpente da Mãe (ansiedade aprendida)
Chakras afetados: Umbilical (emoções) + Plexo Solar (pensamentos) + Laríngeo (expressão reprimida)
Perguntas diagnósticas: "Você expressa o que pensa ou engole?" "Quem na sua família tinha ansiedade?"
Tratamento: Presente Solar/Lunar Umbilical + Bálsamo Umbilical + Kit DNA + Rescue Umbilical (crises agudas)

DOR NAS COSTAS / PROBLEMAS ESTRUTURAIS:
Causa alquímica: Deficiência de Terra — pessoa carregando peso ancestral que não é seu
Raiz ancestral: DNA comprometido — herança de traumas de gerações anteriores "pesando" nas costas
Chakras afetados: Basal (estrutura) + comprometimento ancestral geral
Perguntas diagnósticas: "Você sente que carrega o peso da família nas costas?" "Problemas na coluna têm histórico familiar?"
Tratamento: Passado Solar/Lunar Basal + Kit DNA + Alliastrum Ferro (para suportar o peso com força)

PROBLEMAS DE PELE / ALERGIAS:
Causa alquímica: Fogo em excesso (inflamação) OU Ar em excesso (hipersensibilidade) + rejeição intrauterina
Raiz ancestral: Traumas intrauterinos (bebê não foi desejado ou houve rejeição emocional durante gestação)
Chakras afetados: Basal (pertencimento) + Matrix (traumas intrauterinos)
Perguntas diagnósticas: "Você sabe se foi um bebê desejado?" "Como foi a gravidez da sua mãe?"
Tratamento: Kit Traumas Intrauterinos + Presente Solar/Lunar Basal + equilíbrio do Fogo

CÂNCER / TUMORES:
Causa alquímica: Frustração acumulada por não ser o próprio eu + raiva reprimida de não viver a missão
Raiz: Desobediência civil ao espírito — viver a vida dos outros (pai, mãe, cônjuge) ao invés da própria
Chakras afetados: dependem da localização do tumor (localização física indica chakra comprometido)
Perguntas diagnósticas: "O que você sempre quis fazer mas nunca fez?" "Você está vivendo a vida que sempre quis ou a que te mandaram viver?"
Tratamento: Vitriol (descarbonização espiritual) + Kit DNA + Corpus Celestes do arquétipo de missão + acompanhamento de consciência

PROBLEMAS DE RELACIONAMENTO (PADRÕES REPETITIVOS):
Causa alquímica: Torus desequilibrado (atrai frequência errada) + Serpente correspondente ao padrão
Raiz: Padrão herdado do pai ou mãe em relacionamentos
Chakras afetados: Cardíaco + Umbilical
Perguntas diagnósticas: "Você sempre se relaciona com o mesmo tipo de pessoa?" "Seus pais tinham um relacionamento saudável?"
Tratamento: Kit Torus + Serpente do Pai/Mãe conforme o padrão + Passado Solar/Lunar Cardíaco
"""
TAGS["Mapeamento Sintomas para Causas Alquímicas — Diagnóstico Joel Aleixo"] = ["protocolo", "fundamentos", "conceito_basico", "matrix_trauma", "matrix_padrao", "floral"]

# ===========================================================================
# ANAMNESE ALQUÍMICA
# ===========================================================================
DOCS["Anamnese Alquímica — As 5 Perguntas Centrais do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — ANAMNESE ALQUÍMICA
Keywords: anamnese alquímica, perguntas diagnósticas, como diagnosticar, perguntas joel aleixo, investigação clínica, workflow diagnóstico, o que perguntar paciente, primeira sessão, consulta alquímica

A Anamnese Alquímica é o processo de investigação clínica do método Joel Aleixo.
Não é um diagnóstico médico — é uma investigação espiritual e ancestral.
O objetivo é mapear: qual padrão está ativo? De onde vem? Em qual setenio foi instalado?

AS 5 PERGUNTAS CENTRAIS DO JOEL ALEIXO:

PERGUNTA 1: "O que a senhora veio fazer aqui no meu consultório?"
Objetivo: Identificar a queixa apresentada — que frequentemente mascara a causa real.
O que escutar: A primeira coisa que o paciente diz revela onde mais dói.
Atenção: A queixa declarada raramente é o problema real — é a porta de entrada.

PERGUNTA 2: "Como foi esse seu ano?" (ou "Como foi quando isso começou?")
Objetivo: Mapear o contexto temporal. Conectar o início do sintoma a um evento de vida.
O que fazer com a resposta: identificar em qual setenio estava o paciente quando o sintoma apareceu.
Exemplo: "Fiquei doente aos 28" → Setenio Saturn Return → crise de identidade vs. comandos familiares.

PERGUNTA 3: "O que você fez com sua raiva?"
Objetivo: Identificar emoções reprimidas, especialmente a raiva não expressa.
Padrões revelados:
- Se a raiva nunca é expressa → pode virar câncer, doenças autoimunes
- Se é expressa explosivamente → Fogo em excesso, Serpente do Pai ativa com raiva paterna
- Se o paciente diz "nunca fico com raiva" → grande sinal de repressão

PERGUNTA 4: "Qual é o maior sonho da sua vida?"
Objetivo: Identificar a missão espiritual e o grau de alinhamento ou desvio.
O que escutar: A lacuna entre o sonho e a vida atual.
Padrão de deobediência civil: "Eu queria ser artista mas fui médico por minha mãe" → Vitriol + limpeza de comandos.
Padrão de missão bloqueada: quando o sonho está claro mas há medo extremo → Corpus Celestes do arquétipo do sonho.

PERGUNTA 5: "Seu pai ou sua mãe tinha esse mesmo padrão?"
Objetivo: Confirmar qual Serpente está ativa — paterna ou materna.
Mapeamento:
- Padrão vem do pai → Serpente do Pai, Passado Solar (chakra correspondente)
- Padrão vem da mãe → Serpente da Mãe, Passado Lunar (chakra correspondente)
- Vem dos dois → DNA Alquímico multigeracional, Kit DNA

WORKFLOW DIAGNÓSTICO COMPLETO:

Após as 5 perguntas, o terapeuta deve:

1. MAPEAR O SETENIO:
Quando o padrão começou? Qual setenio corresponde àquela idade?
0-7: Basal (segurança, sobrevivência) | 7-14: Umbilical (emoções, família)
14-21: Plexo Solar (identidade) | 21-28: Cardíaco (amor) | 28-35: Laríngeo (expressão)
35-42: Frontal (visão) | 42-49: Coronário (propósito)

2. IDENTIFICAR A SERPENTE:
Lado direito do corpo ou herança paterna → Serpente do Pai
Lado esquerdo do corpo ou herança materna → Serpente da Mãe

3. CRUZAR COM O MAPA NATAL:
Qual planeta/casa está comprometido? Qual elemento domina em excesso ou está carente?
Qual arquétipo está bloqueado? (Corpus Celestes correspondente)

4. IDENTIFICAR O ELEMENTO DESEQUILIBRADO:
Fogo (ação/coragem) | Terra (estrutura/segurança) | Água (emoção/fluxo) | Ar (comunicação/mente)

5. PRESCREVER FLORAIS:
Passado Solar/Lunar do chakra do setenio comprometido
+ Kit DNA se padrão multigeracional
+ Corpus Celestes do arquétipo a desenvolver
+ Rescue se há crise aguda
+ Vitriol se há desobediência espiritual crônica

PRINCÍPIO CENTRAL:
"O que não se cura, se repete."
A anamnese identifica o que não foi curado — a raiz do padrão repetitivo.
"""
TAGS["Anamnese Alquímica — As 5 Perguntas Centrais do Método Joel Aleixo"] = ["protocolo", "fundamentos", "conceito_basico", "matrix_padrao"]

# ===========================================================================
# MIASMAS
# ===========================================================================
DOCS["Miasmas — Toxinas Herdadas e Padrões Ancestrais do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — MIASMAS
Keywords: miasmas, toxinas herdadas, padrões ancestrais, herança familiar, doença ancestral, o que não se cura se repete, padrões repetitivos, herança energética, karma familiar, 5 gerações

Os Miasmas são padrões informativos tóxicos herdados de gerações anteriores que se depositam no campo energético e físico.

DEFINIÇÃO:
Diferente de doenças genéticas (DNA estrutural fixo), os Miasmas são:
- Informações energéticas, não genes físicos
- Podem ser liberados e transformados (ao contrário do DNA físico)
- Transmitidos pelas Serpentes (linhagem paterna e materna)
- Armazenados como "carvões" comprimidos na estrutura óssea

ORIGEM DOS MIASMAS:
Podem vir de até 5 gerações para trás.
Um bisavô que sofreu uma guerra → transmite padrão de sobrevivência apavorada para os filhos → netos → bisnetos.
Uma avó que foi abusada → transmite padrão de relações violentas como "normal".
Cada geração que não cura o padrão, intensifica-o para a próxima.

"O QUE NÃO SE CURA, SE REPETE"
Este é o princípio central dos miasmas.
Se o padrão não é tratado conscientemente numa geração, ele se repete na seguinte.
Muitas vezes com intensidade maior (como uma dívida com juros).

MANIFESTAÇÕES DE MIASMAS ATIVOS:
- Doenças crônicas que não respondem a tratamentos convencionais
- Padrões de vida repetitivos: sempre o mesmo tipo de parceiro, trabalho, crise
- "Azar" sistêmico — situações negativas que se repetem sem causa lógica
- Doenças que aparecem na mesma idade em que um ancestral adoeceu
- Comportamentos que a pessoa não quer ter mas não consegue parar

EXEMPLOS DE MIASMAS CLÍNICOS:
1. Padrão de abandono: bisavó abandonada pelo marido → avó abandonada → mãe abandonada → paciente sempre abandona ou é abandonada
2. Padrão de violência: avô violento → pai que repetiu ou jurou nunca repetir (mas repete de forma "leve")
3. Padrão financeiro: família inteira que nunca conseguiu prosperar, cada geração recomeçando do zero
4. Padrão de doença: câncer que aparece na mesma parte do corpo, na mesma faixa etária, em diferentes gerações
5. Padrão de dependência: alcoolismo, dependência afetiva ou química que atravessa gerações

DIAGNÓSTICO DE MIASMAS:
Perguntas-chave:
- "Seu pai/mãe/avó tinha esse mesmo padrão?"
- "Em que idade seu pai ficou doente? Em que parte do corpo?"
- "Alguém na sua família morreu jovem de forma parecida?"
- "Qual é o padrão que sua família sempre repetiu?"

Sinais de miasma ativo vs. trauma pessoal:
- Se o padrão começou na infância ANTES de qualquer trauma pessoal → miasma
- Se múltiplas gerações têm o mesmo padrão → miasma multigeracional
- Se o padrão "persiste" mesmo após trabalho terapêutico intenso → miasma ainda não liberado

TRATAMENTO DE MIASMAS:
1. Consciência: nomear o padrão e reconhecer que ele não é do paciente — é da linhagem
2. Kit DNA: principal ferramenta para limpeza de padrões multigeracionais
3. Florais Passado Solar/Lunar dos chakras comprometidos: limpar cada camada ancestral
4. Serpente do Pai e/ou Serpente da Mãe: conforme a linhagem de origem
5. Tempo: miasmas de múltiplas gerações precisam de protocolos de 3-6 meses

PRINCÍPIO TERAPÊUTICO CENTRAL:
Quando o paciente libera um miasma, não apenas ele cura — mas toda a linhagem que carregou aquele padrão é liberada também.
"Você não está se curando apenas por você — está curando seus ancestrais e seus descendentes."
"""
TAGS["Miasmas — Toxinas Herdadas e Padrões Ancestrais do Método Joel Aleixo"] = ["miasma", "matrix_heranca", "matrix_padrao", "dna", "dna_leitura", "fundamentos", "conceito_basico"]

# ===========================================================================
# MAIN
# ===========================================================================
async def main():
    settings = get_settings()
    print(f"\nConectado: {settings.SUPABASE_URL[:40]}...")
    print(f"Terapeuta ID: {TERAPEUTA_ID}")
    print(f"Documentos a indexar: {len(DOCS)}\n")

    for titulo, conteudo in DOCS.items():
        tags = TAGS.get(titulo, ["fundamentos"])
        await indexar(titulo, conteudo, tags)

    print(f"\n{'='*60}")
    print(f"FASE 2 CONCLUÍDA! {len(DOCS)} documentos indexados.")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
