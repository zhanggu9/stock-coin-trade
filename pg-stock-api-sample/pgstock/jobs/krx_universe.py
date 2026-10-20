"""KOSPI·KOSDAQ 상장 주식 목록 (ETF·ETN·리츠·펀드 등 상품 제외).

한국투자증권이 인증 없이 공개하는 종목 마스터 파일(kospi_code.mst / kosdaq_code.mst)을 받아
'증권그룹구분코드'로 주식만 고른다. 마스터 파일은 매 영업일 갱신되므로 신규 상장·상장폐지가
다음 수집부터 자동으로 반영된다.

마스터 한 줄 = [단축코드 9][표준코드 12][한글명 가변][고정폭 영역]. 고정폭 영역은 줄 끝에서
KOSPI 227자, KOSDAQ 221자(줄바꿈 제외)이며 첫 2자가 증권그룹구분코드다.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date

import requests

MASTER_URLS = {
    "KOSPI": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
    "KOSDAQ": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
}
# KIS 예제 파서의 228/222는 줄바꿈을 포함한 길이다. 여기서는 줄바꿈을 떼고 자른다.
TAIL_LENGTH = {"KOSPI": 227, "KOSDAQ": 221}
# 고정폭 영역 안의 '주식 상장 일자'(YYYYMMDD) 위치
LISTING_DATE_OFFSET = {"KOSPI": 105, "KOSDAQ": 100}
# 수집 대상: ST 주권(보통주·우선주·스팩), FS 외국주권, DR 주식예탁증서.
# 제외: EF ETF, EN ETN, RT 리츠, IF 인프라투융자, MF/PF/BC 펀드·수익증권, SW/SR 신주인수권 등.
STOCK_GROUP_CODES = frozenset({"ST", "FS", "DR"})
# 형식이 바뀌어 거의 다 걸러지는 사고를 막기 위한 최소 종목 수
MIN_EXPECTED = {"KOSPI": 500, "KOSDAQ": 1000}

_CODE_PATTERN = re.compile(r"[0-9A-Z]{6}")


@dataclass(frozen=True)
class ListedStock:
    code: str
    name: str
    market: str
    listed_on: date | None


def _parse_yyyymmdd(value: str) -> date | None:
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def parse_master(content: bytes, market: str) -> list[ListedStock]:
    """마스터 파일 내용에서 주식(STOCK_GROUP_CODES)만 골라낸다."""
    tail = TAIL_LENGTH[market]
    offset = LISTING_DATE_OFFSET[market]
    stocks = []
    # str.splitlines()는 고정폭 영역에 들어 있을 수 있는 제어문자(\x1c 등)에서도 줄을 나누므로 쓰지 않는다.
    for line in content.decode("cp949").split("\n"):
        line = line.rstrip("\r")
        if len(line) <= tail:
            continue
        head, fixed = line[:-tail], line[-tail:]
        if fixed[:2] not in STOCK_GROUP_CODES:
            continue
        code = head[0:9].strip()
        if not _CODE_PATTERN.fullmatch(code):
            continue
        stocks.append(ListedStock(
            code=code,
            name=head[21:].strip() or code,
            market=market,
            listed_on=_parse_yyyymmdd(fixed[offset:offset + 8]),
        ))
    return stocks


def fetch_listed_stocks(timeout: float = 60) -> dict[str, ListedStock]:
    """KOSPI·KOSDAQ 상장 주식을 {종목코드: ListedStock}으로 돌려준다 (KOSPI 우선)."""
    result: dict[str, ListedStock] = {}
    for market, url in MASTER_URLS.items():
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            content = archive.read(archive.namelist()[0])
        stocks = parse_master(content, market)
        if len(stocks) < MIN_EXPECTED[market]:
            raise RuntimeError(f"{market} 종목 마스터에서 주식이 {len(stocks)}개만 나왔습니다 (형식 변경 의심).")
        for stock in stocks:
            result.setdefault(stock.code, stock)
    return result
