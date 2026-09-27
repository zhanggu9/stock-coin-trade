from sqlalchemy import text


def get_member(engine, member_id: int) -> dict | None:
    sql = text("""
        SELECT member_id, username, email, asset
        FROM member WHERE member_id=:member_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"member_id": member_id}).mappings().first()
    return dict(row) if row else None
