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
NETWORK_NAME="${PROJECT_NAME}_app_network"

add_hosts_entry() {
    local entry="$1"
    if grep -qF "$entry" /etc/hosts 2>/dev/null; then
        echo "  already present: $entry"
    else
        echo "  adding (requires sudo): $entry"
        echo "$entry" | sudo tee -a /etc/hosts > /dev/null
    fi
}

# Clear a stale bridge that may have been left by a previous failed run.
# podman-compose down does not remove the bridge from the rootless network namespace,
# so a ghost interface with the wrong subnet can silently block DNS on the next start.
clear_stale_bridge() {
    local bridge
    bridge=$(podman network inspect "${NETWORK_NAME}" 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0].get('network_interface',''))" 2>/dev/null || true)
    if [ -n "$bridge" ]; then
        if podman unshare --rootless-netns -- ip link show "$bridge" &>/dev/null; then
            echo "  removing stale bridge $bridge from rootless namespace..."
            podman unshare --rootless-netns -- ip link delete "$bridge" 2>/dev/null || true
        fi
    fi
}

echo "Configuring /etc/hosts..."
add_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.api"
add_hosts_entry "${NGINX_IP} ${PROJECT_NAME}.pgadmin"

echo "Clearing any stale network bridges..."
clear_stale_bridge

echo "Building API image..."
podman-compose build api

echo "Starting services..."
podman-compose up -d

echo ""
echo "Stack is up:"
echo "  API docs: http://${PROJECT_NAME}.api/docs"
echo "  pgAdmin:  http://${PROJECT_NAME}.pgadmin"
