def session_ttl(client, prefix: str, sid: str) -> int:
    if not sid or len(sid) > 256:
        raise ValueError("올바르지 않은 SID")
    return client.ttl(f"{prefix}{sid}")
