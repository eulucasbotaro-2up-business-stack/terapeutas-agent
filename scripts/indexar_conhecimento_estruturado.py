"""
Script para indexar documentos de conhecimento estruturado no RAG.

Uso:
    python scripts/indexar_conhecimento_estruturado.py

Cria um documento 'knowledge' no Supabase e indexa o conteúdo com embeddings.
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Adiciona o root do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings
from src.core.supabase_client import get_supabase
from src.rag.processor import dividir_em_chunks, gerar_embeddings, salvar_chunks_no_supabase

# Terapeuta Joel Aleixo
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"


def criar_documento_no_banco(titulo: str, descricao: str = "") -> str:
    """Cria registro na tabela documentos e retorna o ID."""
    supabase = get_supabase()
    doc_id = str(uuid.uuid4())

    supabase.table("documentos").insert({
        "id": doc_id,
        "terapeuta_id": TERAPEUTA_ID,
        "nome_arquivo": titulo,
        "tipo": "pdf",
        "tamanho_bytes": len(descricao),
        "storage_path": f"knowledge/{doc_id}.txt",
        "total_chunks": 0,
        "processado": True,
    }).execute()

    print(f"  [+] Documento criado: {doc_id} — {titulo}")
    return doc_id


def remover_chunks_antigos_por_titulo(titulo: str) -> None:
    """Remove chunks de um documento pelo nome para reindexar."""
    supabase = get_supabase()

    # Busca documentos com esse nome
    resultado = supabase.table("documentos").select("id").eq("terapeuta_id", TERAPEUTA_ID).eq("nome_arquivo", titulo).execute()

    for doc in resultado.data:
        doc_id = doc["id"]
        supabase.table("embeddings").delete().eq("documento_id", doc_id).execute()
        supabase.table("documentos").delete().eq("id", doc_id).execute()
        print(f"  [-] Removido documento antigo: {doc_id}")


async def indexar_documento(titulo: str, conteudo: str, descricao: str = "") -> None:
    """Indexa um documento de conhecimento estruturado."""
    print(f"\n{'='*60}")
    print(f"Indexando: {titulo}")
    print(f"{'='*60}")

    # Remove versão anterior se existir
    remover_chunks_antigos_por_titulo(titulo)

    # Cria novo documento
    doc_id = criar_documento_no_banco(titulo, descricao)

    # Divide em chunks
    chunks = dividir_em_chunks(conteudo)
    print(f"  [+] {len(chunks)} chunks gerados")

    # Gera embeddings
    print(f"  [~] Gerando embeddings...")
    embeddings = await gerar_embeddings(chunks)
    print(f"  [+] {len(embeddings)} embeddings gerados")

    # Salva no Supabase
    total = await salvar_chunks_no_supabase(chunks, embeddings, TERAPEUTA_ID, doc_id)
    print(f"  [+] {total} chunks salvos no Supabase")


# ===========================================================================
# DOCUMENTOS DE CONHECIMENTO ESTRUTURADO
# ===========================================================================

DOCS = {}

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA BASAL (1º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Basal (Muladhara)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA BASAL
Keywords: kit primus, chakra basal, muladhara, primeiro chakra, 1º chakra, base, raiz, florais basal, flores basal

O Chakra Basal (Muladhara) é o 1º chakra, localizado na base da coluna vertebral.
Governa: instinto de sobrevivência, enraizamento, segurança, estrutura física, materialidade, ancestralidade.
Elemento: Terra
Substâncias alquímicas: Sal Sulfúrico Basal + Sulphur Mercurial Basal
Biorritmo: 24 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA BASAL:

1. PASSADO SOLAR BASAL
Nome: Passado Solar Basal
Chakra: Basal (1º)
Polaridade: Passado Solar
Tema: Traumas ancestrais paternos, feridas da linhagem paterna do passado.
Indicação: Quando há padrões herdados do pai e ancestrais masculinos que se repetem; bloqueios de enraizamento vindos da linhagem paterna.
Balanceamento: Ativa o enraizamento masculino, dissolve padrões ancestrais paternos.

2. PASSADO LUNAR BASAL
Nome: Passado Lunar Basal
Chakra: Basal (1º)
Polaridade: Passado Lunar
Tema: Traumas ancestrais maternos, feridas da linhagem materna do passado.
Indicação: Quando há padrões herdados da mãe e ancestrais femininos; dificuldade de enraizamento pela linhagem materna.
Balanceamento: Ativa o enraizamento feminino, dissolve padrões ancestrais maternos.

3. PRESENTE SOLAR BASAL
Nome: Presente Solar Basal
Chakra: Basal (1º)
Polaridade: Presente Solar
Tema: Desafios atuais de enraizamento e segurança na vida presente — perspectiva masculina/ativa.
Indicação: Insegurança financeira atual, falta de estrutura, dificuldade de sustentar projetos.
Balanceamento: Traz estabilidade, presença, força de manifestação no aqui-agora.

4. PRESENTE LUNAR BASAL
Nome: Presente Lunar Basal
Chakra: Basal (1º)
Polaridade: Presente Lunar
Tema: Desafios atuais de enraizamento — perspectiva feminina/receptiva.
Indicação: Insegurança emocional presente, falta de pertencimento, dificuldade de receber.
Balanceamento: Traz receptividade, acolhimento, segurança emocional no presente.

5. FUTURO SOLAR BASAL
Nome: Futuro Solar Basal
Chakra: Basal (1º)
Polaridade: Futuro Solar
Tema: Projeção de medo e insegurança no futuro — perspectiva ativa/expansiva.
Indicação: Medo de não conseguir sustentar o futuro, ansiedade sobre prosperidade.
Balanceamento: Abre confiança no futuro, expansão segura.

6. FUTURO LUNAR BASAL
Nome: Futuro Lunar Basal
Chakra: Basal (1º)
Polaridade: Futuro Lunar
Tema: Projeção de medo no futuro — perspectiva receptiva/intuitiva.
Indicação: Medo do futuro desconhecido, resistência à mudança, apego ao que já foi.
Balanceamento: Abertura suave para novos ciclos, confiança no processo.

7. INTEGRATIVO BASAL
Nome: Integrativo Basal
Chakra: Basal (1º)
Polaridade: Integrativo
Tema: Integração de todas as polaridades do chakra basal.
Indicação: Quando é necessário harmonizar todas as dimensões do chakra basal simultaneamente.
Balanceamento: Integração completa do enraizamento em todas as dimensões.

COMPOSTOS DO CHAKRA BASAL:
- Bálsamo Basal: fórmula composta com os 7 florais do chakra basal
- Rescue Basal (Resgate Basal): fórmula de emergência para crises do chakra basal

FÓRMULAS COM RESCUE BASAL:
O Rescue Basal pode ser usado em momentos de crise de enraizamento aguda, perda de chão, desamparo extremo.
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA UMBILICAL (2º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Umbilical (Svadhisthana)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA UMBILICAL
Keywords: kit primus, chakra umbilical, svadhisthana, segundo chakra, 2º chakra, umbigo, sacro, florais umbilical, flores umbilical, emoções, ansiedade

O Chakra Umbilical (Svadhisthana) é o 2º chakra, localizado abaixo do umbigo.
Governa: emoções, prazer, criatividade, relações interpessoais, fluxo da vida, sexualidade.
Elemento: Água
Substâncias alquímicas: Sulphur Mercurial Umbilical + Sal Sulfúrico Umbilical
Biorritmo: 12 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA UMBILICAL:

1. PASSADO SOLAR UMBILICAL
Nome: Passado Solar Umbilical
Chakra: Umbilical (2º)
Polaridade: Passado Solar
Tema: Feridas emocionais do passado — perspectiva paterna/masculina/ativa.
Indicação: Emoções não resolvidas com a figura paterna; padrões emocionais herdados do pai que ainda afetam o presente.
Balanceamento: Libera bloqueios emocionais masculinos do passado, fluidez emocional paterna.

2. PASSADO LUNAR UMBILICAL
Nome: Passado Lunar Umbilical
Chakra: Umbilical (2º)
Polaridade: Passado Lunar
Tema: Feridas emocionais do passado — perspectiva materna/feminina/receptiva.
Indicação: Emoções não resolvidas com a figura materna; padrões emocionais herdados da mãe; dependência emocional materna.
Balanceamento: Libera bloqueios emocionais femininos do passado, cura o vínculo materno.

3. PRESENTE SOLAR UMBILICAL
Nome: Presente Solar Umbilical
Chakra: Umbilical (2º)
Polaridade: Presente Solar
Tema: Desequilíbrios emocionais atuais — perspectiva ativa/expressiva.
Indicação: Ansiedade emocional presente, dificuldade de expressar emoções, reatividade emocional no cotidiano.
Balanceamento: Traz equilíbrio emocional presente, clareza nos relacionamentos.

4. PRESENTE LUNAR UMBILICAL
Nome: Presente Lunar Umbilical
Chakra: Umbilical (2º)
Polaridade: Presente Lunar
Tema: Desequilíbrios emocionais atuais — perspectiva receptiva/intuitiva.
Indicação: Hipersensibilidade emocional, absorção de emoções alheias, dificuldade de receber amor.
Balanceamento: Traz escudamento emocional saudável, receptividade equilibrada.

5. FUTURO SOLAR UMBILICAL
Nome: Futuro Solar Umbilical
Chakra: Umbilical (2º)
Polaridade: Futuro Solar
Tema: Projeções emocionais no futuro — perspectiva ativa.
Indicação: Ansiedade sobre relações futuras, medo de se emocionar no futuro.
Balanceamento: Confiança emocional no futuro, abertura para novas experiências.

6. FUTURO LUNAR UMBILICAL
Nome: Futuro Lunar Umbilical
Chakra: Umbilical (2º)
Polaridade: Futuro Lunar
Tema: Projeções emocionais no futuro — perspectiva receptiva.
Indicação: Medo de se abrir emocionalmente no futuro, fechamento afetivo preventivo.
Balanceamento: Suavidade na abertura emocional futura, receptividade para o novo.

7. INTEGRATIVO UMBILICAL
Nome: Integrativo Umbilical
Chakra: Umbilical (2º)
Polaridade: Integrativo
Tema: Integração de todas as polaridades emocionais do chakra umbilical.
Indicação: Quando é necessário trabalhar o chakra umbilical de forma completa e integrada.
Balanceamento: Harmonia emocional plena, fluxo completo do centro umbilical.

COMPOSTOS DO CHAKRA UMBILICAL:
- Bálsamo Umbilical: fórmula composta com os 7 florais do chakra umbilical
- Rescue Umbilical (Resgate Umbilical): fórmula de emergência para crises emocionais do chakra umbilical

FÓRMULAS COM RESCUE UMBILICAL:
O Rescue Umbilical é indicado para crises emocionais agudas, choros sem motivo aparente, colapso emocional, hipersensibilidade extrema, ansiedade emocional intensa.
Pode ser combinado com Bálsamo Umbilical para suporte prolongado.
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA PLEXO SOLAR (3º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Plexo Solar (Manipura)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA PLEXO SOLAR
Keywords: kit primus, chakra plexo solar, manipura, terceiro chakra, 3º chakra, plexo, solar, florais plexo solar, poder pessoal, vontade, autoestima

O Chakra Plexo Solar (Manipura) é o 3º chakra, localizado no plexo solar (entre o umbigo e o esterno).
Governa: poder pessoal, vontade, autoestima, identidade, assertividade, digestão emocional.
Elemento: Fogo
Substâncias alquímicas: Sulphur Mercurial do Plexo + Sal Sulfúrico do Plexo
Biorritmo: 8 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA PLEXO SOLAR:

1. PASSADO SOLAR PLEXO SOLAR
Nome: Passado Solar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Passado Solar
Tema: Feridas de poder e vontade do passado — linhagem paterna.
Indicação: Questões de poder com o pai, padrões de submissão ou dominância herdados.
Balanceamento: Restaura o poder pessoal masculino, desfaz padrões de submissão paternos.

2. PASSADO LUNAR PLEXO SOLAR
Nome: Passado Lunar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Passado Lunar
Tema: Feridas de poder e vontade do passado — linhagem materna.
Indicação: Questões de poder com a mãe, dependência de aprovação materna.
Balanceamento: Restaura o poder pessoal feminino, independência da aprovação materna.

3. PRESENTE SOLAR PLEXO SOLAR
Nome: Presente Solar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Presente Solar
Tema: Desequilíbrios de poder pessoal no presente — perspectiva ativa.
Indicação: Dificuldade de assertividade atual, procrastinação, falta de iniciativa.
Balanceamento: Ativa vontade e iniciativa no presente.

4. PRESENTE LUNAR PLEXO SOLAR
Nome: Presente Lunar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Presente Lunar
Tema: Desequilíbrios de poder no presente — perspectiva receptiva.
Indicação: Baixa autoestima presente, necessidade excessiva de validação.
Balanceamento: Restaura autoestima e reconhecimento interno.

5. FUTURO SOLAR PLEXO SOLAR
Nome: Futuro Solar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Futuro Solar
Tema: Projeções de poder e conquista no futuro.
Indicação: Medo de falhar, bloqueio para agir em direção às metas.
Balanceamento: Confiança na própria capacidade de realização futura.

6. FUTURO LUNAR PLEXO SOLAR
Nome: Futuro Lunar Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Futuro Lunar
Tema: Projeções de poder no futuro — perspectiva receptiva.
Indicação: Medo de sucesso, autossabotagem preventiva.
Balanceamento: Abertura suave para o próprio poder e reconhecimento futuro.

7. INTEGRATIVO PLEXO SOLAR
Nome: Integrativo Plexo Solar
Chakra: Plexo Solar (3º)
Polaridade: Integrativo
Tema: Integração completa do poder pessoal.
Indicação: Integração de todas as dimensões do poder pessoal e autoestima.
Balanceamento: Harmonia plena do centro de poder pessoal.

COMPOSTOS DO CHAKRA PLEXO SOLAR:
- Bálsamo Plexo Solar: fórmula composta com os 7 florais do chakra plexo solar
- Rescue Plexo Solar (Resgate Plexo Solar): fórmula de emergência para crises de poder pessoal

FÓRMULAS COM RESCUE PLEXO SOLAR:
Indicado para: crises de autoestima aguda, colapso de identidade, ataques de pânico relacionados ao poder pessoal.
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA CARDÍACO (4º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Cardíaco (Anahata)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA CARDÍACO
Keywords: kit primus, chakra cardíaco, anahata, quarto chakra, 4º chakra, coração, florais cardíaco, amor, compaixão, perdão

O Chakra Cardíaco (Anahata) é o 4º chakra, localizado no centro do peito.
Governa: amor incondicional, compaixão, perdão, equilíbrio entre o material e o espiritual, relacionamentos.
Elemento: Ar
Substâncias alquímicas: Sulphur Mercurial Cardíaco + Sal Sulfúrico Cardíaco
Biorritmo: 6 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA CARDÍACO:

1. PASSADO SOLAR CARDÍACO
Nome: Passado Solar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Passado Solar
Tema: Feridas do coração do passado — linhagem paterna.
Indicação: Mágoas com o pai, dificuldade de receber amor paterno, coração fechado por feridas do pai.
Balanceamento: Cura o coração masculino do passado, abre para receber e dar amor através da linhagem paterna.

2. PASSADO LUNAR CARDÍACO
Nome: Passado Lunar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Passado Lunar
Tema: Feridas do coração do passado — linhagem materna.
Indicação: Mágoas com a mãe, coração fechado por feridas maternas, dificuldade de amor incondicional.
Balanceamento: Cura o coração feminino do passado, dissolve mágoas maternas.

3. PRESENTE SOLAR CARDÍACO
Nome: Presente Solar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Presente Solar
Tema: Desequilíbrios do amor no presente — perspectiva ativa.
Indicação: Dificuldade de expressar amor atualmente, coração guardado, falta de compaixão ativa.
Balanceamento: Abre o coração para expressar amor e compaixão no presente.

4. PRESENTE LUNAR CARDÍACO
Nome: Presente Lunar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Presente Lunar
Tema: Desequilíbrios do amor no presente — perspectiva receptiva.
Indicação: Dificuldade de receber amor, hipersensibilidade afetiva, coração que absorve tudo.
Balanceamento: Equilíbrio na receptividade afetiva, coração que recebe sem se dissolver.

5. FUTURO SOLAR CARDÍACO
Nome: Futuro Solar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Futuro Solar
Tema: Projeções afetivas no futuro — perspectiva ativa.
Indicação: Medo de amar no futuro, fechamento preventivo do coração.
Balanceamento: Confiança em amar novamente, abertura para novos vínculos.

6. FUTURO LUNAR CARDÍACO
Nome: Futuro Lunar Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Futuro Lunar
Tema: Projeções afetivas no futuro — perspectiva receptiva.
Indicação: Medo de ser ferido no futuro, resistência em se abrir afetivamente.
Balanceamento: Receptividade suave para o amor futuro, confiança nos vínculos.

7. INTEGRATIVO CARDÍACO
Nome: Integrativo Cardíaco
Chakra: Cardíaco (4º)
Polaridade: Integrativo
Tema: Integração completa do amor em todas as dimensões.
Indicação: Quando o coração precisa de uma cura integrada de todas as polaridades.
Balanceamento: Amor pleno, compaixão integrada, perdão total.

COMPOSTOS DO CHAKRA CARDÍACO:
- Bálsamo Cardíaco: fórmula composta com os 7 florais do chakra cardíaco
- Rescue Cardíaco (Resgate Cardíaco): fórmula de emergência para crises do coração

FÓRMULAS COM RESCUE CARDÍACO:
Indicado para: rupturas afetivas agudas, luto, coração partido, crises de compaixão excessiva (síndrome do cuidador).
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA LARÍNGEO (5º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Laríngeo (Vishuddha)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA LARÍNGEO
Keywords: kit primus, chakra laríngeo, vishuddha, quinto chakra, 5º chakra, garganta, expressão, voz, comunicação, florais laríngeo

O Chakra Laríngeo (Vishuddha) é o 5º chakra, localizado na garganta.
Governa: comunicação, expressão autêntica, criatividade verbal, verdade, escuta.
Elemento: Éter/Espaço
Substâncias alquímicas: Sulphur Mercurial Laríngeo + Sal Sulfúrico Laríngeo
Biorritmo: 4-5 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA LARÍNGEO:

1. PASSADO SOLAR LARÍNGEO
Nome: Passado Solar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Passado Solar
Tema: Silenciamentos e censuras do passado — linhagem paterna.
Indicação: "Sua voz foi silenciada pelo pai"; padrões de não poder se expressar herdados da linhagem paterna.
Balanceamento: Libera a voz masculina do passado, restaura o direito à expressão.

2. PASSADO LUNAR LARÍNGEO
Nome: Passado Lunar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Passado Lunar
Tema: Silenciamentos do passado — linhagem materna.
Indicação: Voz silenciada pela mãe ou ancestrais femininos; padrões de suavizar a verdade.
Balanceamento: Libera a voz feminina do passado, autenticidade na expressão.

3. PRESENTE SOLAR LARÍNGEO
Nome: Presente Solar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Presente Solar
Tema: Dificuldades de expressão no presente — perspectiva ativa.
Indicação: Dificuldade de falar a verdade atualmente, gagueira, medo de se posicionar.
Balanceamento: Clareza e coragem na expressão presente.

4. PRESENTE LUNAR LARÍNGEO
Nome: Presente Lunar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Presente Lunar
Tema: Dificuldades de expressão no presente — perspectiva receptiva/escuta.
Indicação: Dificuldade de escutar o outro, falar sem ouvir, ou escutar demais sem se expressar.
Balanceamento: Equilíbrio entre expressão e escuta.

5. FUTURO SOLAR LARÍNGEO
Nome: Futuro Solar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Futuro Solar
Tema: Projeções de expressão no futuro.
Indicação: Medo de se expor publicamente no futuro, bloqueio criativo-verbal sobre projetos futuros.
Balanceamento: Confiança na própria voz para o futuro.

6. FUTURO LUNAR LARÍNGEO
Nome: Futuro Lunar Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Futuro Lunar
Tema: Projeções de expressão no futuro — perspectiva receptiva.
Indicação: Medo de ser incompreendido no futuro, silenciamento preventivo.
Balanceamento: Abertura para ser ouvido e compreendido no futuro.

7. INTEGRATIVO LARÍNGEO
Nome: Integrativo Laríngeo
Chakra: Laríngeo (5º)
Polaridade: Integrativo
Tema: Integração completa da expressão autêntica.
Indicação: Integração de voz, escuta e verdade em todas as dimensões.
Balanceamento: Expressão plena, verdade integrada.

COMPOSTOS DO CHAKRA LARÍNGEO:
- Bálsamo Laríngeo: fórmula composta com os 7 florais do chakra laríngeo
- Rescue Laríngeo (Resgate Laríngeo): fórmula de emergência para bloqueios de expressão agudos
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA FRONTAL (6º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Frontal (Ajna)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA FRONTAL
Keywords: kit primus, chakra frontal, ajna, sexto chakra, 6º chakra, terceiro olho, intuição, visão, clareza mental, florais frontal

O Chakra Frontal (Ajna) é o 6º chakra, localizado entre as sobrancelhas (terceiro olho).
Governa: intuição, visão interior, clareza mental, discernimento, percepção extrassensorial.
Elemento: Luz/Éter sutil
Substâncias alquímicas: Sulphur Mercurial Frontal + Sal Sulfúrico Frontal
Biorritmo: 3 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA FRONTAL:

1. PASSADO SOLAR FRONTAL
Nome: Passado Solar Frontal
Chakra: Frontal (6º)
Polaridade: Passado Solar
Tema: Bloqueios de visão e percepção do passado — linhagem paterna.
Indicação: Crenças limitantes sobre a realidade herdadas do pai; "olhos fechados" para certas verdades por padrão paterno.
Balanceamento: Abre a visão masculina do passado, claridade perceptiva.

2. PASSADO LUNAR FRONTAL
Nome: Passado Lunar Frontal
Chakra: Frontal (6º)
Polaridade: Passado Lunar
Tema: Bloqueios de intuição do passado — linhagem materna.
Indicação: Intuição bloqueada por padrões maternos; medos de "ver demais".
Balanceamento: Abre a visão intuitiva feminina do passado.

3. PRESENTE SOLAR FRONTAL
Nome: Presente Solar Frontal
Chakra: Frontal (6º)
Polaridade: Presente Solar
Tema: Desequilíbrios de clareza mental no presente — perspectiva ativa.
Indicação: Confusão mental atual, dificuldade de discernimento, pensamentos dispersos.
Balanceamento: Clareza e foco mental no presente.

4. PRESENTE LUNAR FRONTAL
Nome: Presente Lunar Frontal
Chakra: Frontal (6º)
Polaridade: Presente Lunar
Tema: Desequilíbrios de intuição no presente — perspectiva receptiva.
Indicação: Intuição barulhenta (confusão entre intuição e medo), dificuldade de confiar na percepção interna.
Balanceamento: Silencia o ruído mental, apura a intuição.

5. FUTURO SOLAR FRONTAL
Nome: Futuro Solar Frontal
Chakra: Frontal (6º)
Polaridade: Futuro Solar
Tema: Visão do futuro — perspectiva ativa.
Indicação: Dificuldade de visualizar o futuro, falta de propósito e direção.
Balanceamento: Abre a visão de futuro, clareza sobre o caminho.

6. FUTURO LUNAR FRONTAL
Nome: Futuro Lunar Frontal
Chakra: Frontal (6º)
Polaridade: Futuro Lunar
Tema: Visão do futuro — perspectiva intuitiva.
Indicação: Medo do que pode "ver" no futuro, bloqueio de profecias pessoais.
Balanceamento: Confiança na visão intuitiva do futuro.

7. INTEGRATIVO FRONTAL
Nome: Integrativo Frontal
Chakra: Frontal (6º)
Polaridade: Integrativo
Tema: Integração completa da visão e intuição.
Indicação: Integração de todas as dimensões perceptivas.
Balanceamento: Clareza plena, intuição integrada com razão.

COMPOSTOS DO CHAKRA FRONTAL:
- Bálsamo Frontal: fórmula composta com os 7 florais do chakra frontal
- Rescue Frontal (Resgate Frontal): fórmula de emergência para crises de clareza mental
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — CHAKRA CORONÁRIO (7º Chakra)
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Florais do Chakra Coronário (Sahasrara)"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS CHAKRA CORONÁRIO
Keywords: kit primus, chakra coronário, sahasrara, sétimo chakra, 7º chakra, coroa, conexão espiritual, transcendência, florais coronário

O Chakra Coronário (Sahasrara) é o 7º chakra, localizado no topo da cabeça.
Governa: conexão com o divino, transcendência, propósito de vida, consciência cósmica, espiritualidade.
Elemento: Consciência pura
Substâncias alquímicas: Sulphur Mercurial Coronário + Sal Sulfúrico Coronário
Biorritmo: 2 horas

FLORAIS DO KIT PRIMUS PARA O CHAKRA CORONÁRIO:

1. PASSADO SOLAR CORONÁRIO
Nome: Passado Solar Coronário
Chakra: Coronário (7º)
Polaridade: Passado Solar
Tema: Bloqueios espirituais do passado — linhagem paterna.
Indicação: Traumas espirituais herdados do pai; corte da conexão divina por padrão paterno.
Balanceamento: Restaura a conexão espiritual masculina do passado.

2. PASSADO LUNAR CORONÁRIO
Nome: Passado Lunar Coronário
Chakra: Coronário (7º)
Polaridade: Passado Lunar
Tema: Bloqueios espirituais do passado — linhagem materna.
Indicação: Traumas espirituais herdados da mãe; religiões impostas; corte da fé.
Balanceamento: Restaura a conexão espiritual feminina do passado.

3. PRESENTE SOLAR CORONÁRIO
Nome: Presente Solar Coronário
Chakra: Coronário (7º)
Polaridade: Presente Solar
Tema: Desconexão espiritual no presente — perspectiva ativa.
Indicação: Vazio existencial atual, falta de propósito, ateísmo defensivo.
Balanceamento: Reconexão com propósito e espiritualidade no presente.

4. PRESENTE LUNAR CORONÁRIO
Nome: Presente Lunar Coronário
Chakra: Coronário (7º)
Polaridade: Presente Lunar
Tema: Desconexão espiritual no presente — perspectiva receptiva.
Indicação: Dificuldade de receber graça e sincronicidades, bloqueio na conexão meditativa.
Balanceamento: Receptividade espiritual, abertura para a graça.

5. FUTURO SOLAR CORONÁRIO
Nome: Futuro Solar Coronário
Chakra: Coronário (7º)
Polaridade: Futuro Solar
Tema: Propósito e missão futura — perspectiva ativa.
Indicação: Dúvida sobre a missão de vida, medo de não cumprir o propósito.
Balanceamento: Clareza e confiança na missão futura.

6. FUTURO LUNAR CORONÁRIO
Nome: Futuro Lunar Coronário
Chakra: Coronário (7º)
Polaridade: Futuro Lunar
Tema: Propósito e missão futura — perspectiva receptiva.
Indicação: Resistência em se entregar ao propósito maior, medo da transcendência.
Balanceamento: Entrega suave ao fluxo divino do futuro.

7. INTEGRATIVO CORONÁRIO
Nome: Integrativo Coronário
Chakra: Coronário (7º)
Polaridade: Integrativo
Tema: Integração completa da conexão espiritual.
Indicação: Quando o ser precisa integrar todas as dimensões espirituais.
Balanceamento: Iluminação integrada, conexão divina plena.

COMPOSTOS DO CHAKRA CORONÁRIO:
- Bálsamo Coronário: fórmula composta com os 7 florais do chakra coronário
- Rescue Coronário (Resgate Coronário): fórmula de emergência para crises espirituais

FÓRMULAS COM RESCUE CORONÁRIO:
Indicado para: crises espirituais agudas, ataques de ego, perda total de propósito, colapso de fé.
"""

