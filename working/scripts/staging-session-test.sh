#!/usr/bin/env bash
# Redis 세션 백엔드가 배포된 뒤 MariaDB 로그인과 Redis 세션을 함께 확인한다.
set -euo pipefail
ST_API_BASE="${ST_API_BASE:-https://st.edumgt.co.kr}"
ST_COOKIE_JAR="$(mktemp)"
trap 'rm -f "$ST_COOKIE_JAR"' EXIT
read -r -p "Demo email: " ST_EMAIL
read -r -s -p "Demo password: " ST_PASSWORD; printf '\n'
ST_BODY="$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' "$ST_EMAIL" "$ST_PASSWORD")"

curl --fail-with-body --show-error \
  -c "$ST_COOKIE_JAR" \
  -H 'content-type: application/json' \
  --data "$ST_BODY" \
  "$ST_API_BASE/api/member/login"

curl --fail-with-body --show-error -b "$ST_COOKIE_JAR" "$ST_API_BASE/api/member/me"
