#!/usr/bin/env python3
"""
Script de configuração do WhatsApp via Evolution API v2.

Automatiza o processo de:
1. Criar uma instância WhatsApp na Evolution API
2. Configurar o webhook para apontar para o backend FastAPI
3. Gerar e exibir o QR Code para parear o WhatsApp
4. Testar enviando uma mensagem de teste

Uso:
    python src/scripts/setup_whatsapp.py

Variáveis de ambiente carregadas do arquivo .env na raiz do projeto.
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao path para importar módulos locais
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv(PROJECT_ROOT / ".env", override=True)

# --- Configurações ---
# Usa env vars quando disponíveis, com fallback para os valores informados
EVOLUTION_API_URL = os.getenv(
    "EVOLUTION_API_URL",
    "https://evolution-api-production-33cc.up.railway.app",
).rstrip("/")
EVOLUTION_API_KEY = os.getenv(
    "EVOLUTION_API_KEY",
    "terapeutas-agent-evo-key-2026",
)
FASTAPI_BACKEND_URL = os.getenv(
    "FASTAPI_BACKEND_URL",
    "https://modest-respect-production.up.railway.app",
).rstrip("/")
WEBHOOK_ENDPOINT = f"{FASTAPI_BACKEND_URL}/webhook/evolution"

# Headers padrão para todas as requisições
HEADERS = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json",
}

# Timeout das requisições (segundos)
TIMEOUT = 30.0


# =============================================
# Funções auxiliares
# =============================================

def print_separador(titulo: str = "") -> None:
    """Imprime um separador visual no terminal."""
    print()
    print("=" * 60)
    if titulo:
        print(f"  {titulo}")
        print("=" * 60)


def print_json(data: dict) -> None:
    """Imprime um dict formatado como JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


async def fazer_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body: dict | None = None,
) -> dict | None:
    """
    Faz uma requisição HTTP à Evolution API.

    Retorna o JSON da resposta ou None em caso de erro.
    """
    url = f"{EVOLUTION_API_URL}{path}"
    try:
        response = await client.request(
            method=method,
            url=url,
            headers=HEADERS,
            json=json_body,
            timeout=TIMEOUT,
        )

        print(f"  [{method}] {path} → {response.status_code}")

        if response.status_code >= 400:
            print(f"  ERRO: {response.text}")
            return None

        # Algumas respostas podem ser vazias
        if response.text.strip():
            return response.json()
        return {}

    except httpx.ConnectError as exc:
        print(f"  ERRO DE CONEXÃO: {exc}")
        print(f"  Verifique se a Evolution API está acessível em: {EVOLUTION_API_URL}")
        return None
    except httpx.TimeoutException:
        print(f"  TIMEOUT: A requisição para {path} excedeu {TIMEOUT}s")
        return None


# =============================================
# Etapas do setup
# =============================================

async def etapa_1_criar_instancia(
    client: httpx.AsyncClient,
    nome_instancia: str,
) -> bool:
    """
    Etapa 1: Criar instância WhatsApp na Evolution API.

    Args:
        client: Cliente HTTP.
        nome_instancia: Nome da instância a criar.

    Returns:
        True se criou com sucesso, False se falhou.
    """
    print_separador("ETAPA 1 — Criar Instância WhatsApp")
    print(f"  Nome da instância: {nome_instancia}")
    print(f"  Evolution API: {EVOLUTION_API_URL}")

    resultado = await fazer_request(
        client,
        "POST",
        "/instance/create",
        json_body={
            "instanceName": nome_instancia,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        },
    )

    if resultado is None:
        print("  ✗ Falha ao criar instância.")
        return False

    print("  ✓ Instância criada com sucesso!")
    print_json(resultado)
    return True


