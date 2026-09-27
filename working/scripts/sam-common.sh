#!/usr/bin/env bash

WORKING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

select_target() {
  TARGET="${1:-member}"
  case "$TARGET" in
    member|quant|ohlcv|session|knowledge) ;;
    *)
      printf '지원 타깃: member | quant | ohlcv | session | knowledge\n' >&2
      return 2
      ;;
  esac

  TEMPLATE="$WORKING_ROOT/template/template-${TARGET}.yaml"
  BUILD_DIR="$WORKING_ROOT/.aws-sam/${TARGET}"
  BUILT_TEMPLATE="$BUILD_DIR/template.yaml"
  EVENT="$WORKING_ROOT/lambda/${TARGET}/event.json"
  ENV_JSON="$WORKING_ROOT/env/local-env.generated.json"
  FUNCTION_ID="DatabasePracticeFunction"
  STACK_NAME="stock-coin-trade-${TARGET}-practice"

  case "$TARGET" in
    ohlcv) DOCKER_NETWORK="${SAM_DOCKER_NETWORK:-postgresql_default}" ;;
    *) DOCKER_NETWORK="${SAM_DOCKER_NETWORK:-stock-coin-trade_internal}" ;;
  esac
}

require_docker_network() {
  if ! docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1; then
    printf 'Docker network not found: %s\n' "$DOCKER_NETWORK" >&2
    printf 'Compose DB를 먼저 실행하거나 SAM_DOCKER_NETWORK를 지정하세요.\n' >&2
    return 1
  fi
}
