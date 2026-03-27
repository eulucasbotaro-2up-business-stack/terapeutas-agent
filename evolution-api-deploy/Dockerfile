# Dockerfile — Evolution API v2 para deploy no Railway
# WORKAROUND: A imagem v2.2.3 ignora env vars externas (issue #1474)
# Solucao: sobrescrever o .env interno via ENTRYPOINT customizado

FROM atendai/evolution-api:v2.2.3

EXPOSE 8080
WORKDIR /evolution

# Cria script de entrypoint que sobrescreve .env antes de tudo
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
