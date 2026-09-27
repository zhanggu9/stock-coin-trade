import json
from sqlalchemy import create_engine
from ohlcv_service import load_summary
from secret_config import secret_values

config = secret_values(("OHLCV_DATABASE_URL",), "OHLCV_SECRET_ARN")
engine = create_engine(config["OHLCV_DATABASE_URL"], pool_pre_ping=True)


def lambda_handler(event, context):
    summary = load_summary(engine)
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps(summary, ensure_ascii=False, default=str)}
