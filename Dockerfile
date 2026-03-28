# Dockerfile — Terapeutas Agent (FastAPI)
# Funciona local (docker-compose), Railway e Render.com

FROM python:3.12-slim

WORKDIR /app

# Backend matplotlib via ENV — garante Agg mesmo se alguma lib importar pyplot
# antes do matplotlib.use("Agg") no código (ex: lib de terceiros)
ENV MPLBACKEND=Agg

# Diretório gravável para cache do matplotlib — /root pode ser read-only em containers
ENV MPLCONFIGDIR=/tmp/matplotlib_cache

# build-essential necessário para compilar pyswisseph (extensão C do kerykeion)
# zlib1g + libjpeg: evita mismatch de versão ao salvar PNG via Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    zlib1g \
    libjpeg62-turbo \
    fonts-dejavu-core \
    fontconfig \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório de cache do matplotlib com permissão garantida
RUN mkdir -p /tmp/matplotlib_cache

# Instala dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-builda o font cache do matplotlib em tempo de build (não em cold start)
# Evita falha silenciosa na primeira geração de imagem em container novo
RUN python -c "import matplotlib; matplotlib.font_manager._load_fontmanager(try_read_cache=False)" || true

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