async def etapa_2_configurar_webhook(
    client: httpx.AsyncClient,
    nome_instancia: str,
) -> bool:
    """
    Etapa 2: Configurar webhook para receber mensagens do WhatsApp.

    Args:
        client: Cliente HTTP.
        nome_instancia: Nome da instância.

    Returns:
        True se configurou com sucesso, False se falhou.
    """
    print_separador("ETAPA 2 — Configurar Webhook")
    print(f"  Webhook URL: {WEBHOOK_ENDPOINT}")
    print(f"  Eventos: MESSAGES_UPSERT")

    resultado = await fazer_request(
        client,
        "POST",
        f"/webhook/set/{nome_instancia}",
        json_body={
            "url": WEBHOOK_ENDPOINT,
            "webhookByEvents": True,
            "webhookBase64": False,
            "events": [
                "MESSAGES_UPSERT",
            ],
        },
    )

    if resultado is None:
        print("  ✗ Falha ao configurar webhook.")
        return False

    print("  ✓ Webhook configurado com sucesso!")
    print_json(resultado)
    return True


async def etapa_3_gerar_qrcode(
    client: httpx.AsyncClient,
    nome_instancia: str,
) -> bool:
    """
    Etapa 3: Gerar QR Code para parear o WhatsApp.

    Exibe o QR Code de duas formas:
    - Texto (pairing code) no terminal
    - Salva a imagem do QR Code em um arquivo PNG (se disponível em base64)

    Args:
        client: Cliente HTTP.
        nome_instancia: Nome da instância.

    Returns:
        True se gerou com sucesso, False se falhou.
    """
    print_separador("ETAPA 3 — Gerar QR Code para Pareamento")
    print(f"  Solicitando QR code da instância: {nome_instancia}")

    resultado = await fazer_request(
        client,
        "GET",
        f"/instance/connect/{nome_instancia}",
    )

    if resultado is None:
        print("  ✗ Falha ao gerar QR code.")
        return False

    print("  ✓ QR Code gerado!")

    # Tenta extrair e exibir o QR code
    # A Evolution API v2 pode retornar o QR code em diferentes formatos
    qr_base64 = resultado.get("base64")
    qr_code = resultado.get("code")
    pairing_code = resultado.get("pairingCode")

    # Exibe o pairing code se disponível
    if pairing_code:
        print()
        print(f"  CÓDIGO DE PAREAMENTO: {pairing_code}")
        print(f"  Use esse código no WhatsApp > Aparelhos Conectados > Conectar com número de telefone")

    # Exibe o código QR como texto (pode ser escaneado com apps de QR)
    if qr_code:
        print()
        print("  QR Code (texto para escanear):")
        print(f"  {qr_code}")

    # Salva a imagem do QR code se veio em base64
    if qr_base64:
        # Remove o prefixo "data:image/png;base64," se existir
        base64_data = qr_base64
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        qr_file = PROJECT_ROOT / f"qrcode_{nome_instancia}.png"
        try:
            qr_bytes = base64.b64decode(base64_data)
            qr_file.write_bytes(qr_bytes)
            print()
            print(f"  QR Code salvo em: {qr_file}")
            print(f"  Abra o arquivo e escaneie com o WhatsApp do celular.")
        except Exception as exc:
            print(f"  Aviso: Não foi possível salvar o QR code como imagem: {exc}")

    # Salva a resposta completa para referência
    response_file = PROJECT_ROOT / "qrcode_response.json"
    response_file.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Resposta completa salva em: {response_file}")

    if not qr_base64 and not qr_code and not pairing_code:
        print()
        print("  Resposta da API:")
        print_json(resultado)
        print()
        print("  Nota: O QR code pode estar em um formato diferente do esperado.")
        print("  Verifique a resposta acima e consulte a documentação da Evolution API v2.")

    return True


