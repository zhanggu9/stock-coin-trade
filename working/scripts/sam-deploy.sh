#!/usr/bin/env bash
# Lambda/API STEP 8 — lambda.env의 EC2 Docker 접속값으로 타깃별 스택을 배포한다.
set -euo pipefail
source "$(dirname "$0")/sam-common.sh"
select_target "${1:-member}"

ENV_FILE="$WORKING_ROOT/env/lambda.env"
[[ -f "$ENV_FILE" ]] || {
  printf '배포 설정 없음: %s\n' "$ENV_FILE" >&2
  printf 'cp %s/env/lambda.env.example %s 후 실제 값을 입력하세요.\n' "$WORKING_ROOT" "$ENV_FILE" >&2
  exit 1
}

# 저장소 사용자가 직접 관리하는 shell 형식 파일이다. URL은 작은따옴표로 감싼다.
# shellcheck disable=SC1090
source "$ENV_FILE"

required=(VPC_SUBNET_IDS)
parameters=()
case "$TARGET" in
  member)
    required+=(LAMBDA_MEMBER_DATABASE_URL JWT_ISSUER JWT_AUDIENCE)
    parameters+=(
      "ParameterKey=DatabaseUrl,ParameterValue=${LAMBDA_MEMBER_DATABASE_URL:-}"
      "ParameterKey=JwtIssuer,ParameterValue=${JWT_ISSUER:-}"
      "ParameterKey=JwtAudience,ParameterValue=${JWT_AUDIENCE:-}"
    ) ;;
  quant)
    required+=(LAMBDA_QUANT_DATABASE_URL)
    parameters+=("ParameterKey=QuantDatabaseUrl,ParameterValue=${LAMBDA_QUANT_DATABASE_URL:-}") ;;
  ohlcv)
    required+=(LAMBDA_OHLCV_DATABASE_URL VPC_ID)
    alb_mode="${LAMBDA_OHLCV_CREATE_ALB:-false}"
    [[ "$alb_mode" == true || "$alb_mode" == false ]] || {
      printf 'LAMBDA_OHLCV_CREATE_ALB 값은 true 또는 false여야 합니다.\n' >&2
      exit 1
    }
    if [[ -n "${LAMBDA_OHLCV_CERTIFICATE_ARN:-}" && "$alb_mode" != true ]]; then
      printf 'HTTPS 인증서를 쓰려면 LAMBDA_OHLCV_CREATE_ALB=true여야 합니다.\n' >&2
      exit 1
    fi
    parameters+=(
      "ParameterKey=OhlcvDatabaseUrl,ParameterValue=${LAMBDA_OHLCV_DATABASE_URL:-}"
      "ParameterKey=VpcId,ParameterValue=${VPC_ID:-}"
      "ParameterKey=CreateAlb,ParameterValue=$alb_mode"
      "ParameterKey=AlbCertificateArn,ParameterValue=${LAMBDA_OHLCV_CERTIFICATE_ARN:-}"
    ) ;;
  session)
    required+=(LAMBDA_REDIS_URL JWT_ISSUER JWT_AUDIENCE)
    parameters+=(
      "ParameterKey=RedisUrl,ParameterValue=${LAMBDA_REDIS_URL:-}"
      "ParameterKey=JwtIssuer,ParameterValue=${JWT_ISSUER:-}"
      "ParameterKey=JwtAudience,ParameterValue=${JWT_AUDIENCE:-}"
    ) ;;
  knowledge)
    required+=(LAMBDA_QDRANT_URL)
    parameters+=("ParameterKey=QdrantUrl,ParameterValue=${LAMBDA_QDRANT_URL:-}")
    [[ -z "${LAMBDA_QDRANT_API_KEY:-}" ]] || parameters+=("ParameterKey=QdrantApiKey,ParameterValue=$LAMBDA_QDRANT_API_KEY") ;;
esac

if [[ "$TARGET" != ohlcv ]]; then
  required+=(VPC_SECURITY_GROUP_IDS)
  parameters+=("ParameterKey=VpcSecurityGroupIds,ParameterValue=${VPC_SECURITY_GROUP_IDS:-}")
fi
parameters+=("ParameterKey=VpcSubnetIds,ParameterValue=${VPC_SUBNET_IDS:-}")

for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { printf 'lambda.env 필수 값 누락: %s\n' "$name" >&2; exit 1; }
  [[ "${!name}" != *CHANGE_ME* && "${!name}" != *EXAMPLE* ]] || {
    printf 'lambda.env 자리표시자를 실제 값으로 바꾸세요: %s\n' "$name" >&2
    exit 1
  }
done

"$WORKING_ROOT/scripts/sam-build.sh" "$TARGET"
sam deploy \
  --template-file "$BUILT_TEMPLATE" \
  --stack-name "$STACK_NAME" \
  --config-file "$WORKING_ROOT/template/samconfig.toml" \
  --config-env "$TARGET" \
  --parameter-overrides "${parameters[@]}" \
  --no-fail-on-empty-changeset

aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output table
