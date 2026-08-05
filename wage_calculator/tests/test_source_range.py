import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import build_event


def test_default_source_range_is_single_day():
    e = build_event("공가", date(2026, 7, 6))
    assert e.source_range == (date(2026, 7, 6), date(2026, 7, 6)), e.source_range
    print("OK: test_default_source_range_is_single_day")


def test_explicit_source_range_is_kept():
    e = build_event("특별휴가", date(2026, 7, 8), source_range=(date(2026, 7, 6), date(2026, 7, 10)))
    assert e.source_range == (date(2026, 7, 6), date(2026, 7, 10)), e.source_range
    print("OK: test_explicit_source_range_is_kept")


if __name__ == "__main__":
    test_default_source_range_is_single_day()
    test_explicit_source_range_is_kept()
    print("ALL OK")
