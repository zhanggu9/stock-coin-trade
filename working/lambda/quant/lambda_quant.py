import json
from sqlalchemy import create_engine
from quant_service import recent_prices
from secret_config import environment_values

config = environment_values(("QUANT_DATABASE_URL",))
engine = create_engine(config["QUANT_DATABASE_URL"], pool_pre_ping=True)


def lambda_handler(event, context):
    query = event.get("queryStringParameters") or {}
    symbol = query.get("symbol", "005930").strip().upper()[:20]
    if not symbol:
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": "symbol이 필요합니다."}, ensure_ascii=False)}
    try:
        limit = max(1, min(int(query.get("limit", 30)), 100))
    except (TypeError, ValueError):
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": "limit은 정수여야 합니다."}, ensure_ascii=False)}
    rows = recent_prices(engine, symbol, limit)
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"rows": rows}, ensure_ascii=False, default=str)}
