#!/usr/bin/env bash
# graft-target.sh — sam init 으로 만든 프로젝트에 working/lambda/<target> 소스를 이식한다.
#
#   사용법: working/scripts/graft-target.sh <target> <project-dir>
#   예시:   working/scripts/graft-target.sh quant sam-app-02
#
# SAM 활용 2 STEP 2 의 "Hello World → working/ 소스" 대조표 다섯 항목을 한 번에 수행한다.
#   1) lambda/<target>/ 의 핸들러·서비스·secret_config·requirements 를 <project>/<target>/ 로 복사
#   2) lambda/<target>/event.json 을 <project>/events/<target>.json 으로 복사
#   3) template.yaml 에 함수 리소스(Handler·CodeUri·환경변수·HttpApi 경로)를 생성 또는 추가
#   4) env.json 에 함수 논리 ID 별 로컬 환경변수(자리표시자)를 생성 또는 병합
#   5) 처음 이식할 때만 hello_world/·tests/ 를 제거 (다시 실행하면 기존 함수는 유지)
# 실제 계정·비밀번호는 env.json 의 USER:PASSWORD 를 직접 바꾼다. env.json 은 커밋하지 않는다.
set -euo pipefail

TARGET="${1:-}"; PROJECT="${2:-}"
[[ -n "$TARGET" && -n "$PROJECT" ]] || { sed -n 2,5p "$0" | sed 's/^# \{0,1\}//'; exit 2; }

