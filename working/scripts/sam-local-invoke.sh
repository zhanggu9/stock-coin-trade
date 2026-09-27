#!/usr/bin/env bash
# Lambda/API STEP 7 — 타깃 이벤트를 Lambda 컨테이너로 단일 호출한다.
set -euo pipefail
source "$(dirname "$0")/sam-common.sh"
select_target "${1:-member}"
require_docker_network

[[ -f "$BUILT_TEMPLATE" ]] || "$WORKING_ROOT/scripts/sam-build.sh" "$TARGET"
sam local invoke "$FUNCTION_ID" \
  --template-file "$BUILT_TEMPLATE" \
  --event "$EVENT" \
  --env-vars "$ENV_JSON" \
  --docker-network "$DOCKER_NETWORK"
