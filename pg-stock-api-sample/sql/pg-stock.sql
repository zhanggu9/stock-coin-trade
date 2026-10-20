-- Fresh-install schema for the separate Korean-stock OHLCV PostgreSQL database.
-- Existing installations are not changed: docker-entrypoint-initdb.d runs only
-- when the pg-stock-data volume is empty.

CREATE TABLE IF NOT EXISTS tickers (
    ticker_code varchar(20) PRIMARY KEY,
    name varchar(100),
    market varchar(20) DEFAULT 'KOSPI',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ohlcv (
    ticker_code varchar(20) NOT NULL REFERENCES tickers(ticker_code),
    trade_date date NOT NULL,
    open numeric(14, 4),
    high numeric(14, 4),
    low numeric(14, 4),
    close numeric(14, 4),
    adj_close numeric(14, 4),
    volume bigint,
    PRIMARY KEY (ticker_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_trade_date ON ohlcv (trade_date);

CREATE TABLE IF NOT EXISTS ohlcv_data_quality_issues (
    ticker_code varchar(20) NOT NULL,
    trade_date date NOT NULL,
    reason text NOT NULL,
    source_file text NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker_code, trade_date, reason)
);

CREATE TABLE IF NOT EXISTS ohlcv_sync_status (
    ticker_code varchar(20) NOT NULL,
    data_year smallint NOT NULL,
    provider varchar(20) NOT NULL,
    status varchar(20) NOT NULL,
    requested_from date NOT NULL,
    requested_to date NOT NULL,
    fetched_rows integer NOT NULL DEFAULT 0,
    upserted_rows integer NOT NULL DEFAULT 0,
    last_error varchar(500),
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    PRIMARY KEY (ticker_code, data_year)
);

CREATE TABLE IF NOT EXISTS ohlcv_summary_snapshot (
    snapshot_id smallint PRIMARY KEY CHECK (snapshot_id = 1),
    ohlcv_rows bigint NOT NULL DEFAULT 0,
    ticker_count integer NOT NULL DEFAULT 0,
    first_date date,
    last_date date,
    quarantined_rows bigint NOT NULL DEFAULT 0,
    affected_tickers integer NOT NULL DEFAULT 0,
    tracked_ranges integer NOT NULL DEFAULT 0,
    success_ranges integer NOT NULL DEFAULT 0,
    failed_ranges integer NOT NULL DEFAULT 0,
    last_completed_at timestamptz,
    refreshed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ohlcv_yearly_summary (
    data_year smallint PRIMARY KEY,
    row_count bigint NOT NULL,
    ticker_count integer NOT NULL,
    first_date date NOT NULL,
    last_date date NOT NULL,
    refreshed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ohlcv_market_summary (
    market varchar(40) PRIMARY KEY,
    ticker_count integer NOT NULL,
    refreshed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ohlcv_daily_batch_runs (
    batch_date date PRIMARY KEY,
    status varchar(30) NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    fetched_rows bigint NOT NULL DEFAULT 0,
    upserted_rows bigint NOT NULL DEFAULT 0,
    aggregate_refreshed_at timestamptz,
    error_message varchar(500)
);

-- 1분봉 (KIS 주식일별분봉조회). 한 행 = 한 종목의 하루치 정규장 분봉. 배열 열은 lz4로 압축한다.
-- 거래가 없던 분은 빠지며 bar_count = 0 은 그날 분봉이 없었다는 기록이다. hhmm 은 봉 시작 시각(예: 930 = 09:30).
CREATE TABLE IF NOT EXISTS ohlcv_minute_day (
    ticker_code varchar(20) NOT NULL,
    trade_date date NOT NULL,
    bar_count smallint NOT NULL,
    hhmm smallint[] NOT NULL,
    open integer[] NOT NULL,
    high integer[] NOT NULL,
    low integer[] NOT NULL,
    close integer[] NOT NULL,
    volume bigint[] NOT NULL,
    source varchar(20) NOT NULL DEFAULT 'kis',
    collected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_minute_day_trade_date ON ohlcv_minute_day (trade_date);
ALTER TABLE ohlcv_minute_day ALTER COLUMN hhmm SET COMPRESSION lz4;
ALTER TABLE ohlcv_minute_day ALTER COLUMN open SET COMPRESSION lz4;
ALTER TABLE ohlcv_minute_day ALTER COLUMN high SET COMPRESSION lz4;
ALTER TABLE ohlcv_minute_day ALTER COLUMN low SET COMPRESSION lz4;
ALTER TABLE ohlcv_minute_day ALTER COLUMN close SET COMPRESSION lz4;
ALTER TABLE ohlcv_minute_day ALTER COLUMN volume SET COMPRESSION lz4;

-- 분봉 한 개 = 한 행으로 펼쳐 보는 뷰 (trade_time 은 한국시간 봉 시작 시각)
CREATE OR REPLACE VIEW ohlcv_minute_bar AS
SELECT d.ticker_code,
       d.trade_date + make_interval(hours => b.hhmm / 100, mins => b.hhmm % 100) AS trade_time,
       b.open, b.high, b.low, b.close, b.volume
FROM ohlcv_minute_day d
CROSS JOIN LATERAL unnest(d.hhmm, d.open, d.high, d.low, d.close, d.volume)
     AS b(hhmm, open, high, low, close, volume);
