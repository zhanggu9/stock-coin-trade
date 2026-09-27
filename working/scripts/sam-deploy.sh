#!/usr/bin/env bash
# Lambda/API STEP 8 — 타깃별 별도 스택으로 빌드 결과를 배포한다.
set -euo pipefail
source "$(dirname "$0")/sam-common.sh"
select_target "${1:-member}"

"$WORKING_ROOT/scripts/sam-build.sh" "$TARGET"
sam deploy --guided \
  --template-file "$BUILT_TEMPLATE" \
  --stack-name "$STACK_NAME" \
  --config-file "$WORKING_ROOT/template/samconfig.toml" \
  --config-env "$TARGET"

aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output table
