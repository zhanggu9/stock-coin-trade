import json
from sqlalchemy import create_engine
from ohlcv_service import load_summary
from secret_config import environment_values

config = environment_values(("OHLCV_DATABASE_URL",))
engine = create_engine(config["OHLCV_DATABASE_URL"], pool_pre_ping=True)


def lambda_handler(event, context):
    summary = load_summary(engine)
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps(summary, ensure_ascii=False, default=str)}
