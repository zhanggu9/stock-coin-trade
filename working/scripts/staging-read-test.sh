#!/usr/bin/env bash
# 비로그인 공개 DB 읽기 확인. 쓰기 없이 PostgreSQL·Qdrant 응답과 HTTP 상태를 본다.
set -euo pipefail
ST_API_BASE="${ST_API_BASE:-https://st.edumgt.co.kr}"

curl --fail-with-body --show-error "$ST_API_BASE/api/quant/overview"
curl --fail-with-body --show-error "$ST_API_BASE/api/ohlcv-db/summary"
curl --fail-with-body --show-error "$ST_API_BASE/api/stocks/ai/qdrant/stats"
