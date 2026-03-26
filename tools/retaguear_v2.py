"""
Re-tagueia chunks existentes no Supabase com modulo e tags.
Usa UPDATE individual por arquivo para evitar timeouts no pooler.
"""

import psycopg2
import sys

CONN_STRING = "postgresql://postgres.vtcjuaiuyjizkuyqfhtj:MwFljvUegz3UFcXj@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres"

PDF_MAP = {
    "Material de Pesquisa.pdf": (1, ["fundamentos", "pesquisa", "conceito_basico"]),
    "PESQUISA AVAN\u00c7ADA.pdf": (1, ["fundamentos", "pesquisa"]),
    "PERGUNTAS FREQUENTES.pdf": (1, ["fundamentos", "faq"]),
    "PERGUNTAS FREQUENTES \u2013 4 ELEMENTOS & PLETORA.pdf": (1, ["fundamentos", "faq", "elementos", "pletora"]),
    "M1.Apostila-Modulo-1 .pdf": (1, ["fundamentos", "conceito_basico"]),
    "QUATRO ELEMENTOS E PLETORA.pdf": (2, ["elementos", "pletora", "elemento_terra", "elemento_agua", "elemento_fogo", "elemento_ar"]),
    "MATRIX E TRAUMAS.pdf": (2, ["matrix", "matrix_trauma", "matrix_padrao"]),
    "M2.Apostila - Phoenix-e-Pletora .pdf": (2, ["elementos", "pletora", "phoenix"]),
    "M2.Apostila -Trindade-e-Tartarus.pdf": (2, ["transmutacao", "trindade", "tartarus"]),
    "DNA.pdf": (3, ["dna", "dna_leitura"]),
    "M3.Apostila M\u00f3dulo 3.pdf": (3, ["dna"]),
    "M4.Apostila - Alquimia Avan\u00e7ada.pdf": (4, ["transmutacao", "aliastrum"]),
    "M4.Apostila Aliastrum.pdf": (4, ["transmutacao", "aliastrum"]),
    "M4.Apostila Matrix.pdf": (4, ["matrix", "matrix_campo"]),
    "M4.apostila_guia_vitriol_torus_06.05.16 - Logo Escola de Alquimia (1).pdf": (4, ["vitriol", "torus"]),
    "ASTROLOGIA.pdf": (5, ["astrologia", "astro_mapa", "astro_ciclo"]),
    "APROFUNDAMENTO NOS 7 CHACKRAS.pdf": (5, ["chakra", "chakra_base", "chakra_sacral", "chakra_plexo", "chakra_cardiaco", "chakra_laringeo", "chakra_frontal", "chakra_coronario"]),
    "O Fluxus Continuum de John Dee PDF (1).pdf": (5, ["fluxus", "astro_ciclo"]),
    "O Fluxus Continuum de John Dee PDF.pdf": (5, ["fluxus", "astro_ciclo"]),
    "COMO USAR OS PROTOCOLOS.pdf": (6, ["protocolo", "protocolo_uso"]),
}