# ---------------------------------------------------------------------------
# RESCUE FLORAIS — FLORAIS DE RESGATE (todos os chakras)
# ---------------------------------------------------------------------------
DOCS["Rescue Florais — Florais de Resgate do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — RESCUE FLORAIS (FLORAIS DE RESGATE)
Keywords: rescue, resgate, rescue floral, floral resgate, emergência, crise, rescue basal, rescue umbilical, rescue plexo, rescue cardíaco, rescue laríngeo, rescue frontal, rescue coronário

Os Florais de Resgate (Rescue) são fórmulas de emergência do método Joel Aleixo.
Cada chakra tem seu próprio Rescue específico.
NÃO confundir com Rescue Remedy de Bach — os Rescues Joel Aleixo são exclusivos do método alquímico.

LISTA COMPLETA DOS RESCUES POR CHAKRA:

RESCUE BASAL (Resgate Basal)
Chakra: Basal (1º)
Indicação: Crises de enraizamento aguda, perda de chão, desamparo extremo, colapso financeiro repentino.
Uso: Emergência de enraizamento e sobrevivência.

RESCUE UMBILICAL (Resgate Umbilical)
Chakra: Umbilical (2º)
Indicação: Crises emocionais agudas, choro sem motivo aparente, colapso emocional, hipersensibilidade extrema, ansiedade emocional intensa.
Uso: Emergência emocional, quando as emoções ficam incontroláveis.

RESCUE PLEXO SOLAR (Resgate Plexo Solar)
Chakra: Plexo Solar (3º)
Indicação: Crises de identidade aguda, ataques de pânico relacionados ao poder pessoal, colapso de autoestima súbito.
Uso: Emergência de poder pessoal e identidade.

RESCUE CARDÍACO (Resgate Cardíaco)
Chakra: Cardíaco (4º)
Indicação: Rupturas afetivas agudas, luto, coração partido, crises de compaixão excessiva, síndrome do cuidador em colapso.
Uso: Emergência afetiva e de cura do coração.

RESCUE LARÍNGEO (Resgate Laríngeo)
Chakra: Laríngeo (5º)
Indicação: Bloqueios de expressão agudos, perda súbita de voz energética, gagueira de crise, calar-se por medo extremo.
Uso: Emergência de expressão e comunicação.

RESCUE FRONTAL (Resgate Frontal)
Chakra: Frontal (6º)
Indicação: Confusão mental extrema, dissociação, crise de percepção, perda de discernimento aguda.
Uso: Emergência de clareza mental e percepção.

RESCUE CORONÁRIO (Resgate Coronário)
Chakra: Coronário (7º)
Indicação: Crises espirituais agudas, ataques de ego, perda total de propósito, colapso de fé.
Uso: Emergência espiritual e de propósito.

COMO USAR OS RESCUES:
Os Rescues são usados em momentos de crise aguda, como primeira resposta.
Para suporte continuado, usa-se o Bálsamo do chakra correspondente.
Pode-se combinar o Rescue com o Bálsamo do mesmo chakra para transição da crise para o equilíbrio.
"""

# ---------------------------------------------------------------------------
# BÁLSAMOS — COMPOSTOS POR CHAKRA
# ---------------------------------------------------------------------------
DOCS["Bálsamos Alquímicos — Compostos por Chakra do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — BÁLSAMOS ALQUÍMICOS
Keywords: bálsamo, bálsamos, composto, compostos, balsamico, balsamicos, bálsamo basal, bálsamo umbilical, bálsamo plexo, bálsamo cardíaco, bálsamo laríngeo, bálsamo frontal, bálsamo coronário

Os Bálsamos são compostos alquímicos que reúnem os 7 florais de um chakra em uma única fórmula.
Método Joel Aleixo — uso para equilíbrio contínuo de um chakra específico.

LISTA COMPLETA DOS BÁLSAMOS:

BÁLSAMO BASAL
Composição: todos os 7 florais do Chakra Basal (Passado Solar/Lunar + Presente Solar/Lunar + Futuro Solar/Lunar + Integrativo)
Indicação: Trabalho prolongado de enraizamento, estabilidade financeira, questões de sobrevivência crônicas.
Uso: Suporte contínuo ao chakra basal.

BÁLSAMO UMBILICAL
Composição: todos os 7 florais do Chakra Umbilical
Indicação: Trabalho prolongado de equilíbrio emocional, ansiedade crônica, padrões emocionais repetitivos.
Uso: Suporte contínuo ao equilíbrio emocional.

BÁLSAMO PLEXO SOLAR
Composição: todos os 7 florais do Chakra Plexo Solar
Indicação: Trabalho prolongado de poder pessoal, autoestima, identidade.
Uso: Suporte contínuo ao poder pessoal.

BÁLSAMO CARDÍACO
Composição: todos os 7 florais do Chakra Cardíaco
Indicação: Trabalho prolongado de cura do coração, relacionamentos, compaixão.
Uso: Suporte contínuo ao amor e relações.

BÁLSAMO LARÍNGEO
Composição: todos os 7 florais do Chakra Laríngeo
Indicação: Trabalho prolongado de expressão, comunicação, voz autêntica.
Uso: Suporte contínuo à expressão.

BÁLSAMO FRONTAL
Composição: todos os 7 florais do Chakra Frontal
Indicação: Trabalho prolongado de clareza mental, intuição, discernimento.
Uso: Suporte contínuo à percepção e clareza.

BÁLSAMO CORONÁRIO
Composição: todos os 7 florais do Chakra Coronário
Indicação: Trabalho prolongado de conexão espiritual, propósito, transcendência.
Uso: Suporte contínuo à espiritualidade.

BÁLSAMO INTEGRAL (quando disponível)
Indicação: Equilíbrio de todos os chakras simultaneamente.
"""

# ---------------------------------------------------------------------------
# KIT PRIMUS — VISÃO GERAL COMPLETA
# ---------------------------------------------------------------------------
DOCS["Kit Primus — Visão Geral do Sistema de 99 Flores"] = """
CONHECIMENTO ESTRUTURADO — KIT PRIMUS VISÃO GERAL
Keywords: kit primus, 99 flores, noventa e nove flores, sistema floral, florais alquímicos, método joel aleixo, chakras florais, polaridades florais

O KIT PRIMUS é o sistema floral exclusivo do método alquímico do Joel Aleixo.
Composto por 99 florais alquímicos organizados por chakra e polaridade.

ESTRUTURA DO KIT PRIMUS:
- 7 chakras × 7 polaridades = 49 florais individuais
- + 7 Bálsamos (um por chakra) = 56
- + 7 Rescues (um por chakra) = 63
- + outros compostos e fórmulas especiais = até 99

OS 7 CHAKRAS:
1. Chakra Basal (Muladhara) — Terra — Enraizamento
2. Chakra Umbilical (Svadhisthana) — Água — Emoções
3. Chakra Plexo Solar (Manipura) — Fogo — Poder
4. Chakra Cardíaco (Anahata) — Ar — Amor
5. Chakra Laríngeo (Vishuddha) — Éter — Expressão
6. Chakra Frontal (Ajna) — Luz — Intuição/Visão
7. Chakra Coronário (Sahasrara) — Consciência — Espiritualidade

AS 7 POLARIDADES DE CADA CHAKRA:
1. Passado Solar — traumas/padrões do passado, linhagem paterna
2. Passado Lunar — traumas/padrões do passado, linhagem materna
3. Presente Solar — desequilíbrios atuais, perspectiva ativa/expressiva
4. Presente Lunar — desequilíbrios atuais, perspectiva receptiva/intuitiva
5. Futuro Solar — medos e bloqueios projetados no futuro, perspectiva ativa
6. Futuro Lunar — medos e bloqueios projetados no futuro, perspectiva receptiva
7. Integrativo — integração de todas as polaridades do chakra

NOMENCLATURA:
Cada floral é nomeado como: [Polaridade] [Chakra]
Exemplos:
- "Presente Solar Umbilical" = floral para desequilíbrio emocional ativo no presente (chakra umbilical)
- "Passado Lunar Basal" = floral para traumas de enraizamento maternos (chakra basal)
- "Integrativo Coronário" = floral integrador do chakra coronário

DIFERENÇA DO FLORAL DE BACH:
Os florais do Kit Primus NÃO são florais de Bach, não são derivados de Bach e não têm relação com o sistema de Bach.
São florais alquímicos exclusivos desenvolvidos por Joel Aleixo.
Nunca mencionar "Bach" ao falar dos florais Joel Aleixo.

COMO PRESCREVER:
1. Identificar o chakra mais comprometido
2. Identificar a polaridade afetada (passado/presente/futuro, solar/lunar)
3. Prescrever o floral específico OU o Bálsamo para trabalho contínuo
4. Em emergências: prescrever o Rescue do chakra correspondente
"""

# ---------------------------------------------------------------------------
# DNA ALQUÍMICO
# ---------------------------------------------------------------------------
DOCS["DNA Alquímico — Padrões Comprometidos do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — DNA ALQUÍMICO
Keywords: DNA alquímico, DNA comprometido, padrões DNA, alquimia DNA, código DNA, hereditariedade alquímica, padrões herdados, marcadores alquímicos

O DNA Alquímico no método Joel Aleixo refere-se a padrões energéticos e emocionais hereditários
que se manifestam de forma repetida nas linhagens familiares.

CONCEITO:
O DNA Alquímico é uma metáfora para o conjunto de padrões vibratórios herdados que influenciam
a saúde emocional, espiritual e física de uma pessoa.
Quando o DNA está "comprometido", há padrões que se repetem de geração em geração.

TIPOS DE DNA COMPROMETIDO (exemplos comuns):
- DNA de abandono: padrão de ser abandonado ou abandonar
- DNA de escassez: padrão de nunca ter o suficiente
- DNA de traição: padrão de trair ou ser traído
- DNA de rejeição: padrão de se sentir rejeitado
- DNA de culpa: padrão de carregar culpa geracional
- DNA de poder: padrão de abuso de poder ou submissão
- DNA de silêncio: padrão de não poder se expressar
- DNA de doença: padrão de adoecimento geracional

DIAGNÓSTICO DO DNA ALQUÍMICO:
- Observado através do mapa natal alquímico
- Identificado nas repetições de padrões na história familiar
- Confirmado pela análise dos elementos e chakras comprometidos

TRATAMENTO:
- Florais do Kit Primus das polaridades Passado Solar e Passado Lunar (dos chakras comprometidos)
- Trabalho com os setenios correspondentes
- Protocolo de desprogramação alquímica
"""

# ---------------------------------------------------------------------------
# SERPENTES ALQUÍMICAS
# ---------------------------------------------------------------------------
DOCS["Serpentes Alquímicas — As 7 Serpentes do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — SERPENTES ALQUÍMICAS
Keywords: serpentes, serpentes alquímicas, 7 serpentes, serpente, kundalini alquímica, padrões serpente, bloqueios serpente

As Serpentes Alquímicas no método Joel Aleixo representam padrões de comportamento
e bloqueios energéticos específicos que "enrolam" a energia vital da pessoa.

CONCEITO:
Cada "serpente" é um padrão repetitivo que drena energia e mantém a pessoa presa.
O trabalho alquímico busca "despertar" ou "transmutar" as serpentes comprometidas.

AS 7 SERPENTES (padrões principais):
1. Serpente do Medo: padrão de paralisação pelo medo, dificuldade de agir
2. Serpente da Raiva: padrão de raiva reprimida ou explosiva, ressentimento
3. Serpente da Tristeza: padrão de melancolia, depressão, luto não resolvido
4. Serpente do Orgulho: padrão de arrogância, dificuldade de pedir ajuda
5. Serpente da Inveja: padrão de comparação, falta de gratidão pelo próprio caminho
6. Serpente da Preguiça: padrão de estagnação, resistência ao movimento
7. Serpente da Luxúria/Desejo: padrão de apego excessivo, dependência

COMO IDENTIFICAR AS SERPENTES ATIVAS:
- Análise do mapa natal alquímico
- Padrões de comportamento repetitivos
- Chakras comprometidos que se correlacionam com cada serpente

TRATAMENTO DAS SERPENTES:
- Florais específicos por chakra relacionado à serpente ativa
- Trabalho com os setenios
- Compostos alquímicos indicados pelo terapeuta
"""

# ---------------------------------------------------------------------------
# SETENIOS
# ---------------------------------------------------------------------------
DOCS["Setenios — Ciclos de 7 Anos do Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — SETENIOS
Keywords: setenio, setenios, ciclos 7 anos, sete anos, ciclo vital, fases de vida, ciclos alquímicos, idade ciclo

Os Setenios (ou Seteênios) são ciclos de 7 anos que estruturam o desenvolvimento humano
segundo o método Joel Aleixo. Cada ciclo governa um chakra específico.

ESTRUTURA DOS SETENIOS:

1º SETENIO (0-7 anos) — Chakra Basal
Tema: Enraizamento, segurança básica, sobrevivência.
Questões: Como foi o nascimento? A infância foi segura? Havia comida e abrigo?
Impacto: Define os padrões básicos de segurança e enraizamento.

2º SETENIO (7-14 anos) — Chakra Umbilical
Tema: Emoções, relações familiares, identidade emocional.
Questões: Como eram as relações familiares? As emoções eram permitidas?
Impacto: Define os padrões emocionais e de relacionamento.

3º SETENIO (14-21 anos) — Chakra Plexo Solar
Tema: Identidade, poder pessoal, adolescência, individualidade.
Questões: Como foi a adolescência? O poder pessoal foi respeitado?
Impacto: Define os padrões de poder pessoal e identidade.

4º SETENIO (21-28 anos) — Chakra Cardíaco
Tema: Amor, relacionamentos adultos, parcerias, abertura do coração.
Questões: Como foram os primeiros relacionamentos adultos? O coração se abriu?
Impacto: Define os padrões de amor e vínculos afetivos.

5º SETENIO (28-35 anos) — Chakra Laríngeo
Tema: Expressão, carreira, comunicação, propósito profissional.
Questões: A pessoa se expressa autenticamente? Encontrou sua voz profissional?
Impacto: Define os padrões de expressão e realização profissional.

6º SETENIO (35-42 anos) — Chakra Frontal
Tema: Visão, sabedoria, intuição, meio da vida.
Questões: A pessoa usa sua intuição? Tem clareza de propósito?
Impacto: Define os padrões de percepção e sabedoria.

7º SETENIO (42-49 anos) — Chakra Coronário
Tema: Espiritualidade, legado, conexão com o divino.
Questões: A pessoa tem propósito espiritual? Que legado está construindo?
Impacto: Define os padrões espirituais e de transcendência.

SETENIOS SUBSEQUENTES:
8º Setenio (49-56): Novo ciclo, integração de todos os chakras.
Os ciclos se repetem com maior profundidade espiritual.

APLICAÇÃO CLÍNICA:
- Identificar em qual setenio o paciente está atualmente
- Analisar os traumas dos setenios anteriores (especialmente 1º, 2º e 3º)
- Prescrever florais correspondentes ao setenio comprometido
- O mapa natal mostra os setenios mais críticos
"""

# ---------------------------------------------------------------------------
# ELEMENTOS ALQUÍMICOS
# ---------------------------------------------------------------------------
DOCS["Elementos Alquímicos — Fogo, Terra, Água, Ar, Éter no Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — ELEMENTOS ALQUÍMICOS
Keywords: elementos, elementos alquímicos, fogo, terra, água, ar, éter, elemento dominante, elemento carente, balanceamento elementos, diagnóstico elementos

Os Elementos Alquímicos são a base do diagnóstico no método Joel Aleixo.
Cada pessoa tem uma composição elementar única que define sua personalidade e padrões.

OS 5 ELEMENTOS:

FOGO
Chakra associado: Plexo Solar
Características positivas: Liderança, ação, transformação, coragem, vitalidade, iniciativa.
Excesso: Agressividade, impaciência, dominância, queimar o outro.
Carência: Falta de energia, passividade, dificuldade de agir.
Tipo físico: Corpo quente, ativo, dinâmico.

TERRA
Chakra associado: Basal
Características positivas: Estabilidade, pragmatismo, senso prático, materialidade saudável.
Excesso: Rigidez, teimosia, apego ao material, conservadorismo excessivo.
Carência: Instabilidade, falta de enraizamento, dificuldade de concretizar.
Tipo físico: Corpo denso, sólido.

ÁGUA
Chakra associado: Umbilical
Características positivas: Sensibilidade, empatia, fluidez, criatividade, intuição emocional.
Excesso: Hipersensibilidade, fusão com o outro, reatividade emocional, ciúme.
Carência: Frieza emocional, dificuldade de sentir, robotismo afetivo.
Tipo físico: Corpo fluido, adaptável.

AR
Chakra associado: Laríngeo e Cardíaco
Características positivas: Comunicação, inteligência, versatilidade, leveza, conexão.
Excesso: Dispersão, superficialidade, instabilidade, falta de comprometimento.
Carência: Dificuldade de comunicação, isolamento, pensamento lento.
Tipo físico: Corpo leve, ágil.

ÉTER
Chakra associado: Frontal e Coronário
Características positivas: Espiritualidade, intuição superior, visão ampla, propósito.
Excesso: Desconexão do plano material, "pé no ar", sonhador sem ação.
Carência: Materialismo excessivo, falta de propósito, vazio existencial.
Tipo físico: Corpo delicado, sutil.

DIAGNÓSTICO ELEMENTAR:
- Elemento Dominante: o elemento mais presente na composição — forças e excessos
- Elemento Carente: o elemento menos presente — vulnerabilidades e crescimento
- Desequilíbrio elementar: quando um elemento domina em excesso ou está muito carente

TRATAMENTO POR ELEMENTO:
- Excesso de Fogo: florais do Plexo Solar (resfriamento)
- Excesso de Água: florais do Umbilical (equilíbrio emocional)
- Carência de Terra: florais Basais (enraizamento)
- Carência de Ar: florais Laríngeos (expressão)
- Desequilíbrio de Éter: florais Frontais/Coronários
"""

# ---------------------------------------------------------------------------
# MAPA NATAL ALQUÍMICO
# ---------------------------------------------------------------------------
DOCS["Mapa Natal Alquímico — Interpretação no Método Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — MAPA NATAL ALQUÍMICO
Keywords: mapa natal, mapa alquímico, mapa astral, astrologia alquímica, mapa de nascimento, interpretação mapa, leitura mapa, signos, planetas, casas

O Mapa Natal Alquímico é a ferramenta central de diagnóstico do método Joel Aleixo.
Diferente da astrologia convencional, o mapa é interpretado pela ótica da alquimia.

COMPONENTES DO MAPA NATAL ALQUÍMICO:

PLANETAS E SEUS SIGNIFICADOS ALQUÍMICOS:
- Sol: identidade, ego, propósito, o "Rei interno"
- Lua: emoções, inconsciente, mãe, padrões emocionais
- Mercúrio: comunicação, mente, expressão
- Vênus: amor, relacionamentos, beleza, valores
- Marte: ação, desejo, luta, assertividade
- Júpiter: expansão, fé, prosperidade, crescimento
- Saturno: limites, estrutura, karma, lições de vida
- Urano: mudança, revolução, originalidade, quebra de padrões
- Netuno: espiritualidade, ilusão, sonho, dissolução
- Plutão: transformação profunda, morte e renascimento, poder

SIGNOS E ELEMENTOS ALQUÍMICOS:
Fogo: Áries, Leão, Sagitário
Terra: Touro, Virgem, Capricórnio
Ar: Gêmeos, Libra, Aquário
Água: Câncer, Escorpião, Peixes

CASAS ASTROLÓGICAS E CHAKRAS:
Casa 1 (Ascendente): identidade, chakra basal/plexo solar
Casa 2: recursos materiais, chakra basal
Casa 4: família, ancestralidade, chakra basal/umbilical
Casa 5: criatividade, prazer, chakra cardíaco/plexo
Casa 7: relacionamentos, parcerias, chakra cardíaco
Casa 10 (Meio do Céu): carreira, propósito público, chakra laríngeo/coronário
Casa 12: inconsciente, karma, chakra frontal/coronário

INTERPRETAÇÃO ALQUÍMICA:
O terapeuta Joel Aleixo usa o mapa para:
1. Identificar elementos dominantes e carentes
2. Mapear padrões de DNA Alquímico (aspectos tensos entre planetas)
3. Identificar serpentes ativas (configurações específicas)
4. Determinar o setenio atual e seus desafios
5. Prescrever florais do Kit Primus com base no mapa

GERAÇÃO DO MAPA:
Para gerar o mapa natal são necessários:
- Data de nascimento (dia, mês, ano)
- Hora de nascimento (HH:MM — quanto mais precisa, melhor)
- Cidade de nascimento
"""

# ---------------------------------------------------------------------------
# PROTOCOLO CLÍNICO
# ---------------------------------------------------------------------------
DOCS["Protocolo Clínico — Fluxo de Diagnóstico e Prescrição Joel Aleixo"] = """
CONHECIMENTO ESTRUTURADO — PROTOCOLO CLÍNICO
Keywords: protocolo, protocolo clínico, diagnóstico, prescrição, fluxo de atendimento, consulta, sessão, como diagnosticar, como prescrever

FLUXO PADRÃO DE UMA SESSÃO (Método Joel Aleixo):

1. ANAMNESE ALQUÍMICA
- Queixa principal do paciente
- História familiar (pais, avós — padrões repetidos)
- Setenio atual e histórico dos setenios
- Sintomas físicos (correlacionados com chakras)
- Padrões emocionais recorrentes

2. ANÁLISE DO MAPA NATAL
- Levantamento do mapa: data + hora + cidade de nascimento
- Identificação do elemento dominante e carente
- Planetas comprometidos (aspectos tensos: quadratura, oposição, conjunção tensa)
- DNA Alquímico comprometido
- Serpentes ativas

3. DIAGNÓSTICO ALQUÍMICO
- Chakras comprometidos (primário e secundário)
- Polaridades afetadas (passado/presente/futuro, solar/lunar)
- Elementos desequilibrados
- Setenio de origem do trauma

4. PRESCRIÇÃO DO KIT PRIMUS
- Florais individuais por chakra e polaridade
- OU Bálsamo do chakra comprometido
- Rescue para situações de emergência
- Dosagem: conforme protocolo do método

5. ACOMPANHAMENTO
- Retorno em 30-45 dias
- Reavaliação do progresso
- Ajuste da prescrição se necessário
- Registro em prontuário alquímico

PERGUNTAS-CHAVE PARA DIAGNÓSTICO:
- "Qual é o padrão que mais se repete na sua vida?"
- "Como era a relação com seu pai/mãe?"
- "Em que área da vida você sente mais dificuldade?"
- "Você tem sintomas físicos? Onde no corpo?"
- "Qual foi o evento mais marcante da sua vida?"
"""


async def main():
    settings = get_settings()
    print(f"\nConectado ao Supabase: {settings.SUPABASE_URL[:40]}...")
    print(f"Terapeuta ID: {TERAPEUTA_ID}")
    print(f"\nTotal de documentos a indexar: {len(DOCS)}")

    for titulo, conteudo in DOCS.items():
        await indexar_documento(titulo, conteudo, f"Conhecimento estruturado: {titulo}")

    print(f"\n{'='*60}")
    print(f"INDEXAÇÃO CONCLUÍDA!")
    print(f"Total de documentos indexados: {len(DOCS)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
