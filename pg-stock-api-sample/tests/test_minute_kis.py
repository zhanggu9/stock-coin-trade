from datetime import date

from pgstock.jobs.minute_kis import KisMinuteClient, parse_minute_rows


def _row(hhmm, price, volume=10):
    return {"stck_bsop_date": "20261020", "stck_cntg_hour": f"{hhmm:04d}00", "stck_oprc": str(price),
            "stck_hgpr": str(price + 5), "stck_lwpr": str(price - 5), "stck_prpr": str(price), "cntg_vol": str(volume)}


def test_parse_minute_rows_sorts_and_filters():
    """시간 오름차순으로 바꾸고 가격 0 행은 버리며 고가·저가가 시가·종가를 포함하게 한다."""
    rows = [_row(901, 100), _row(900, 100), {**_row(902, 100), "stck_oprc": "0"},
            {**_row(903, 100), "stck_hgpr": "99"}]
    assert parse_minute_rows(rows) == [(900, 100, 105, 95, 100, 10), (901, 100, 105, 95, 100, 10),
                                       (903, 100, 100, 95, 100, 10)]


class FakeClient(KisMinuteClient):
    """KIS 대신 382개(09:00~15:20 381개 + 15:30) 분봉을 시간 역순 120개씩 돌려준다."""

    def __init__(self):
        super().__init__("key", "secret", "https://example.invalid", per_second=0)
        minutes = [h * 100 + m for h in range(9, 16) for m in range(60) if 900 <= h * 100 + m <= 1520] + [1530]
        self.all_rows = [_row(t, 1000 + i) for i, t in enumerate(minutes)]
        self.requests = []

    def _page(self, code, ymd, hour):
        self.requests.append(hour)
        upto = [r for r in self.all_rows if r["stck_cntg_hour"] <= hour]
        return list(reversed(upto))[:120]


def test_fetch_day_paginates_backwards_without_duplicates():
    client = FakeClient()
    bars = client.fetch_day("005930", date(2026, 10, 20))
    assert len(bars) == len(client.all_rows) == 382
    assert bars[0][0] == 900 and bars[-1][0] == 1530
    assert len({bar[0] for bar in bars}) == 382
    assert len(client.requests) == 4 and client.requests[0] == "153000"
