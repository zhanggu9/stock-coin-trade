#!/usr/bin/env bash
# 저장소 루트 .env를 SAM local 전용 Docker 서비스 URL JSON으로 변환한다.
set -euo pipefail

WORKING_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$WORKING_ROOT/.." && pwd)"
SOURCE_ENV="$REPO_ROOT/.env"
OUTPUT="$WORKING_ROOT/env/local-env.generated.json"

[[ -f "$SOURCE_ENV" ]] || { printf '.env 없음: %s\n' "$SOURCE_ENV" >&2; exit 1; }
umask 077

python3 - "$SOURCE_ENV" "$OUTPUT" <<'PY'
import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

source, output = map(Path, sys.argv[1:])
values = {}
for raw in source.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")

def required(name, default=""):
    value = values.get(name, default)
    if not value:
        raise SystemExit(f".env 필수 값 누락: {name}")
    return value

member_user = required("MARIADB_USER", "mockinv")
member_password = values.get("MARIADB_PASSWORD") or "12345678!!"
member_db = required("MARIADB_DATABASE", "mockinv")
quant_user = required("QUANT_DB_USER", "quant")
quant_password = values.get("QUANT_DB_PASSWORD") or "quant"
quant_db = required("QUANT_DB_NAME", "quant_research")

ohlcv_url = values.get("OHLCV_DATABASE_URL") or "postgresql+psycopg://admin:admin1234@pg-stock:5432/admin"
qdrant_url = values.get("QDRANT_URL") or "http://qdrant:6333"
if qdrant_url == ":memory:":
    qdrant_url = "http://qdrant:6333"

payload = {
    "DatabasePracticeFunction": {
        "DATABASE_URL": f"mysql+pymysql://{quote_plus(member_user)}:{quote_plus(member_password)}@mariadb:3306/{member_db}",
        "QUANT_DATABASE_URL": f"postgresql+psycopg://{quote_plus(quant_user)}:{quote_plus(quant_password)}@postgres:5432/{quant_db}",
        "OHLCV_DATABASE_URL": ohlcv_url,
        "REDIS_URL": values.get("REDIS_URL") or "redis://redis:6379/0",
        "REDIS_SESSION_KEY_PREFIX": values.get("REDIS_SESSION_KEY_PREFIX") or "stock-coin-trade:session:",
        "QDRANT_URL": qdrant_url,
        "QDRANT_API_KEY": values.get("QDRANT_API_KEY", ""),
        "QDRANT_COLLECTION": "market_knowledge",
    }
}
output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
print(f"Generated: {output}")
PY
