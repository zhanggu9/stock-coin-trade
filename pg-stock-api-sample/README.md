# pg-stock-api-sample

`python-stock-backend` 에서 **pg-stock(PostgreSQL) OHLCV 크롤링과 조회 API** 에 관련된 Python 소스만 떼어내
단독으로 실행할 수 있게 모은 샘플입니다. MariaDB·Redis·Qdrant 등 다른 의존성은 없습니다.

## 폴더 구성

```
pg-stock-api-sample/
├─ main.py                         # FastAPI 진입점 (+ APScheduler lifespan)
├─ requirements.txt
├─ .env.example
├─ sql/pg-stock.sql                # pg-stock 초기 스키마 (tickers, ohlcv, 집계·상태 테이블)
├─ tests/test_ohlcv_sync.py        # 수집 구간 계산 단위 테스트
└─ pgstock/
   ├─ config.py                    # 환경변수 설정 (원본 Settings 의 OHLCV 항목만)
   ├─ errors.py                    # ApiError + JSON 오류 핸들러
   ├─ parsing.py                   # clamp / parse_int
   ├─ jobs/
   │  ├─ krx_universe.py           # KOSPI·KOSDAQ 주식 목록 (KIS 종목 마스터, ETF·ETN·리츠·펀드 제외)
   │  ├─ ohlcv_backfill.py         # 10년치 누락 진단·재수집 CLI
   │  ├─ ohlcv_crawler.py          # 네이버·야후 일봉 다운로드, upsert, 주요 24종목 CLI
   │  ├─ ohlcv_sync.py             # 연도 단위 증분 수집(멱등), ohlcv_sync_status 기록
   │  ├─ ohlcv_aggregate.py        # 집계 스냅샷 갱신, 일일 배치 원장
   │  └─ scheduler.py              # APScheduler 등록 (09:50·12:50·16:50 KST)
   ├─ services/
   │  ├─ ohlcv_store.py            # pg-stock 읽기 전용 조회 (요약·종목·행·공개 API)
   │  ├─ ohlcv_ingest.py           # 종목 하나 온디맨드 적재
   │  └─ openapi_auth.py           # Bearer 키 검증 + 호출 제한
   └─ api/
      ├─ ohlcv_db.py               # GET /api/ohlcv-db/{summary,tickers,rows}
      └─ openapi_ohlcv.py          # /openapi/v1/ohlcv/{search,tickers,{code}} , POST ingest
```

## 원본과 달라진 점

| 항목 | 원본 (`python-stock-backend`) | 샘플 |
|---|---|---|
| import 경로 | `app.core.*`, `app.jobs.*`, `app.services.*` | `pgstock.*` |
| 설정 | `app.core.config.Settings` 전체 | OHLCV 관련 항목만 (`pgstock/config.py`) |
| 스케줄러 | 코인마켓캡·업비트·봇 거래·OHLCV | OHLCV 증분 수집만 |
| Open API 키 | MariaDB `api_key` 테이블 SHA-256 조회 | `OHLCV_API_KEYS` 환경변수 고정 키 |
| Open API 라우트 | 주식·주문·계좌 포함 | `/openapi/v1/ohlcv/*` 만 |

수집·upsert·집계·조회 로직 자체는 원본과 동일합니다.

## 실행

```bash
cd pg-stock-api-sample
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # OHLCV_DATABASE_URL 을 실제 pg-stock 에 맞게 수정

# (처음 한 번) 빈 DB에 스키마 생성
psql "postgresql://admin:admin1234@localhost:55432/admin" -f sql/pg-stock.sql

# 최초 일괄 수집 (내장 주요 24종목, 2020-01-01 ~ 오늘)
python -m pgstock.jobs.ohlcv_crawler
python -m pgstock.jobs.ohlcv_crawler --ticker 005930 --start 2024-01-01 --provider auto --dry-run

# API + 스케줄러 기동
uvicorn main:app --reload --port 8010
```

pg-stock 을 Docker 로 띄우려면 저장소 루트의 `docker-compose.pg-stock.yml` 을 그대로 쓰면 됩니다.

## 수집 대상 (OHLCV_SYNC_TICKERS=listed, 기본값)

한국투자증권 공개 종목 마스터(`kospi_code.mst`, `kosdaq_code.mst`)의 증권그룹구분코드로 **주식만** 고릅니다.
마스터는 매 영업일 갱신되므로 신규 상장·상장폐지가 다음 수집부터 반영됩니다.

| 포함 | 제외 |
|---|---|
| ST 주권(보통주·우선주·스팩), FS 외국주권, DR 주식예탁증서 | EF ETF, EN ETN, RT 리츠, IF 인프라투융자, MF·PF·BC 펀드·수익증권, SW·SR 신주인수권 |

2026-10 기준 약 2,740종목(KOSPI 915, KOSDAQ 1,824)이며 `OHLCV_SYNC_START_YEAR=2016` 부터(약 10년치) 받습니다.
상장일 이전 연도와 공급자에 데이터가 없던 과거 연도(`ohlcv_sync_status.status = 'empty'`)는 정기 수집에서 다시 요청하지 않습니다.

### 10년치 누락 진단·재수집

```bash
python -m pgstock.jobs.ohlcv_backfill --dry-run      # 진단만 (종목별 기대 거래일 대비 누락 일수)
python -m pgstock.jobs.ohlcv_backfill                # 누락 종목만 네이버에서 시작일~오늘 다시 받아 upsert
```

