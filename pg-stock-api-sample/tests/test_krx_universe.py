from datetime import date

from pgstock.jobs.krx_universe import LISTING_DATE_OFFSET, TAIL_LENGTH, parse_master
from pgstock.jobs.ohlcv_sync import skip_known_empty_years


def _line(market, code, name, group, listed="20170710"):
    """KIS 마스터 한 줄을 흉내 낸다: [단축코드 9][표준코드 12][한글명][고정폭 영역]."""
    fixed = [" "] * TAIL_LENGTH[market]
    fixed[0:2] = group
    offset = LISTING_DATE_OFFSET[market]
    fixed[offset:offset + 8] = listed
    return f"{code:<9}KR7{code}000{name}" + "".join(fixed)


def test_parse_master_keeps_only_stocks():
    """ST/FS/DR(주식)만 남기고 ETF·ETN·리츠는 빼며 상장일을 읽는지 검증한다."""
    lines = [
        _line("KOSPI", "035720", "카카오", "ST"),
        _line("KOSPI", "069500", "KODEX 200", "EF"),
        _line("KOSPI", "Q50006", "신한 레버리지 ETN", "EN"),
        _line("KOSPI", "293940", "신한알파리츠", "RT"),
        _line("KOSPI", "900140", "엘브이엠씨홀딩스", "FS", "20130530"),
        _line("KOSPI", "J00362", "KG모빌리티 122WR", "SW"),
    ]
    stocks = parse_master("\r\n".join(lines).encode("cp949"), "KOSPI")
    assert [(s.code, s.name, s.market) for s in stocks] == [
        ("035720", "카카오", "KOSPI"),
        ("900140", "엘브이엠씨홀딩스", "KOSPI"),
    ]
    assert stocks[0].listed_on == date(2017, 7, 10)


def test_parse_master_kosdaq_layout():
    """KOSDAQ은 고정폭 길이·상장일 위치가 다르다."""
    stocks = parse_master(_line("KOSDAQ", "086520", "에코프로", "ST", "20070720").encode("cp949"), "KOSDAQ")
    assert [(s.code, s.listed_on) for s in stocks] == [("086520", date(2007, 7, 20))]


def test_skip_years_before_listing_and_known_empty():
    """상장 전 연도와 empty로 확인된 과거 연도는 빼고 올해는 남긴다."""
    ranges = [(y, date(y, 1, 1), date(y + 1, 1, 1)) for y in range(2016, 2027)]
    kept = skip_known_empty_years(ranges, "0001A0", date(2026, 10, 21), {("0001A0", 2025)}, date(2024, 3, 2))
    assert [year for year, _, _ in kept] == [2024, 2026]
