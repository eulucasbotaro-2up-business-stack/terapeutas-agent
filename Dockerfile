# Dockerfile — Terapeutas Agent (FastAPI)
# Funciona local (docker-compose), Railway e Render.com

FROM python:3.12-slim

WORKDIR /app

# Instala dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

EXPOSE 8000

# Comando padrão
# Usa $PORT se disponível (Render/Railway definem), senão 8000
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
