from sqlalchemy import text

SUMMARY_SQL = text("""
  SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
  FROM ohlcv_summary_snapshot WHERE snapshot_id=1
""")


def load_summary(engine) -> dict:
    with engine.connect() as conn:
        row = conn.execute(SUMMARY_SQL).mappings().one()
    return dict(row)
