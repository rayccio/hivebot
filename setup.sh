#!/bin/bash
set -e

# HiveBot Production Installer
# Run from project root.

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ASCII Art Banner
show_banner() {
    echo -e "${PURPLE}"
    echo '╔══════════════════════════════════════════════════════════════╗'
    echo '║                                                              ║'
    echo '║   ██╗  ██╗██╗██╗   ██╗███████╗██████╗  ██████╗ ████████╗     ║'
    echo '║   ██║  ██║██║██║   ██║██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝     ║'
    echo '║   ███████║██║██║   ██║█████╗  ██████╔╝██║   ██║   ██║        ║'
    echo '║   ██╔══██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗██║   ██║   ██║        ║'   
    echo '║   ██║  ██║██║ ╚████╔╝ ███████╗██████╔╝╚██████╔╝   ██║        ║'
    echo '║   ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═════╝  ╚═════╝    ╚═╝        ║'
    echo '║                                                              ║'
    echo '║                   Enterprise Hive Intelligence               ║'
    echo '║                      Production Orchestrator                 ║'
    echo '║                                                              ║'
    echo '╚══════════════════════════════════════════════════════════════╝'
    echo -e "${NC}"
}

# Small banner for final status
show_small_banner() {
    echo -e "${CYAN}"
    echo '   ██╗  ██╗██╗██╗   ██╗███████╗██████╗  ██████╗ ████████╗'
    echo '   ██║  ██║██║██║   ██║██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝'
    echo '   ███████║██║██║   ██║█████╗  ██████╔╝██║   ██║   ██║   '
    echo '   ██╔══██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗██║   ██║   ██║   '
    echo '   ██║  ██║██║ ╚████╔╝ ███████╗██████╔╝╚██████╔╝   ██║   '
    echo '   ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═════╝  ╚═════╝    ╚═╝   '
    echo -e "${NC}"
}

# Auto‑elevate to root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}🔐 This script requires root privileges. Re‑executing with sudo...${NC}"
    exec sudo "$0" "$@"
fi

show_banner

echo -e "${GREEN}🚀 HiveBot Production Installer${NC}"
echo "----------------------------------------"

# --- 1. Check prerequisites ---
echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker not installed.${NC}" >&2; exit 1; }

COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}   ✅ Docker Compose v2 (plugin) found${NC}"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    echo -e "${GREEN}   ✅ Docker Compose v1 (standalone) found${NC}"
else
    echo -e "${RED}❌ Docker Compose is required but not installed. Aborting.${NC}" >&2
    exit 1
fi

# --- 2. Detect public IP using multiple services ---
echo -e "${YELLOW}🌍 Detecting public IP address...${NC}"
PUBLIC_IP=""
if command -v curl >/dev/null 2>&1; then
    for service in "ifconfig.me" "icanhazip.com" "ipecho.net/plain" "api.ipify.org"; do
        PUBLIC_IP=$(curl -s -4 "$service" 2>/dev/null || echo "")
        if [ -n "$PUBLIC_IP" ]; then
            break
        fi
    done
elif command -v wget >/dev/null 2>&1; then
    for service in "ifconfig.me" "icanhazip.com" "ipecho.net/plain" "api.ipify.org"; do
        PUBLIC_IP=$(wget -qO- -4 "$service" 2>/dev/null || echo "")
        if [ -n "$PUBLIC_IP" ]; then
            break
        fi
    done
else
    PUBLIC_IP=$(hostname -I | awk '{print $1}')
fi

if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP="localhost"
    echo -e "${YELLOW}⚠️  Could not detect public IP. Falling back to 'localhost'.${NC}"
else
    echo -e "${GREEN}   ✅ Public IP: $PUBLIC_IP${NC}"
fi

# Format IPv6 for URLs (brackets)
if [[ "$PUBLIC_IP" == *":"* ]]; then
    URL_IP="[${PUBLIC_IP}]"
else
    URL_IP="${PUBLIC_IP}"
fi

# --- 3. Create required directories ---
echo -e "${YELLOW}📁 Ensuring directory structure...${NC}"
mkdir -p ./agents
mkdir -p ./logs
mkdir -p ./data
mkdir -p ./data/artifacts
mkdir -p ./secrets
mkdir -p ./global_files
mkdir -p ./layers

# --- 4. Validate and repair master key (hex only, length 64) ---
validate_master_key() {
    local key_file="$1"
    local content=$(tr -d '\n\r' < "$key_file")
    if [[ ! "$content" =~ ^[0-9a-fA-F]{64}$ ]]; then
        return 1
    fi
    return 0
}

