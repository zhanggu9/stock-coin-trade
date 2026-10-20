"""주요 국내 종목의 2020년 이후 일별 OHLCV를 가져와 pg-stock에 upsert한다.

pg-stock-api-sample 루트에서 실행:
    python -m pgstock.jobs.ohlcv_crawler

``ohlcv``가 (ticker_code, trade_date)를 기본키로 쓰므로 멱등하다. 다시 실행하면 공급자 보정도 반영된다.
"""

from __future__ import annotations

import argparse
import ast
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import create_engine, text

from pgstock.config import get_settings

# 반도체·자동차·플랫폼·배터리·바이오·금융·통신의 유동성 높은 KOSPI/KOSDAQ 대표 종목.
MAJOR_TICKERS = {
    "005930": ("삼성전자", "KOSPI"),
    "000660": ("SK하이닉스", "KOSPI"),
    "005380": ("현대차", "KOSPI"),
    "000270": ("기아", "KOSPI"),
    "012330": ("현대모비스", "KOSPI"),
    "035420": ("NAVER", "KOSPI"),
    "035720": ("카카오", "KOSPI"),
    "051910": ("LG화학", "KOSPI"),
    "373220": ("LG에너지솔루션", "KOSPI"),
    "006400": ("삼성SDI", "KOSPI"),
    "207940": ("삼성바이오로직스", "KOSPI"),
    "068270": ("셀트리온", "KOSPI"),
    "105560": ("KB금융", "KOSPI"),
    "055550": ("신한지주", "KOSPI"),
    "086790": ("하나금융지주", "KOSPI"),
    "316140": ("우리금융지주", "KOSPI"),
    "066570": ("LG전자", "KOSPI"),
    "017670": ("SK텔레콤", "KOSPI"),
    "028260": ("삼성물산", "KOSPI"),
    "247540": ("에코프로비엠", "KOSDAQ"),
    "086520": ("에코프로", "KOSDAQ"),
    "196170": ("알테오젠", "KOSDAQ"),
    "091990": ("셀트리온헬스케어", "KOSDAQ"),
    "263750": ("펄어비스", "KOSDAQ"),
}


def yahoo_symbol(code, market):
    """국내 시장 코드에 맞는 Yahoo Finance 티커 접미사를 붙인다."""
    return f"{code}.KS" if market == "KOSPI" else f"{code}.KQ"


