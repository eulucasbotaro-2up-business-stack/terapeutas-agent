# Dockerfile — Evolution API v2 para deploy no Render.com
# Usa a imagem oficial da Evolution API como base
# O Render.com builda este Dockerfile a partir do repo GitHub

FROM atendai/evolution-api:v2.2.3

# --- Configuracoes da Evolution API v2 ---

# Servidor
ENV SERVER_TYPE=http

# Autenticacao — API Key para proteger a instancia
ENV AUTHENTICATION_TYPE=apikey

# Banco de dados — desabilitado (usa SQLite interno por padrao)
ENV DATABASE_ENABLED=false

# Logs
ENV LOG_LEVEL=WARN

# CORS
ENV CORS_ORIGIN=*

EXPOSE 8080

# IMPORTANTE: O Render injeta $PORT dinamicamente.
# A Evolution API usa SERVER_PORT para definir em qual porta escutar.
# Este CMD sincroniza o PORT do Render com SERVER_PORT da Evolution API,
# e depois executa o entrypoint original da imagem.
WORKDIR /evolution
CMD ["sh", "-c", "export SERVER_PORT=${PORT:-8080} && . ./Docker/scripts/deploy_database.sh && npm run start:prod"]
