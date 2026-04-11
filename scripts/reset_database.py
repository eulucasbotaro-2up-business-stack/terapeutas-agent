"""
Script para RESETAR completamente o banco de dados.
Remove TODOS os dados (mantém schema/tabelas).
Depois rode seed_demo_data.py e gerar_mapas_demo.py para repopular.

Uso: python scripts/reset_database.py
"""

import requests

SUPABASE_URL = "https://vtcjuaiuyjizkuyqfhtj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ0Y2p1YWl1eWppemt1eXFmaHRqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE4Mzk4OCwiZXhwIjoyMDg5NzU5OTg4fQ.Ie1RAfW4TBFX1GKB2_5vTUKCpVV6SWWW1qa5bJoYetQ"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Tabelas na ordem correta (respeitando FKs — filhas primeiro)
TABELAS_PARA_LIMPAR = [
    "diagnosticos_alquimicos",
    "anotacoes_prontuario",
    "acompanhamentos",
    "resumos_sessao",
    "perfil_usuario",
    "chat_estado",
    "conversas",
    "mapas_astrais",
    "codigos_liberacao",
    "pacientes",
    # NÃO limpar: terapeutas (contas), portal_auth (credenciais),
    # embeddings (knowledge base), documentos (knowledge base)
]


def limpar_tabela(tabela: str) -> bool:
    """Deleta TODOS os registros de uma tabela via REST API."""
    # Usar um filtro que pega tudo: id != '00000000-0000-0000-0000-000000000000'
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?id=neq.00000000-0000-0000-0000-000000000000"
    r = requests.delete(url, headers=HEADERS)
    if r.status_code in (200, 204):
        return True
    elif r.status_code == 404:
        # Tabela pode não existir
        print(f"  [SKIP] Tabela '{tabela}' não encontrada")
        return True
    else:
        print(f"  [ERRO] {tabela}: {r.status_code} — {r.text[:200]}")
        return False


def limpar_storage():
    """Remove todos os arquivos do bucket 'mapas'."""
    # Listar arquivos
    url = f"{SUPABASE_URL}/storage/v1/object/list/mapas"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # Listar pastas (terapeuta_ids)
    r = requests.post(url, headers=headers, json={"prefix": "", "limit": 1000})
    if r.status_code != 200:
        print(f"  [AVISO] Não conseguiu listar storage: {r.status_code}")
        return

    items = r.json()
    for folder in items:
        folder_name = folder.get("name", "")
        if not folder_name:
            continue

        # Listar arquivos dentro da pasta
        r2 = requests.post(url, headers=headers, json={"prefix": f"{folder_name}/", "limit": 1000})
        if r2.status_code == 200:
            files = r2.json()
            file_paths = [f"{folder_name}/{f['name']}" for f in files if f.get("name")]

            if file_paths:
                # Deletar em batch
                del_url = f"{SUPABASE_URL}/storage/v1/object/mapas"
                r3 = requests.delete(del_url, headers=headers, json={"prefixes": file_paths})
                if r3.status_code in (200, 204):
                    print(f"  Removidos {len(file_paths)} arquivos de {folder_name}/")
                else:
                    print(f"  [AVISO] Erro ao remover arquivos: {r3.status_code}")


def main():
    print("=" * 60)
    print("RESET COMPLETO DO BANCO DE DADOS")
    print("=" * 60)
    print("\nIsso vai APAGAR todos os dados (pacientes, conversas, mapas, etc)")
    print("O schema/tabelas serão mantidos.\n")

    # Limpar tabelas
    print("[1/2] Limpando tabelas...")
    for tabela in TABELAS_PARA_LIMPAR:
        ok = limpar_tabela(tabela)
        status = "OK" if ok else "FALHA"
        print(f"  {tabela}: {status}")

    # Limpar storage
    print("\n[2/2] Limpando Storage (imagens de mapas)...")
    limpar_storage()

    print("\n" + "=" * 60)
    print("RESET CONCLUÍDO!")
    print("Agora rode:")
    print("  1. python scripts/seed_demo_data.py")
    print("  2. python scripts/gerar_mapas_demo.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
