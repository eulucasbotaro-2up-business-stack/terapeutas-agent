"""
Script para taguear os chunks restantes sem modulo/tags na tabela embeddings.
Atualiza baseado no campo metadata->arquivo_fonte ou metadata->nome_arquivo.
"""

import psycopg2

DB_URL = "postgresql://postgres.vtcjuaiuyjizkuyqfhtj:MwFljvUegz3UFcXj@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres"

# Mapeamento: padroes de nome -> (modulo, tags)
# Usa startswith para match parcial
MAPEAMENTO = {
    # PDFs principais (por nome exato ou prefixo)
    "DNA.pdf": (3, ["dna", "dna_alquimico", "7_cores", "chakra"]),
    "ASTROLOGIA.pdf": (5, ["astrologia", "mapa_astral"]),
    "MATRIX E TRAUMAS.pdf": (2, ["matrix", "traumas", "heranca"]),
    "QUATRO ELEMENTOS E PLETORA.pdf": (2, ["4_elementos", "pletora"]),
    "COMO USAR OS PROTOCOLOS.pdf": (6, ["protocolos", "florais", "tratamento"]),
    "PERGUNTAS FREQUENTES": (1, ["fundamentos", "perguntas"]),
    "Material de Pesquisa.pdf": (1, ["fundamentos", "pesquisa"]),
    "PESQUISA AVANCADA.pdf": (1, ["fundamentos", "pesquisa"]),
    "PESQUISA AVAN": (1, ["fundamentos", "pesquisa"]),
    "APROFUNDAMENTO NOS 7 CHACKRAS.pdf": (5, ["chakra", "7_cores"]),
    "M1.Apostila": (1, ["fundamentos", "modulo1"]),
    "M2.Apostila": (2, ["elementos", "modulo2"]),
    "M3.Apostila": (3, ["dna", "modulo3"]),
    "M4.Apostila": (4, ["transmutacao", "modulo4", "avancado"]),
    "O Fluxus": (5, ["fluxus", "astrologia"]),
    "REFERENCIA DO DNA": (3, ["dna", "dna_referencia"]),
    "Miasmas.pdf": (2, ["miasma", "matrix_heranca"]),
    "Apostila Trindade e Tartarus": (4, ["transmutacao", "nigredo", "trindade"]),
    "Apostila Rubedo": (4, ["transmutacao", "rubedo"]),
    "BIORRITIMOS.pdf": (5, ["biorritmo", "astro_ciclo"]),
    "SIGNIFICADO KITE PRIMUS": (6, ["protocolo", "kit_primus"]),
    "A Aura das flores": (6, ["floral", "floral_aura"]),
    # YouTube
    "YouTube - ": (1, ["youtube", "joel_fala"]),
    # NotebookLM
    "NotebookLM - Como Joel Diagnostica": (1, ["notebooklm", "referencia", "diagnostico"]),
    "NotebookLM - Mapeamento Diagnostico Alquimico": (1, ["notebooklm", "referencia", "diagnostico"]),
    "NotebookLM - Matrix e Heranca Ancestral": (2, ["notebooklm", "referencia", "matrix", "heranca"]),
    "NotebookLM - Tabela Sintomas e Causas Alquimicas": (1, ["notebooklm", "referencia", "diagnostico"]),
    "NotebookLM - Tipos de Florais Alquimicos": (6, ["notebooklm", "referencia", "floral"]),
    "NotebookLM - Voz e Estilo do Joel": (1, ["notebooklm", "referencia"]),
}


def match_arquivo(nome):
    """Encontra o mapeamento correto para um nome de arquivo."""
    if not nome:
        return None
    # Tenta match exato primeiro
    if nome in MAPEAMENTO:
        return MAPEAMENTO[nome]
    # Tenta match por prefixo (do mais especifico pro mais generico)
    for pattern, value in sorted(MAPEAMENTO.items(), key=lambda x: -len(x[0])):
        if nome.startswith(pattern):
            return value
    return None


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Busca chunks sem modulo
    cur.execute("""
        SELECT id, metadata->>'arquivo_fonte' as af, metadata->>'nome_arquivo' as na
        FROM embeddings
        WHERE modulo IS NULL
    """)
    rows = cur.fetchall()
    print(f"Encontrados {len(rows)} chunks sem modulo")

    if not rows:
        print("Nada para atualizar!")
        conn.close()
        return

    # Agrupa por arquivo para log
    updated = 0
    skipped = 0
    not_found = set()

    for chunk_id, arquivo_fonte, nome_arquivo in rows:
        nome = arquivo_fonte or nome_arquivo
        mapping = match_arquivo(nome)

        if mapping:
            modulo, tags = mapping
            cur.execute(
                "UPDATE embeddings SET modulo = %s, tags = %s WHERE id = %s",
                (modulo, tags, chunk_id)
            )
            updated += 1
        else:
            not_found.add(nome)
            skipped += 1

    conn.commit()
    print(f"\nResultado:")
    print(f"  Atualizados: {updated}")
    print(f"  Ignorados: {skipped}")
    if not_found:
        print(f"  Arquivos sem mapeamento: {not_found}")

    # Verificacao final
    cur.execute("SELECT count(*) FROM embeddings WHERE modulo IS NULL")
    remaining = cur.fetchone()[0]
    print(f"\nChunks restantes sem modulo: {remaining}")

    conn.close()


if __name__ == "__main__":
    main()
