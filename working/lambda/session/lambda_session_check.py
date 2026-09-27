import json
import os
from redis import Redis
from secret_config import environment_values
from session_service import session_ttl

config = environment_values(("REDIS_URL",))
client = Redis.from_url(config["REDIS_URL"], socket_timeout=3)
prefix = os.environ.get("REDIS_SESSION_KEY_PREFIX", "stock-coin-trade:session:")


def lambda_handler(event, context):
    sid = (event.get("queryStringParameters") or {}).get("sid", "")
    try:
        ttl = session_ttl(client, prefix, sid)
    except ValueError as exc:
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": str(exc)}, ensure_ascii=False)}
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"exists": ttl >= 0, "ttl": ttl})}
