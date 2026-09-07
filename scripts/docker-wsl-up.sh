#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose v2 is required" >&2
  exit 1
fi

if [[ ! -r /proc/version ]] || ! grep -qi microsoft /proc/version; then
  echo "This launcher is intended for Docker Engine running inside WSL." >&2
  echo "Use 'docker compose up --build' on ordinary Linux/Docker Desktop setups." >&2
  exit 1
fi

if [[ -n "${PRODAGENTIC_WSL_IP:-}" ]]; then
  WSL_IP="${PRODAGENTIC_WSL_IP}"
else
  WSL_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
fi

is_private_ipv4() {
  local ip="$1"
  local a b c d
  IFS=. read -r a b c d <<<"$ip"

  [[ "$a" =~ ^[0-9]+$ && "$b" =~ ^[0-9]+$ && "$c" =~ ^[0-9]+$ && "$d" =~ ^[0-9]+$ ]] || return 1
  (( a >= 0 && a <= 255 && b >= 0 && b <= 255 && c >= 0 && c <= 255 && d >= 0 && d <= 255 )) || return 1

  (( a == 10 )) && return 0
  (( a == 172 && b >= 16 && b <= 31 )) && return 0
  (( a == 192 && b == 168 )) && return 0
  return 1
}

if [[ -z "$WSL_IP" ]] || ! is_private_ipv4 "$WSL_IP"; then
  echo "Refusing WSL fallback: expected an RFC1918 IPv4 address, got '${WSL_IP:-<empty>}'" >&2
  echo "Override only with a private WSL address: PRODAGENTIC_WSL_IP=<ip> bash scripts/docker-wsl-up.sh" >&2
  exit 1
fi

export PRODAGENTIC_WEB_BIND_HOST="$WSL_IP"
export NEXT_PUBLIC_API_URL="http://$WSL_IP:8000"
export PRODAGENTIC_ALLOW_PRIVATE_HTTP_API="true"
export CORS_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://$WSL_IP:3000"
export FRONTEND_URL="http://$WSL_IP:3000"
export LINKEDIN_REDIRECT_URI="http://$WSL_IP:8000/api/integrations/linkedin/callback"

echo "prodAgentic WSL NAT mode"
echo "  WSL IP:   $WSL_IP"
echo "  Frontend: http://$WSL_IP:3000"
echo "  Backend:  http://$WSL_IP:8000"
echo "  Mongo:    127.0.0.1:27017 only"

docker compose up -d --build --remove-orphans
docker compose ps

echo
echo "Open this URL from Windows:"
echo "http://$WSL_IP:3000"
