# Dockerfile — Terapeutas Agent (FastAPI)
# Funciona local (docker-compose), Railway e Render.com

FROM python:3.12-slim

WORKDIR /app

# build-essential necessário para compilar pyswisseph (extensão C do kerykeion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

EXPOSE 8000

# Comando padrão
# Usa $PORT se disponível (Render/Railway definem), senão 8000
# --workers 1 para Railway (single container, sem conflito de estado em memória)
# --timeout-keep-alive 65 para suportar webhooks Meta (timeout padrão deles é 60s)
CMD uvicorn src.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --timeout-keep-alive 65 \
    --log-level info \
    --access-log
