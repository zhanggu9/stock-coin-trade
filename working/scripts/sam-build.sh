#!/usr/bin/env bash
# Lambda/API STEP 5 — 타깃별 디렉터리에 검증·빌드한다.
set -euo pipefail
source "$(dirname "$0")/sam-common.sh"
select_target "${1:-member}"

sam validate --lint --template-file "$TEMPLATE"
sam build --use-container --template-file "$TEMPLATE" --build-dir "$BUILD_DIR"
printf 'Built template: %s\n' "$BUILT_TEMPLATE"