시장 거래일 달력은 대형주 5종목 일봉의 합집합으로 만들고, 종목별로 max(시작일, 상장일) 이후 달력 거래일 중
DB에 없는 날을 셉니다. 재수집 후에도 남는 누락은 대부분 거래정지 등으로 공급자에도 없는 날입니다.

### 서버 컨테이너 교체

서버에서 새 이미지를 빌드한 뒤(`docker build -t pg-stock-api-sample:latest .`) 로컬 PC에서 실행하면
기존 컨테이너의 환경변수·네트워크·포트·재시작 정책을 유지한 채 `OHLCV_SYNC_TICKERS=listed`, `OHLCV_SYNC_START_YEAR=2016` 으로
다시 만듭니다. 새 컨테이너가 `/health` 에 응답하지 않으면 원래 컨테이너로 되돌립니다.

```bash
ssh -i /home/l/stock-coin-trade/test-0922.pem ubuntu@13.209.87.155 'bash -s' < scripts/redeploy_container.sh
```

## 1분봉 (KIS, 과거 약 1년 + 매일 누적)

KIS Open API 주식일별분봉조회(`FHKST03010230`)는 과거 1분봉을 **약 1년(거래일 약 250일)만** 보관합니다.
그래서 처음에 남아 있는 1년치를 전 종목 받아 두고, 매일 장 마감 후 그날 분봉을 더해 기간을 늘립니다.
네이버 차트 API는 최근 6거래일, 야후는 최근 30일만 줘서 과거 수집에는 쓸 수 없습니다.

| 항목 | 값 |
|---|---|
| 저장 | `ohlcv_minute_day` (종목·하루당 1행, 분봉은 배열 열 + lz4 압축), 행 단위 조회는 뷰 `ohlcv_minute_bar` |
| 대상 | 일봉 테이블에서 그날 거래량이 있던 KOSPI·KOSDAQ 주식 (상장 전·거래정지일 제외) |
| 용량 (실측) | 종목·하루당 약 4~5KB → 전 종목 1년 약 3GB (분봉 1행씩 저장하면 약 15GB) |
| 호출 | 1회 120분, 종목·하루당 평균 2.2회. 전 종목 1년치 약 150만 회 (초당 15회 기준 약 30시간) |

```bash
python -m pgstock.jobs.minute_backfill --dry-run   # 남은 종목·일 수와 예상 시간
python -m pgstock.jobs.minute_backfill             # 보관된 가장 오래된 날부터 수집 (중단 후 다시 실행하면 이어받기)
```

`MINUTE_SYNC_ENABLED=true` 이면 스케줄러가 평일 17:30에 최근 `MINUTE_CATCHUP_DAYS` 거래일 중 빠진 종목·일을 채웁니다.
백필과 정기 수집은 DB 잠금으로 동시에 돌지 않습니다. 서버에서는 `~/pg-stock-api-deploy/minute.env` 에 KIS 키와
`MINUTE_SYNC_ENABLED=true` 를 두면 `scripts/redeploy_container.sh` 가 함께 반영합니다.

## 수집 흐름

1. `scheduler.start_scheduler()` 가 기동 시 집계 스냅샷을 한 번 만들고, `run_incremental_sync` 를 cron 으로 등록합니다.
2. `ohlcv_sync.collect_ohlcv()` 가 종목마다 `ohlcv` 의 연도별 마지막 거래일을 보고 빠진 연도는 전체,
   올해는 최근 `OHLCV_SYNC_CORRECTION_DAYS` 일부터 다시 받아 `upsert_ticker()` 로 적재합니다.
3. 결과는 `ohlcv_sync_status` 에 종목·연도 단위로 남고, 끝나면 `refresh_ohlcv_aggregates()` 가
   `ohlcv_summary_snapshot` / `ohlcv_yearly_summary` / `ohlcv_market_summary` 를 갱신합니다.
4. 검색에 없는 종목은 `POST /openapi/v1/ohlcv/ingest` 로 즉시 한 종목만 채울 수 있습니다.

## API

| Method | Path | 인증 | 설명 |
|---|---|---|---|
| GET | `/health` | 없음 | 상태 확인 |
| GET | `/api/ohlcv-db/summary` | 없음 | 일일 스냅샷 기반 전체·연도·시장 집계 |
| GET | `/api/ohlcv-db/tickers?q=&limit=&offset=` | 없음 | 종목별 적재 건수 |
| GET | `/api/ohlcv-db/rows?q=&market=&date_from=&...` | 없음 | AG Grid 용 조건 검색·정렬·페이징 |
| GET | `/openapi/v1/ohlcv/search?q=삼성` | 공개(IP 제한) | 종목 자동완성 |
| GET | `/openapi/v1/ohlcv/tickers?year=2026` | 공개(IP 제한) | 수집 종목 탐색 |
| GET | `/openapi/v1/ohlcv/005930?year=2026` | 공개(IP 제한) | 종목 일봉 페이지 조회 |
| POST | `/openapi/v1/ohlcv/ingest` `{"symbol":"035720.KS","name":"카카오"}` | `Authorization: Bearer <OHLCV_API_KEYS>` | 종목 하나 온디맨드 적재 |

## 테스트

```bash
pytest tests
```
