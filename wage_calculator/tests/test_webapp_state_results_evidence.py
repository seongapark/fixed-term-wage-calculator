import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config
from core.parser import person_key
from webapp.state import AppState

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"
A_FILE = FIXTURE_DIR / "개인정보_예시(A).xlsx"
B_FILE = FIXTURE_DIR / "근무상황_예시(B).xlsx"


def _config_with_survey():
    return Config({
        "surveys": [{"name": "8월 정기조사", "start": "2026-08-01", "end": "2026-08-31"}],
        "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}},
        "holidays": ["2026-08-15"],
    })


def _calculated_state():
    state = AppState()
    state.config_obj = _config_with_survey()
    state.load_files(str(A_FILE), str(B_FILE))
    state.confirm_special_leave(["유급특별휴가"])
    keys = list(state.people.keys())
    state.batch_assign(keys, "8월 정기조사")
    state.prepare_calculation(2026, 8)
    state.run_calculation()
    return state


def test_results_summary_has_five_rows_with_expected_keys():
    state = _calculated_state()
    rows = state.results_summary()
    assert len(rows) == 5
    expected_keys = {"key", "label", "survey", "period", "total_days",
                      "weekly_holiday_days", "remaining_leave_days", "total_payment"}
    assert expected_keys <= rows[0].keys()
    print("OK: test_results_summary_has_five_rows_with_expected_keys")


def test_evidence_names_matches_results_count():
    state = _calculated_state()
    names = state.evidence_names()
    assert len(names) == 5
    assert {"key", "label"} <= names[0].keys()
    print("OK: test_evidence_names_matches_results_count")


def test_evidence_for_returns_none_for_unknown_key():
    state = _calculated_state()
    assert state.evidence_for("존재하지않음::19000101") is None
    print("OK: test_evidence_for_returns_none_for_unknown_key")


def test_evidence_for_known_person_has_all_sections():
    state = _calculated_state()
    key = state.evidence_names()[0]["key"]
    data = state.evidence_for(key)
    assert set(data.keys()) == {
        "raw_rows", "weekly", "late_out", "late_out_total_minutes",
        "late_out_used_total_minutes", "late_out_offset_total_minutes",
        "meal", "leave", "leave_final",
    }
    assert isinstance(data["raw_rows"], list)
    assert "remaining_leave_days" in data["leave_final"]
    print("OK: test_evidence_for_known_person_has_all_sections")


def test_evidence_for_matches_raw_rows_by_name_when_birth_is_unavailable():
    """A파일에 '생년월일' 컬럼이 없거나(선택 컬럼) 비어있으면 TargetPerson.birth가
    ""로 남는다. 이때 evidence_for()가 여전히 정확한 생년월일 일치를
    요구하면, B파일에 실제로 그 사람의 행이 있어도(성명은 일치) 원본이
    영원히 안 보인다. build_target_people()이 동명이인 없는 사람은 이름만
    으로도 안전하게 매칭하는 것과 동일하게, birth가 비어있을 때는 이름만
    으로 매칭해야 한다."""
    state = _calculated_state()
    hong_result = next(r for r in state.results if r.name == "홍길동")
    before = state.evidence_for(person_key(hong_result.name, hong_result.birth))
    assert len(before["raw_rows"]) > 0, "테스트 전제 실패: 홍길동의 원본 행이 없음"

    # A파일에 생년월일 컬럼이 없는 상황을 재현: 계산 결과의 birth를 비운다
    # (PayrollResult는 계산 시점에 TargetPerson.birth를 복사해 가지므로,
    # results 쪽을 직접 비워야 실제 상황을 재현할 수 있다).
    hong_result.birth = ""
    empty_birth_key = person_key(hong_result.name, "")

    after = state.evidence_for(empty_birth_key)
    assert after is not None, "빈 생년월일로도 대상자를 찾을 수 있어야 함"
    assert len(after["raw_rows"]) == len(before["raw_rows"]), (
        "생년월일이 비어있어도 이름이 일치하면 원본 행이 매칭되어야 함"
    )
    print("OK: test_evidence_for_matches_raw_rows_by_name_when_birth_is_unavailable")


def test_evidence_for_matches_raw_rows_when_birth_cell_is_a_real_date():
    """B파일의 '생년월일' 셀이 순수 텍스트가 아니라 실제 날짜형(datetime)일 때도
    근무현황 원본이 정상적으로 매칭되어야 한다 - openpyxl은 날짜형 셀을
    datetime으로 반환하므로 str()로 그냥 비교하면 시간이 붙어 매칭이 조용히
    실패한다(core/retroactive.py의 _row_birth_matches가 이미 같은 문제를
    해결한 적이 있는데, evidence_for()는 그 정규화 없이 이관됨)."""
    state = _calculated_state()
    hong = next(p for p in state.people.values() if p.name == "홍길동")
    key = person_key(hong.name, hong.birth)

    before = state.evidence_for(key)
    assert len(before["raw_rows"]) > 0, "테스트 전제 실패: 홍길동의 원본 행이 없음"

    mutated = 0
    for row in state.giganje_rows:
        if row["성명"] == hong.name:
            # openpyxl은 날짜형 셀을 datetime.date가 아니라 datetime.datetime으로
            # 반환한다(시각이 00:00:00으로 채워짐) - 이 형태로 정확히 재현해야 한다.
            row["생년월일"] = datetime.fromisoformat(hong.birth)
            mutated += 1
    assert mutated > 0, "테스트 전제 실패: 변형할 원본 행이 없음"

    after = state.evidence_for(key)
    assert len(after["raw_rows"]) == len(before["raw_rows"]), (
        "생년월일 셀이 날짜형이어도 원본 행 매칭 개수가 동일해야 함"
    )
    print("OK: test_evidence_for_matches_raw_rows_when_birth_cell_is_a_real_date")


if __name__ == "__main__":
    test_results_summary_has_five_rows_with_expected_keys()
    test_evidence_names_matches_results_count()
    test_evidence_for_returns_none_for_unknown_key()
    test_evidence_for_known_person_has_all_sections()
    test_evidence_for_matches_raw_rows_by_name_when_birth_is_unavailable()
    test_evidence_for_matches_raw_rows_when_birth_cell_is_a_real_date()
    print("ALL OK")
