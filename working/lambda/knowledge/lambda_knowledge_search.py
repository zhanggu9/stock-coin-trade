import json
import os
from qdrant_client import QdrantClient
from knowledge_service import search_knowledge
from secret_config import environment_values

config = environment_values(("QDRANT_URL",))
client = QdrantClient(url=config["QDRANT_URL"], api_key=os.environ.get("QDRANT_API_KEY") or None)
collection = os.environ.get("QDRANT_COLLECTION", "market_knowledge")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": "JSON 본문이 필요합니다."}, ensure_ascii=False)}
    vector = body.get("vector")
    if not isinstance(vector, list) or not vector or not all(isinstance(value, (int, float)) for value in vector):
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": "숫자 배열 vector가 필요합니다."}, ensure_ascii=False)}
    try:
        limit = max(1, min(int(body.get("limit", 5)), 20))
    except (TypeError, ValueError):
        return {"statusCode": 400, "headers": {"content-type": "application/json"},
                "body": json.dumps({"message": "limit은 정수여야 합니다."}, ensure_ascii=False)}
    rows = search_knowledge(client, collection, vector, limit)
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"rows": rows}, ensure_ascii=False)}
