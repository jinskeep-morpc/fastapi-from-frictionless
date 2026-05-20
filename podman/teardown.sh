#!/usr/bin/env bash
# Stops the stack, removes its /etc/hosts entries, and cleans up the network bridge.
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
NETWORK_NAME="${PROJECT_NAME}_app_network"

# Capture the bridge name before podman-compose down removes the network config.
BRIDGE_NAME=$(podman network inspect "${NETWORK_NAME}" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0].get('network_interface',''))" 2>/dev/null || true)

podman-compose down

# podman-compose down removes containers and the network record, but leaves the bridge
# interface in the rootless network namespace. Remove it so the next run starts clean.
if [ -n "$BRIDGE_NAME" ]; then
    if podman unshare --rootless-netns -- ip link show "$BRIDGE_NAME" &>/dev/null; then
        echo "Removing bridge $BRIDGE_NAME from rootless namespace..."
        podman unshare --rootless-netns -- ip link delete "$BRIDGE_NAME" 2>/dev/null || true
    fi
fi

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
