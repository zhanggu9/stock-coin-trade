-- PostgreSQL pg-stock · 집계 스냅샷 조회 (lambda/ohlcv 서비스 함수가 사용)
SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
FROM ohlcv_summary_snapshot
WHERE snapshot_id = 1;
