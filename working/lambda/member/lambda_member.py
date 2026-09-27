import json
from sqlalchemy import create_engine
from member_service import get_member
from secret_config import environment_values

# 핸들러 밖에서 엔진을 한 번만 만들어 호출 간 재사용한다.
config = environment_values(("DATABASE_URL",))
engine = create_engine(config["DATABASE_URL"], pool_pre_ping=True)


def response(status, body):
    return {"statusCode": status, "headers": {"content-type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False, default=str)}


def lambda_handler(event, context):
    raw_id = (event.get("pathParameters") or {}).get("member_id", "")
    if not raw_id.isdigit():
        return response(400, {"message": "member_id가 필요합니다."})
    member = get_member(engine, int(raw_id))
    return response(200, member) if member else response(404, {"message": "회원 없음"})
