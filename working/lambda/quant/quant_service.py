from sqlalchemy import text

SQL = text("""
  SELECT symbol, trade_time, close, volume
  FROM market_data WHERE symbol=:symbol
  ORDER BY trade_time DESC LIMIT :limit
""")


def recent_prices(engine, symbol: str, limit: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(SQL, {"symbol": symbol, "limit": limit})
        return [dict(row) for row in rows.mappings()]
