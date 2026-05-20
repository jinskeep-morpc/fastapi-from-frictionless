#!/usr/bin/env bash
# Sets up /etc/hosts entries for local hostname routing, then builds and starts the stack.
set -e

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.example to .env and configure it first."
    exit 1
fi

set -o allexport
source .env
set +o allexport

PROJECT_NAME="${PROJECT_NAME:-$(basename "$(pwd)")}"
NGINX_IP="${NGINX_IP:-127.0.1.1}"

add_hosts_entry() {
    local entry="$1"
    if grep -qF "$entry" /etc/hosts 2>/dev/null; then
        echo "  already present: $entry"
    else
        echo "  adding (requires sudo): $entry"
        echo "$entry" | sudo tee -a /etc/hosts > /dev/null
    fi
}

echo "Configuring /etc/hosts..."
add_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.api"
add_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.pgadmin"

echo "Building API image..."
podman-compose build api

echo "Starting services..."
podman-compose up -d

echo ""
echo "Stack is up:"
echo "  API docs: http://${PROJECT_NAME}.api/docs"
echo "  pgAdmin:  http://${PROJECT_NAME}.pgadmin"
echo "  Postgres: ${NGINX_IP}:5432"
