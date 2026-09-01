import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import pending
from core.parser import events_from_row


def _person(name, rows):
    events = []
    for row in rows:
        events.extend(events_from_row(row))
    return SimpleNamespace(name=name, events=events)


def _row(category, period, reason="", note="", time_field=None):
    return {
        "소속": "본부", "직급": "기간제", "성명": "홍길동", "생년월일": "1990-01-01",
        "종별": category, "사용기간(날짜)": period, "사용시간(시분)": time_field,
        "사유": reason, "비고": note, "연락처": "", "결재상태": "완료",
    }


def test_unknown_category_is_collected_without_defaults():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("경조사휴가", "2026-08-10")])}
    groups = pending.collect_groups(people)
    assert len(groups) == 1
    assert groups[0]["raw_category"] == "경조사휴가"
    assert groups[0]["default_paid"] is None
    assert groups[0]["default_accrual"] is None
    assert groups[0]["paid"] is None


def test_known_category_without_reason_is_not_collected():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("연가", "2026-08-10")])}
    assert pending.collect_groups(people) == []


def test_known_category_with_reason_is_collected_with_rule_defaults():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("연가", "2026-08-10", reason="집안일")])}
    groups = pending.collect_groups(people)
    assert len(groups) == 1
    assert groups[0]["reason"] == "집안일"
    assert groups[0]["default_paid"] is True
    assert groups[0]["default_accrual"] is True


def test_known_category_with_note_only_is_also_collected():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("공가", "2026-08-10", note="법원출석")])}
    assert len(pending.collect_groups(people)) == 1


def test_full_day_gita_defaults_are_unpaid_and_breaking():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("기타", "2026-08-10", reason="개인사정")])}
    groups = pending.collect_groups(people)
    assert groups[0]["default_paid"] is False
    assert groups[0]["default_accrual"] is False


def test_one_group_per_source_row_even_for_multi_day():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("경조사휴가", "2026-08-10~2026-08-12")])}
    groups = pending.collect_groups(people)
    assert len(groups) == 1
    assert len(groups[0]["events"]) == 3
    assert groups[0]["start"] == date(2026, 8, 10)
    assert groups[0]["end"] == date(2026, 8, 12)


def test_apply_decisions_sets_axes_and_writes_back_to_row():
    row = _row("경조사휴가", "2026-08-10")
    people = {"홍길동::1990-01-01": _person("홍길동", [row])}
    groups = pending.collect_groups(people)
    pending.apply_decisions(groups, [{"paid": False, "accrual": False}])
    event = groups[0]["events"][0]
    assert event.unpaid is True
    assert event.breaks is True
    assert event.classified == "무급특별휴가"
    assert row[pending.PAID_COL] == "무급"
    assert row[pending.ACCRUAL_COL] == "미발생"


def test_apply_decisions_never_overwrites_known_classification():
    """사유가 적힌 연가를 유급으로 확인해도 분류는 '연가'로 남아야 한다 -
    덮어쓰면 연가 잔량 소진이 사라진다."""
    row = _row("연가", "2026-08-10", reason="집안일")
    people = {"홍길동::1990-01-01": _person("홍길동", [row])}
    groups = pending.collect_groups(people)
    pending.apply_decisions(groups, [{"paid": True, "accrual": True}])
    assert groups[0]["events"][0].classified == "연가"
    assert row[pending.PAID_COL] == "유급"


def test_apply_decisions_rejects_wrong_length():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("경조사휴가", "2026-08-10")])}
    groups = pending.collect_groups(people)
    try:
        pending.apply_decisions(groups, [])
    except ValueError:
        return
    raise AssertionError("개수가 다르면 ValueError를 내야 한다")


def test_apply_decisions_rejects_missing_choice():
    people = {"홍길동::1990-01-01": _person("홍길동", [_row("경조사휴가", "2026-08-10")])}
    groups = pending.collect_groups(people)
    try:
        pending.apply_decisions(groups, [{"paid": None, "accrual": True}])
    except ValueError:
        return
    raise AssertionError("미선택이면 ValueError를 내야 한다")


if __name__ == "__main__":
    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_"):
            _fn()
    print("ALL OK")
