#!/bin/sh
set -e

echo "=== Custom entrypoint: sobrescrevendo .env ==="

# Sobrescreve o .env interno da Evolution API com as variaveis do Railway
cat > /evolution/.env << EOF
SERVER_TYPE=http
SERVER_PORT=${PORT:-8080}
AUTHENTICATION_TYPE=apikey
AUTHENTICATION_API_KEY=${AUTHENTICATION_API_KEY:-change-me}
DATABASE_ENABLED=${DATABASE_ENABLED:-true}
DATABASE_PROVIDER=${DATABASE_PROVIDER:-postgresql}
DATABASE_CONNECTION_URI=${DATABASE_CONNECTION_URI}
DATABASE_SAVE_DATA_INSTANCE=${DATABASE_SAVE_DATA_INSTANCE:-true}
DATABASE_SAVE_DATA_NEW_MESSAGE=${DATABASE_SAVE_DATA_NEW_MESSAGE:-false}
DATABASE_SAVE_MESSAGE_UPDATE=${DATABASE_SAVE_MESSAGE_UPDATE:-false}
DATABASE_SAVE_DATA_CONTACTS=${DATABASE_SAVE_DATA_CONTACTS:-false}
DATABASE_SAVE_DATA_CHATS=${DATABASE_SAVE_DATA_CHATS:-false}
DATABASE_SAVE_DATA_LABELS=${DATABASE_SAVE_DATA_LABELS:-false}
DATABASE_SAVE_DATA_HISTORIC=${DATABASE_SAVE_DATA_HISTORIC:-false}
LOG_LEVEL=${LOG_LEVEL:-WARN}
CORS_ORIGIN=*
EOF

echo "=== .env escrito com sucesso ==="
cat /evolution/.env
echo "================================"

# Executa o deploy_database e inicia o app
cd /evolution
. ./Docker/scripts/deploy_database.sh
exec npm run start:prod
