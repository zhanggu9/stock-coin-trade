"""pg-stock PostgreSQL 접속 확인용 간단한 스크립트.

실행:
    python connect_pg_stock.py

접속 URL을 바꾸려면:
    PG_STOCK_URL='postgresql://user:password@host:5432/db' python connect_pg_stock.py
"""

from __future__ import annotations

import os

import psycopg


# 환경변수가 있으면 우선 사용하고, 없으면 제공받은 기본 접속 정보를 사용한다.
DATABASE_URL = os.getenv(
    "PG_STOCK_URL",
    "postgresql://admin:admin1234@43.202.161.134:55432/admin",
)


def main() -> None:
    """PostgreSQL에 연결해 연결 상태와 pg-stock 데이터 개요를 출력한다."""
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]

                cursor.execute("SELECT count(*) FROM tickers")
                ticker_count = cursor.fetchone()[0]

                cursor.execute("SELECT count(*) FROM ohlcv")
                ohlcv_count = cursor.fetchone()[0]

        print("PostgreSQL connection: OK")
        print(f"Server: {version}")
        print(f"Tickers: {ticker_count:,}")
        print(f"OHLCV rows: {ohlcv_count:,}")
    except psycopg.Error as exc:
        print(f"PostgreSQL connection failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