WORKING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$WORKING_ROOT/.." && pwd)"
[[ "$PROJECT" = /* ]] || PROJECT="$REPO_ROOT/$PROJECT"
SRC="$WORKING_ROOT/lambda/$TARGET"

# ── 타깃별 정의: 함수 논리 ID | 핸들러 모듈 | 경로 | 메서드 | 로컬 환경변수(공백 구분, KEY=값) ──
case "$TARGET" in
  quant)     FN=QuantPricesFunction;      MOD=lambda_quant;            PATH_="/quant/prices";              METHOD=GET
             ENVS="QUANT_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@postgres:5432/quant_research"
             ARN_ENV=QUANT_SECRET_ARN ;;
  member)    FN=MemberFunction;           MOD=lambda_member;           PATH_="/members/{member_id}";       METHOD=GET
             ENVS="DATABASE_URL=mysql+pymysql://USER:PASSWORD@mariadb:3306/mockinv"
             ARN_ENV=DATABASE_SECRET_ARN ;;
  ohlcv)     FN=OhlcvSummaryFunction;     MOD=lambda_ohlcv_summary;    PATH_="/ohlcv/summary";             METHOD=GET
             ENVS="OHLCV_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@pg-stock:5432/admin"
             ARN_ENV=OHLCV_SECRET_ARN ;;
  session)   FN=SessionCheckFunction;     MOD=lambda_session_check;    PATH_="/internal/session-check";    METHOD=GET
             ENVS="REDIS_URL=redis://redis:6379/0 REDIS_SESSION_KEY_PREFIX=stock-coin-trade:session:"
             ARN_ENV=REDIS_SECRET_ARN ;;
  knowledge) FN=KnowledgeSearchFunction;  MOD=lambda_knowledge_search; PATH_="/knowledge/search";          METHOD=POST
             ENVS="QDRANT_URL=http://qdrant:6333 QDRANT_API_KEY=LOCAL_DEV_NO_AUTH QDRANT_COLLECTION=market_knowledge"
             ARN_ENV=QDRANT_SECRET_ARN ;;
  *) printf '지원 타깃: quant | member | ohlcv | session | knowledge\n' >&2; exit 2 ;;
esac

[[ -d "$SRC" ]]      || { printf '소스 폴더 없음: %s\n' "$SRC" >&2; exit 1; }
[[ -d "$PROJECT" ]]  || { printf '프로젝트 폴더 없음: %s  (먼저 sam init --name %s ...)\n' "$PROJECT" "$(basename "$PROJECT")" >&2; exit 1; }
[[ -f "$PROJECT/template.yaml" ]] || { printf 'template.yaml 없음: %s 는 sam init 프로젝트가 아닙니다\n' "$PROJECT" >&2; exit 1; }

cd "$PROJECT"
printf '▶ 프로젝트: %s\n▶ 타깃    : %s  (함수 %s, %s %s)\n' "$PROJECT" "$TARGET" "$FN" "$METHOD" "$PATH_"

# 1) 코드 복사
mkdir -p "$TARGET" events
for f in "$SRC"/*.py "$SRC"/requirements.txt; do cp "$f" "$TARGET/"; done
printf '  [1] 코드 복사      : %s/{%s}\n' "$TARGET" "$(ls "$TARGET" | tr '\n' ',' | sed 's/,$//')"

# 2) 이벤트 복사
cp "$SRC/event.json" "events/$TARGET.json"
printf '  [2] 이벤트 복사    : events/%s.json\n' "$TARGET"

# 3) template.yaml — 처음이면 전체 생성, 이미 이식된 프로젝트면 함수 블록만 추가
ENV_YAML=""
for kv in $ENVS; do ENV_YAML+="          ${kv%%=*}: ''"$'\n'; done
FUNC_BLOCK="  $FN:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: $TARGET/                       # working/lambda/$TARGET 에서 복사
      Handler: $MOD.lambda_handler
      Runtime: python3.12
      Architectures: [x86_64]
      Environment:
        Variables:
          $ARN_ENV: ''                        # AWS 배포 시 Secret ARN 입력
$ENV_YAML          # ↑ 로컬 전용: env.json 이 덮어씀 (템플릿에 선언돼야 sam local 이 전달함)
      Events:
        Api:
          Type: HttpApi
          Properties:
            Path: $PATH_
            Method: $METHOD
"
if ! grep -q '^# graft-target' template.yaml; then
  cat > template.yaml <<YAML
# graft-target: working/scripts/graft-target.sh 가 생성한 템플릿 (재실행 시 함수만 추가됨)
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: $(basename "$PROJECT") — working/lambda 소스를 이식한 로컬 실습 템플릿

Globals:
  Function:
    Timeout: 15
    MemorySize: 512

Resources:
$FUNC_BLOCK
Outputs:
  ApiUrl:
    Value: !Sub 'https://\${ServerlessHttpApi}.execute-api.\${AWS::Region}.\${AWS::URLSuffix}'
YAML
  rm -rf hello_world tests
  printf '  [3] template.yaml  : 새로 생성 (hello_world/, tests/ 제거)\n'
elif grep -q "^  $FN:" template.yaml; then
  printf '  [3] template.yaml  : %s 이미 있음 → 그대로 둠\n' "$FN"
else
  python3 - "$FN" <<PY
import sys, pathlib
p = pathlib.Path('template.yaml'); s = p.read_text()
block = '''$FUNC_BLOCK'''
i = s.index('\nOutputs:')
p.write_text(s[:i].rstrip('\n') + '\n\n' + block.rstrip('\n') + '\n' + s[i:])
PY
  printf '  [3] template.yaml  : %s 함수 블록 추가\n' "$FN"
fi

# 4) env.json — 함수 논리 ID 별로 병합
python3 - "$FN" $ENVS <<'PY'
import sys, json, pathlib
fn, kvs = sys.argv[1], sys.argv[2:]
p = pathlib.Path('env.json')
data = json.loads(p.read_text()) if p.exists() else {}
data.setdefault(fn, {})
for kv in kvs:
    k, v = kv.split('=', 1)
    data[fn].setdefault(k, v)
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
print(f"  [4] env.json       : {fn} → {', '.join(k.split('=')[0] for k in kvs)}  (USER:PASSWORD 를 실제 값으로 바꾸세요)")
PY

# 5) 다음 단계 안내
cat <<NEXT
  [5] 완료. 다음 단계:
      cd $PROJECT
      sam validate --lint
      sam build --use-container
      sam local invoke $FN --event events/$TARGET.json --env-vars env.json --docker-network stock-coin-trade_internal
NEXT