if [ -f ./secrets/master.key ]; then
    echo -e "${YELLOW}🔑 Validating existing master key...${NC}"
    if validate_master_key ./secrets/master.key; then
        echo -e "${GREEN}   ✅ Master key is valid.${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Master key is corrupted (invalid hex or wrong length). Regenerating...${NC}"
        mv ./secrets/master.key "./secrets/master.key.corrupted.$(date +%s)"
        openssl rand -hex 32 > ./secrets/master.key
        chmod 600 ./secrets/master.key
        echo -e "${GREEN}   ✅ New master key generated.${NC}"
    fi
else
    echo -e "${YELLOW}🔑 Generating new master key...${NC}"
    openssl rand -hex 32 > ./secrets/master.key
    chmod 600 ./secrets/master.key
    echo -e "${GREEN}   ✅ Master key generated.${NC}"
fi

# --- 5. Generate .env file with correct VITE_API_URL and CORS origins ---
echo -e "${YELLOW}🔧 Generating .env configuration...${NC}"
cat > .env <<EOF
# HiveBot Environment Configuration
ENVIRONMENT=production
DEBUG=false

# Backend CORS: comma‑separated list of allowed origins
BACKEND_CORS_ORIGINS=http://localhost,http://localhost:3000,http://${PUBLIC_IP},http://${PUBLIC_IP}:80,http://${URL_IP}:8080

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_USER=hivebot
POSTGRES_PASSWORD=hivebot
POSTGRES_DB=hivebot

# Docker
DOCKER_NETWORK=hivebot_network

# Frontend API URL (injected at build time) – base backend URL, no path
VITE_API_URL=http://${URL_IP}:8000

# Auto‑spawn agents by default
AUTO_SPAWN=true
EOF

# Copy .env to frontend build context (so VITE_API_URL is embedded)
cp .env frontend/.env

# --- 6. Clean up old Docker state (before building images) ---
echo -e "${YELLOW}🧹 Cleaning up old Docker state...${NC}"
$COMPOSE_CMD down --rmi local --volumes --remove-orphans 2>/dev/null || true
docker system prune -f --volumes

# --- 7. Pre‑build agent image (do NOT run the container) ---
echo -e "${YELLOW}🐳 Pre‑building agent image...${NC}"
$COMPOSE_CMD build agent-builder || {
    echo -e "${RED}❌ Failed to build agent image.${NC}"
    exit 1
}

# --- 8. Pre‑build skill-runner image ---
echo -e "${YELLOW}🐳 Pre‑building skill-runner image...${NC}"
$COMPOSE_CMD build skill-runner-builder || {
    echo -e "${RED}❌ Failed to build skill-runner image.${NC}"
    exit 1
}

# --- 9. Secrets vault initialisation (crash‑proof) ---
echo -e "${YELLOW}🔐 Initializing secure secrets vault...${NC}"
echo -e "${YELLOW}   You will be prompted for the public URL (if any). Press Enter to skip.${NC}"

docker run --rm -i -v "$(pwd)/secrets:/secrets" python:3.11-slim bash -c "
set -e
pip install cryptography > /dev/null 2>&1
python - <<'INNER_EOF'
import os
import json
import sys
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

secrets_path = '/secrets/secrets.enc'
master_key_path = '/secrets/master.key'

# Read master key (hex string)
with open(master_key_path, 'r') as f:
    hex_key = f.read().strip()
    master_key = bytes.fromhex(hex_key)

