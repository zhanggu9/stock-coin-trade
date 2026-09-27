#!/usr/bin/env bash
# Lambda/API STEP 7 — API Gateway 경로를 로컬 HTTP 서버로 검증한다.
set -euo pipefail
source "$(dirname "$0")/sam-common.sh"
select_target "${1:-member}"
PORT="${2:-3001}"
require_docker_network

[[ "$PORT" =~ ^[0-9]+$ ]] || { printf 'port must be numeric\n' >&2; exit 2; }
[[ -f "$BUILT_TEMPLATE" ]] || "$WORKING_ROOT/scripts/sam-build.sh" "$TARGET"

printf 'Target=%s URL=http://127.0.0.1:%s\n' "$TARGET" "$PORT"
sam local start-api \
  --template-file "$BUILT_TEMPLATE" \
  --env-vars "$ENV_JSON" \
  --docker-network "$DOCKER_NETWORK" \
  --port "$PORT"