YT_MAP = {
    "A Cura no mundo dos n": (5, ["biorritmo", "astrologia", "youtube", "joel_fala"]),
    "A Escolha de Curar": (1, ["fundamentos", "youtube", "joel_fala"]),
    "A vida s\u00f3 muda": (1, ["fundamentos", "youtube", "joel_fala"]),
    "Alchemy is practiced": (6, ["floral", "youtube", "joel_fala"]),
    "Cure-se de quem": (1, ["fundamentos", "matrix_padrao", "youtube", "joel_fala"]),
    "Da Hist\u00f3ria da Arte": (2, ["elementos", "youtube", "joel_fala"]),
    "De Volta a Si": (5, ["chakra", "biorritmo", "youtube", "joel_fala"]),
    "Dermatite": (2, ["miasma", "matrix_trauma", "youtube", "joel_fala"]),
    "Do Bournout": (4, ["transmutacao", "matrix_trauma", "youtube", "joel_fala"]),
    "Don\u2019t underestimate": (6, ["protocolo", "youtube", "joel_fala"]),
    "Don't underestimate": (6, ["protocolo", "youtube", "joel_fala"]),
    "Every cancer patient": (3, ["dna", "matrix_heranca", "youtube", "joel_fala"]),
    "Floral Alchemy": (6, ["floral", "youtube", "joel_fala"]),
    "Gerar Vida": (5, ["biorritmo", "youtube", "joel_fala"]),
    "How to awaken": (3, ["dna", "chakra", "youtube", "joel_fala"]),
    "Joel, why can": (6, ["floral", "protocolo", "youtube", "joel_fala"]),
    "DERES": (6, ["protocolo", "matrix_trauma", "youtube", "joel_fala"]),
    "Limiting Beliefs": (2, ["matrix_padrao", "youtube", "joel_fala"]),
    "Living by Alchemy": (1, ["fundamentos", "youtube", "joel_fala"]),
    "O Encontro Que Fechou": (4, ["transmutacao", "youtube", "joel_fala"]),
    "PARE DE HERDAR": (2, ["matrix_heranca", "miasma", "youtube", "joel_fala"]),
    "QUANDO A VOZ CALA": (3, ["dna", "matrix_trauma", "youtube", "joel_fala"]),
    "Quando nada preenche": (4, ["transmutacao", "matrix_padrao", "youtube", "joel_fala"]),
    "QUANDO VOC": (4, ["transmutacao", "youtube", "joel_fala"]),
    "Self-Therapist": (6, ["floral", "protocolo", "youtube", "joel_fala"]),
    "Survival mechanisms": (2, ["matrix_heranca", "youtube", "joel_fala"]),
    "Taking alchemical": (6, ["floral", "youtube", "joel_fala"]),
    "Tem dores que n": (5, ["chakra", "youtube", "joel_fala"]),
    "The liberating power": (4, ["transmutacao", "youtube", "joel_fala"]),
    "Where do alchemical": (6, ["floral", "youtube", "joel_fala"]),
}


def run():
    conn = psycopg2.connect(CONN_STRING)
    cur = conn.cursor()
    # Increase timeout to 5 minutes per statement
    cur.execute("SET statement_timeout = '300s';")
    conn.commit()

    total_updated = 0

    # --- PDFs: update via JOIN com documentos ---
    print("=== Atualizando PDFs ===", flush=True)
    for nome, (modulo, tags) in PDF_MAP.items():
        try:
            cur.execute("""
                UPDATE embeddings e
                SET modulo = %s, tags = %s
                FROM documentos d
                WHERE e.documento_id = d.id
                  AND d.nome_arquivo = %s
                  AND e.modulo IS NULL
            """, (modulo, tags, nome))
            cnt = cur.rowcount
            conn.commit()
            total_updated += cnt
            if cnt > 0:
                print(f"  {cnt:>5} | M{modulo} | {nome}", flush=True)
        except Exception as ex:
            print(f"  ERRO | {nome}: {ex}", flush=True)
            conn.rollback()

    # --- YouTube: update via metadata LIKE ---
    print("\n=== Atualizando YouTube ===", flush=True)
    for pattern, (modulo, tags) in YT_MAP.items():
        try:
            cur.execute("""
                UPDATE embeddings
                SET modulo = %s, tags = %s
                WHERE documento_id IS NULL
                  AND metadata->>'arquivo_fonte' LIKE %s
                  AND modulo IS NULL
            """, (modulo, tags, f"%{pattern}%"))
            cnt = cur.rowcount
            conn.commit()
            total_updated += cnt
            if cnt > 0:
                print(f"  {cnt:>5} | M{modulo} | ...{pattern}...", flush=True)
        except Exception as ex:
            print(f"  ERRO | {pattern}: {ex}", flush=True)
            conn.rollback()

    # --- Verificacao ---
    cur.execute("SELECT COUNT(*) FROM embeddings WHERE modulo IS NOT NULL;")
    tagged = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM embeddings;")
    total = cur.fetchone()[0]
    print(f"\nAtualizado nesta execucao: {total_updated}", flush=True)
    print(f"Total com modulo: {tagged}/{total} ({tagged*100//total}%)", flush=True)

    cur.execute("""
        SELECT modulo, COUNT(*) FROM embeddings
        WHERE modulo IS NOT NULL
        GROUP BY modulo ORDER BY modulo;
    """)
    print("\nDistribuicao por modulo:", flush=True)
    for row in cur.fetchall():
        print(f"  Modulo {row[0]}: {row[1]} chunks", flush=True)

    cur.execute("SELECT COUNT(*) FROM embeddings WHERE modulo IS NULL;")
    null_count = cur.fetchone()[0]
    print(f"\nChunks sem modulo: {null_count}", flush=True)

    conn.close()
    print("\nConcluido!", flush=True)


if __name__ == "__main__":
    run()
