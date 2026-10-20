from pgstock.jobs.ohlcv_crawler import parse_naver_row


def test_naver_row_rounding_and_halt():
    """수정주가 반올림 어긋남은 바로잡고, 거래 없던 날과 큰 어긋남은 버린다."""
    fixed = parse_naver_row(["20160823", 27880, 27999, 27500, 28000, 64063])
    assert (fixed["high"], fixed["low"], fixed["close"]) == (28000.0, 27500.0, 28000.0)
    assert parse_naver_row(["20200506", 0, 0, 0, 7757, 0]) is None          # 거래정지
    assert parse_naver_row(["20200507", 100, 105, 99, 120, 10]) is None     # 큰 어긋남
    assert parse_naver_row(["20200508", 100, 105, 99, 101, 10])["high"] == 105.0