secrets = {}
if os.path.exists(secrets_path):
    try:
        with open(secrets_path, 'rb') as f:
            payload = f.read()
        nonce = payload[:12]
        tag = payload[-16:]
        ciphertext = payload[12:-16]
        cipher = Cipher(algorithms.AES(master_key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        secrets = json.loads(plaintext.decode('utf-8'))
        print('✅ Existing secrets loaded.')
    except (InvalidTag, Exception) as e:
        print(f'⚠️  Could not decrypt existing secrets ({e}). Backing up and starting fresh.')
        backup_name = f'{secrets_path}.corrupted.{int(time.time())}'
        os.rename(secrets_path, backup_name)
        print(f'   Backup saved to: {backup_name}')
        secrets = {}

def get_input(prompt):
    try:
        print(prompt, end='', flush=True)
        value = sys.stdin.readline().strip()
        return value or None
    except:
        return None

# Ask for public URL (for webhooks)
public_ip = '$PUBLIC_IP'
default_url = f'http://{public_ip}:8000' if public_ip != 'localhost' else None
if default_url:
    prompt = f'Public URL (for webhooks) [default: {default_url}]: '
else:
    prompt = 'Public URL (for webhooks, optional): '
entered_url = get_input(prompt)
if entered_url:
    secrets['PUBLIC_URL'] = entered_url
elif default_url:
    secrets['PUBLIC_URL'] = default_url
    print(f'   Using detected public IP: {default_url}')
else:
    secrets['PUBLIC_URL'] = None

# Generate internal API key (used by agents to authenticate with orchestrator)
if 'INTERNAL_API_KEY' not in secrets:
    secrets['INTERNAL_API_KEY'] = os.urandom(32).hex()
    print(f\"🔑 Generated Internal API Key: {secrets['INTERNAL_API_KEY']}\")
    print('   This key is used by agents to authenticate with the orchestrator.')
else:
    print('🔑 Internal API key already exists.')

# Encrypt and save
nonce = os.urandom(12)
cipher = Cipher(algorithms.AES(master_key), modes.GCM(nonce), backend=default_backend())
encryptor = cipher.encryptor()
plaintext = json.dumps(secrets).encode('utf-8')
ciphertext = encryptor.update(plaintext) + encryptor.finalize()
payload = nonce + ciphertext + encryptor.tag

with open(secrets_path, 'wb') as f:
    f.write(payload)
os.chmod(secrets_path, 0o600)
print('✅ Secrets encrypted and saved.')
INNER_EOF
"

# --- 9b. Extract INTERNAL_API_KEY from secrets and add to .env (for worker) ---
echo -e "${YELLOW}🔑 Extracting INTERNAL_API_KEY for worker...${NC}"
INTERNAL_KEY=$(docker run --rm -v "$(pwd)/secrets:/secrets" python:3.11-slim bash -c "
pip install cryptography > /dev/null 2>&1
python - <<'EXTRACT_EOF'
import os, json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

secrets_path = '/secrets/secrets.enc'
master_key_path = '/secrets/master.key'

with open(master_key_path, 'r') as f:
    hex_key = f.read().strip()
    master_key = bytes.fromhex(hex_key)

with open(secrets_path, 'rb') as f:
    payload = f.read()

nonce = payload[:12]
tag = payload[-16:]
ciphertext = payload[12:-16]
cipher = Cipher(algorithms.AES(master_key), modes.GCM(nonce, tag), backend=default_backend())
decryptor = cipher.decryptor()
plaintext = decryptor.update(ciphertext) + decryptor.finalize()
secrets = json.loads(plaintext.decode('utf-8'))
print(secrets.get('INTERNAL_API_KEY', ''))
EXTRACT_EOF
")
if [ -n "$INTERNAL_KEY" ]; then
    echo "INTERNAL_API_KEY=$INTERNAL_KEY" >> .env
    echo -e "${GREEN}   ✅ INTERNAL_API_KEY added to .env${NC}"
else
    echo -e "${RED}   ❌ Failed to extract INTERNAL_API_KEY${NC}"
fi

# --- 9c. Create bridges.env file for bridge workers ---
echo -e "${YELLOW}🔧 Creating bridges.env for bridge workers...${NC}"

docker run --rm -v "$(pwd)/secrets:/secrets" python:3.11-slim bash -c "
pip install cryptography > /dev/null 2>&1
python - <<'EXTRACT_EOF'
import os
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

secrets_path = '/secrets/secrets.enc'
master_key_path = '/secrets/master.key'

with open(master_key_path, 'r') as f:
    hex_key = f.read().strip()
    master_key = bytes.fromhex(hex_key)

with open(secrets_path, 'rb') as f:
    payload = f.read()

nonce = payload[:12]
tag = payload[-16:]
ciphertext = payload[12:-16]
cipher = Cipher(algorithms.AES(master_key), modes.GCM(nonce, tag), backend=default_backend())
decryptor = cipher.decryptor()
plaintext = decryptor.update(ciphertext) + decryptor.finalize()
secrets = json.loads(plaintext.decode('utf-8'))

internal_key = secrets.get('INTERNAL_API_KEY', '')
public_url = secrets.get('PUBLIC_URL', '')

print(f'INTERNAL_API_KEY={internal_key}')
print(f'PUBLIC_URL={public_url}')
EXTRACT_EOF
" > ./bridges.env

chmod 600 ./bridges.env

# --- 10. Build base image first, then the rest (with no-cache to ensure freshness) ---
echo -e "${YELLOW}🐳 Building base image (no-cache)...${NC}"
$COMPOSE_CMD build --no-cache bridge-base

# Explicitly remove any old bridge-telegram image to force a fresh build
echo -e "${YELLOW}🧹 Removing old bridge-telegram image if any...${NC}"
docker rmi $(docker images -q hivebot-bridge-telegram) 2>/dev/null || true

echo -e "${YELLOW}🐳 Building bridge-telegram image with no-cache...${NC}"
$COMPOSE_CMD build --no-cache bridge-telegram

echo -e "${YELLOW}🐳 Building remaining Docker images (with no-cache)...${NC}"
$COMPOSE_CMD build --no-cache

# --- 11. Start services ---
echo -e "${YELLOW}🐳 Starting Docker services...${NC}"
$COMPOSE_CMD up -d

# --- 12. Wait for backend to be healthy ---
echo -e "${YELLOW}⏳ Waiting for backend to become healthy...${NC}"
for i in {1..30}; do
    if docker inspect --format='{{json .State.Health.Status}}' hivebot_backend 2>/dev/null | grep -q '"healthy"'; then
        echo -e "${GREEN}   ✅ Backend is healthy.${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# --- 13. Run database migrations (including new tables) ---
echo -e "${YELLOW}📦 Running database migrations...${NC}"
docker exec hivebot_backend python /app/scripts/create_goal_tables.py || echo -e "${RED}❌ Goal migration failed, but continuing...${NC}"
docker exec hivebot_backend python /app/scripts/create_economy_tables.py || echo -e "${RED}❌ Economy migration failed, but continuing...${NC}"
docker exec hivebot_backend python /app/scripts/create_execution_logs_table.py || echo -e "${RED}❌ Execution logs migration failed, but continuing...${NC}"
docker exec hivebot_backend python /app/scripts/seed_eval_tasks.py || echo -e "${RED}❌ Seeding failed, but continuing...${NC}"

# Phase 0 migration scripts
echo -e "${YELLOW}🔄 Running Phase 0 migrations...${NC}"
docker exec hivebot_backend python /app/scripts/create_layer_tables.py || echo -e "${RED}❌ Layer tables creation failed, but continuing...${NC}"
docker exec hivebot_backend python /app/scripts/seed_core_layer.py || echo -e "${RED}❌ Core layer seeding failed, but continuing...${NC}"
docker exec hivebot_backend python /app/scripts/update_tasks_artifacts.py || echo -e "${RED}❌ Task/artifact update failed, but continuing...${NC}"

# Phase 3 migration: add custom_planner_class column
echo -e "${YELLOW}🔄 Adding custom_planner_class to planner_templates...${NC}"
docker exec hivebot_backend python /app/scripts/add_custom_planner_class.py || echo -e "${RED}❌ Adding custom_planner_class failed, but continuing...${NC}"

# Existing migrations
echo -e "${YELLOW}🔄 Migrating hives to include agentIds...${NC}"
docker exec hivebot_backend python /app/scripts/migrate_hives_add_agent_ids.py || echo -e "${RED}❌ Hive migration failed, but continuing...${NC}"
echo -e "${YELLOW}🔄 Converting JSON columns to JSONB...${NC}"
docker exec hivebot_backend python /app/scripts/convert_json_to_jsonb.py || echo -e "${RED}❌ JSONB conversion failed, but continuing...${NC}"

# Phase 5 migration: add layer_id to tasks
echo -e "${YELLOW}🔄 Adding layerId to tasks...${NC}"
docker exec hivebot_backend python /app/scripts/add_layer_id_to_tasks.py || echo -e "${RED}❌ Adding layerId to tasks failed, but continuing...${NC}"

# --- 14. Install CLI wrapper (Phase 2) ---
echo -e "${YELLOW}🛠️ Installing HiveBot CLI...${NC}"
if [ -f ./hivebot ]; then
    cp ./hivebot /usr/local/bin/hivebot
    chmod +x /usr/local/bin/hivebot
    echo -e "${GREEN}   ✅ CLI installed as 'hivebot'${NC}"
else
    echo -e "${YELLOW}   ⚠️  hivebot wrapper not found, skipping install${NC}"
fi

# --- 15. Final status ---
clear
show_small_banner
echo -e "${GREEN}✅ HiveBot Phase 5 complete!${NC}"
echo -e "   Frontend: http://${URL_IP}:8080"
echo -e "   Backend API: http://${URL_IP}:8000"
echo -e "   Secrets: $(pwd)/secrets"
echo -e "   Bridges env: $(pwd)/bridges.env"
echo -e "   Layers directory: $(pwd)/layers"
echo -e "   CLI: hivebot [install|enable|disable|list|...]"
echo -e "${YELLOW}📘 Ensure ports 8080 and 8000 are open in your firewall.${NC}"
