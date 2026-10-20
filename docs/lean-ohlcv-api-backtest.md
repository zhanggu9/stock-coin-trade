# QuantConnect LEAN: OHLCV API 백테스트

## 실행 화면

AI Sheet 페이지에서 **OHLCV API 백테스트** 탭을 선택하고 종목 코드, 시작일, 종료일, 초기 자금을 입력합니다. 기본 예시는 삼성전자 005930이며 기본 전략은 첫 일봉 매수 후 보유입니다.

## API 호출

POST /api/ai-sheet/lean-ohlcv-backtest

요청 본문 예시:

```json
{
  "ticker_code": "005930",
  "date_from": "2021-01-01",
  "date_to": "2026-10-14",
  "initial_cash": 1000000
}
```

응답에는 종목 코드/이름, 실제 로드된 거래일 범위, rowsLoaded, apiPages, LEAN 통계가 포함됩니다.

## 데이터와 인증

- 기본 조회 주소는 http://43.202.161.134:8010이며 OHLCV_API_BASE_URL 환경 변수로 변경할 수 있습니다.
- 현재 GET /openapi/v1/ohlcv/{ticker_code}는 공개 엔드포인트라 조회용 Bearer 토큰이 필요하지 않고, IP 기준 분당 120회 제한을 사용합니다.
- 조회 API는 date_from, date_to, order=asc, limit=1000, offset을 사용합니다. 응답의 ticker, rows, total, nextOffset을 읽고 rows의 trade_date, open, high, low, close, adj_close, volume을 검증합니다.
- 배포에서 조회 인증을 추가한 경우에만 OHLCV_API_TOKEN을 설정하면 됩니다. 기본 설정에서는 해당 변수를 비워 둡니다.

## 처리 흐름 (CSV 미사용)

1. 백엔드가 OHLCV 조회 API를 페이지 단위로 호출해 날짜 범위의 전체 데이터를 가져옵니다.
2. 날짜/가격/거래량을 검증하고 거래일 기준으로 정렬한 다음 임시 JSON Lines 파일로 직렬화합니다. CSV로 변환하지 않습니다.
3. 백엔드는 JSON Lines와 LEAN 어댑터를 원격 LEAN 실행기에 전송합니다.
4. LEAN 컨테이너는 --network none으로 실행되고 OHLCVJsonData 사용자 정의 어댑터가 각 JSON Lines 행을 LEAN 데이터 포인트로 읽습니다.
5. 백테스트 결과 통계를 반환하고 원격 작업 디렉터리를 정리합니다.

JSON Lines는 API 데이터를 LEAN의 행 단위 사용자 정의 데이터 리더에 전달하기 위한 임시 브리지 파일입니다. API 응답은 CSV로 재작성하지 않습니다. API 요청은 백엔드에서 수행하므로 LEAN 컨테이너에 인터넷 접근을 열어두지 않습니다.

## 검증

```bash
cd python-stock-backend
uv run pytest tests/test_lean_ohlcv.py
uv run ruff check app/api/routes/ai_sheet.py app/services/lean_ohlcv.py tests/test_lean_ohlcv.py
```

실제 백테스트 성공 여부는 실행 환경의 OHLCV_API_BASE_URL, LEAN_SSH_HOST, SSH 키/known_hosts, 원격 Docker 이미지 설정에 따라 달라집니다.
