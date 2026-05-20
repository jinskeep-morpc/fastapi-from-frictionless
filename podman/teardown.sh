#!/usr/bin/env bash
# Stops the stack and removes its /etc/hosts entries.
set -e

if [ ! -f .env ]; then
    echo "ERROR: .env not found."
    exit 1
fi

set -o allexport
source .env
set +o allexport

PROJECT_NAME="${PROJECT_NAME:-$(basename "$(pwd)")}"
NGINX_IP="${NGINX_IP:-127.0.1.1}"

podman-compose down

remove_hosts_entry() {
    local entry="$1"
    if grep -qF "$entry" /etc/hosts 2>/dev/null; then
        echo "  removing (requires sudo): $entry"
        sudo sed -i "\|${entry}|d" /etc/hosts
    fi
}

echo "Removing /etc/hosts entries..."
remove_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.api"
remove_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.pgadmin"

echo "Done."
