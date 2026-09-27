-- PostgreSQL Quant DB · 최근 시세 조회 (lambda/quant 서비스 함수가 사용)
-- 바인드 파라미터: :symbol, :limit
SELECT symbol, trade_time, close, volume
FROM market_data
WHERE symbol = :symbol
ORDER BY trade_time DESC
LIMIT :limit;