def normalize_download(frame):
    """Yahoo DataFrame을 내부 표준 행 목록으로 바꾸고 가격 이상치를 제거한다.

    공급자마다 컬럼명·인덱스·멀티인덱스 형태가 다를 수 있으므로 이 경계에서
    날짜와 가격 컬럼을 통일한다. 고가/저가 관계와 음수 값도 함께 검증해 잘못된
    행이 데이터베이스에 들어가지 않게 한다.
    """
    if frame is None or frame.empty:
        return []
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns={"Adj Close": "adj_close"})
    if "adj_close" not in frame.columns:
        frame["adj_close"] = frame["Close"]
    frame = frame.reset_index().rename(columns={
        "Date": "trade_date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
    })
    required = ["trade_date", "open", "high", "low", "close", "adj_close", "volume"]
    frame = frame[required].dropna()
    frame = frame[
        (frame[["open", "high", "low", "close", "adj_close"]] > 0).all(axis=1)
        & (frame["volume"] >= 0)
        & (frame["high"] >= frame[["open", "low", "close"]].max(axis=1))
        & (frame["low"] <= frame[["open", "high", "close"]].min(axis=1))
    ]
    return [
        {
            "trade_date": row.trade_date.date(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "adj_close": float(row.adj_close),
            "volume": int(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]


def fetch_naver(code, start, end):
    """API 키 없이 국내 일봉을 가져온다(end는 배타)."""
    response = requests.get(
        "https://api.finance.naver.com/siseJson.naver",
        params={
            "symbol": code,
            "requestType": 1,
            "startTime": start.strftime("%Y%m%d"),
            "endTime": (end - timedelta(days=1)).strftime("%Y%m%d"),
            "timeframe": "day",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
        timeout=30,
    )
    response.raise_for_status()
    raw_rows = ast.literal_eval(response.text.strip())
    return [row for row in (parse_naver_row(raw) for raw in raw_rows[1:]) if row is not None]


def parse_naver_row(raw):
    """네이버 일봉 한 행([날짜, 시가, 고가, 저가, 종가, 거래량, ...])을 표준 행으로 바꾼다. 쓸 수 없으면 None.

    - 거래가 없던 날(거래정지 등)은 시가·고가·저가가 0으로 오므로 봉을 만들지 않는다.
    - 네이버는 액면분할 등 이전 구간을 수정주가로 소급 조정하면서 반올림해, 종가가 고가보다 1원 높은 식의
      작은 어긋남이 생긴다(예: 삼성전자우 2016-08-23 고가 27,999 / 종가 28,000). 고가·저가 기준 1%(최소 2원)
      이내면 고가/저가를 시가·종가를 포함하도록 바로잡고, 그보다 크면 잘못된 행으로 보고 버린다.
    """
    if len(raw) < 6 or not raw[0]:
        return None
    trade_date = date.fromisoformat(f"{raw[0][:4]}-{raw[0][4:6]}-{raw[0][6:8]}")
    open_price, high, low, close, volume = raw[1:6]
    if not all(value is not None for value in (open_price, high, low, close, volume)):
        return None
    if min(open_price, high, low, close) <= 0 or volume < 0:
        return None
    top, bottom = max(open_price, close), min(open_price, close)
    if high < low:
        return None
    if top > high or bottom < low:
        tolerance = max(high * 0.01, 2)
        if top - high > tolerance or low - bottom > tolerance:
            return None
        high, low = max(high, top), min(low, bottom)
    return {
        "trade_date": trade_date,
        "open": float(open_price),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        # 네이버는 이 엔드포인트에서 수정 종가를 따로 주지 않는다 (가격 자체가 수정주가).
        "adj_close": float(close),
        "volume": int(volume),
    }


def fetch_yahoo(code, market, start, end):
    """Yahoo Finance에서 [start, end) 구간의 일봉을 받아 표준 행으로 반환한다."""
    frame = yf.download(
        yahoo_symbol(code, market),
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return normalize_download(frame)


def upsert_ticker(engine, code, name, market, rows):
    """종목 메타데이터와 OHLCV 행을 하나의 트랜잭션으로 멱등 저장한다.

    같은 종목·날짜가 이미 있으면 최신 공급자 값으로 갱신하되, 값이 실제로
    달라진 경우에만 업데이트한다. 반환값은 INSERT/UPDATE가 반영한 행 수다.
    """
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO tickers (ticker_code, name, market)
            VALUES (:code, :name, :market)
            ON CONFLICT (ticker_code) DO UPDATE
            SET name = EXCLUDED.name, market = EXCLUDED.market
        """), {"code": code, "name": name, "market": market})
        if rows:
            result = conn.execute(text("""
                INSERT INTO ohlcv
                    (ticker_code, trade_date, open, high, low, close, adj_close, volume)
                VALUES
                    (:ticker_code, :trade_date, :open, :high, :low, :close, :adj_close, :volume)
                ON CONFLICT (ticker_code, trade_date) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    adj_close = EXCLUDED.adj_close,
                    volume = EXCLUDED.volume
                WHERE (ohlcv.open, ohlcv.high, ohlcv.low, ohlcv.close, ohlcv.adj_close, ohlcv.volume)
                      IS DISTINCT FROM
                      (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close,
                       EXCLUDED.adj_close, EXCLUDED.volume)
            """), [{"ticker_code": code, **row} for row in rows])
            return result.rowcount
    return 0


def parse_args():
    """CLI 일괄 수집기의 명령행 옵션을 정의하고 파싱한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01", help="inclusive date (YYYY-MM-DD)")
    parser.add_argument("--end", default=(date.today() + timedelta(days=1)).isoformat(), help="exclusive date (YYYY-MM-DD)")
    parser.add_argument("--ticker", action="append", dest="tickers",
                        help="six-character code; may be repeated (default: all curated major tickers)")
    parser.add_argument("--provider", choices=("naver", "yahoo", "auto"), default="naver",
                        help="market data provider (auto falls back from Yahoo to Naver)")
    parser.add_argument("--dry-run", action="store_true", help="download and validate without DB writes")
    return parser.parse_args()


def main():
    """선택한 종목을 내려받아 저장하고 마지막에 집계 스냅샷을 갱신한다."""
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start >= end:
        raise SystemExit("--start must be before --end")

    selected = args.tickers or list(MAJOR_TICKERS)
    unknown = [code for code in selected if code not in MAJOR_TICKERS]
    if unknown:
        raise SystemExit(f"unknown ticker(s): {', '.join(unknown)}")

    engine = None if args.dry_run else create_engine(get_settings().ohlcv_database_url, pool_pre_ping=True)
    total_rows = 0
    failed = []
    for code in selected:
        name, market = MAJOR_TICKERS[code]
        try:
            if args.provider == "naver":
                rows = fetch_naver(code, start, end)
            elif args.provider == "yahoo":
                rows = fetch_yahoo(code, market, start, end)
            else:
                try:
                    rows = fetch_yahoo(code, market, start, end)
                except Exception:
                    rows = []
                if not rows:
                    rows = fetch_naver(code, start, end)
            if not rows:
                raise RuntimeError("no valid rows returned")
            if engine is not None:
                upsert_ticker(engine, code, name, market, rows)
            total_rows += len(rows)
            print(f"{code} {name}: {len(rows):,} rows ({rows[0]['trade_date']} ~ {rows[-1]['trade_date']})")
        except Exception as exc:
            failed.append(code)
            print(f"ERROR {code} {name}: {exc}")

    print(f"completed: {len(selected) - len(failed)}/{len(selected)} tickers, {total_rows:,} rows")
    if engine is not None:
        from pgstock.jobs.ohlcv_aggregate import refresh_ohlcv_aggregates

        snapshot = refresh_ohlcv_aggregates(engine)
        print(f"aggregate refreshed: {snapshot['ohlcv_rows']:,} rows")
    if failed:
        raise SystemExit(f"failed tickers: {', '.join(failed)}")


if __name__ == "__main__":
    main()
