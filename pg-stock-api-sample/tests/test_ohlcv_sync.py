from datetime import date

from pgstock.jobs.ohlcv_sync import plan_year_ranges


def test_missing_years_and_current_increment_are_planned():
    """누락 연도는 전체 구간, 현재 연도는 보정일수만큼만 계획되는지 검증한다."""
    existing = {
        2024: {"last_date": date(2024, 12, 30), "row_count": 240},
        2026: {"last_date": date(2026, 9, 23), "row_count": 180},
    }
    ranges = plan_year_ranges(existing, 2024, date(2026, 9, 26), correction_days=7)
    assert ranges == [
        (2025, date(2025, 1, 1), date(2026, 1, 1)),
        (2026, date(2026, 9, 16), date(2026, 9, 27)),
    ]


def test_reconciliation_plans_every_year():
    """reconcile 모드가 기존 데이터가 있어도 모든 연도를 다시 계획하는지 검증한다."""
    existing = {2025: {"last_date": date(2025, 12, 30), "row_count": 240}}
    ranges = plan_year_ranges(existing, 2025, date(2026, 2, 3), reconcile=True)
    assert ranges == [
        (2025, date(2025, 1, 1), date(2026, 1, 1)),
        (2026, date(2026, 1, 1), date(2026, 2, 4)),
    ]