async def etapa_4_enviar_mensagem_teste(
    client: httpx.AsyncClient,
    nome_instancia: str,
    numero_teste: str,
) -> bool:
    """
    Etapa 4: Enviar mensagem de teste via WhatsApp.

    Args:
        client: Cliente HTTP.
        nome_instancia: Nome da instância.
        numero_teste: Número para enviar a mensagem de teste (formato: 5511999999999).

    Returns:
        True se enviou com sucesso, False se falhou.
    """
    print_separador("ETAPA 4 — Enviar Mensagem de Teste")
    print(f"  Número destino: {numero_teste}")
    print(f"  Instância: {nome_instancia}")

    mensagem_teste = (
        "🤖 *Terapeutas Agent — Teste de Conexão*\n\n"
        "Se você recebeu esta mensagem, o WhatsApp está conectado "
        "e funcionando corretamente!\n\n"
        "Este é o agente de IA do seu consultório. "
        "Em breve ele estará pronto para responder seus pacientes "
        "com base nos seus materiais e protocolos.\n\n"
        "_Equipe 2UP Business_"
    )

    resultado = await fazer_request(
        client,
        "POST",
        f"/message/sendText/{nome_instancia}",
        json_body={
            "number": numero_teste,
            "text": mensagem_teste,
        },
    )

    if resultado is None:
        print("  ✗ Falha ao enviar mensagem de teste.")
        print("  Verifique se o WhatsApp já foi pareado (Etapa 3).")
        return False

    print("  ✓ Mensagem de teste enviada com sucesso!")
    print_json(resultado)
    return True


# =============================================
# Fluxo principal
# =============================================

async def main() -> None:
    """Fluxo principal do setup do WhatsApp."""
    print_separador("SETUP WHATSAPP — TERAPEUTAS AGENT")
    print(f"  Evolution API: {EVOLUTION_API_URL}")
    print(f"  Backend URL:   {FASTAPI_BACKEND_URL}")
    print(f"  Webhook:       {WEBHOOK_ENDPOINT}")

    # Solicita o nome da instância
    nome_instancia = input("\n  Nome da instância (ex: terapeuta-teste): ").strip()
    if not nome_instancia:
        nome_instancia = "terapeuta-teste"
        print(f"  Usando nome padrão: {nome_instancia}")

    async with httpx.AsyncClient() as client:
        # Etapa 1: Criar instância
        sucesso = await etapa_1_criar_instancia(client, nome_instancia)
        if not sucesso:
            print("\n  Erro na Etapa 1. O script vai continuar mesmo assim")
            print("  (a instância pode já existir).")

        # Etapa 2: Configurar webhook
        sucesso = await etapa_2_configurar_webhook(client, nome_instancia)
        if not sucesso:
            print("\n  Erro na Etapa 2. Verifique a instância e tente novamente.")

        # Etapa 3: Gerar QR Code
        sucesso = await etapa_3_gerar_qrcode(client, nome_instancia)
        if not sucesso:
            print("\n  Erro na Etapa 3. Verifique se a instância foi criada.")

        # Etapa 4: Mensagem de teste (opcional, precisa parear primeiro)
        print()
        enviar_teste = input("  Deseja enviar uma mensagem de teste? (s/N): ").strip().lower()
        if enviar_teste == "s":
            numero_teste = input("  Número de teste (ex: 5511999999999): ").strip()
            if numero_teste:
                await etapa_4_enviar_mensagem_teste(client, nome_instancia, numero_teste)
            else:
                print("  Nenhum número informado. Pulando teste.")
        else:
            print("  Pulando envio de mensagem de teste.")

    # Resumo final
    print_separador("SETUP COMPLETO")
    print(f"  Instância:  {nome_instancia}")
    print(f"  Webhook:    {WEBHOOK_ENDPOINT}")
    print()
    print("  Próximos passos:")
    print("  1. Escaneie o QR Code com o WhatsApp do celular")
    print("  2. Aguarde a conexão ser confirmada")
    print("  3. Envie uma mensagem de teste para o número conectado")
    print("  4. Verifique se o webhook recebeu a mensagem no backend")
    print()


if __name__ == "__main__":
    asyncio.run(main())
