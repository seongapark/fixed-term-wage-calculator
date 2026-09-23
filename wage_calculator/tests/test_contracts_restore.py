import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import contracts
from core.config import Config
from core.models import TargetPerson


def _config(end="2026-08-31"):
    return Config({"surveys": [{"name": "정기조사", "start": "2026-08-01", "end": end}]})


def _people():
    return {
        "a": TargetPerson(name="김철수", birth="1990-01-01", survey_name="정기조사",
                          contract_start=date(2026, 8, 1), contract_end=date(2026, 8, 31)),
        "b": TargetPerson(name="이영희", birth="1991-02-02", survey_name="정기조사",
                          contract_start=date(2026, 8, 10), contract_end=date(2026, 8, 20),
                          contract_overridden=True),
        "c": TargetPerson(name="박민수", birth="", survey_name="정기조사",
                          contract_start=date(2026, 8, 1), contract_end=date(2026, 8, 31)),
    }


def test_restore_uses_current_survey_period_unless_overridden():
    contracts.remember(_people().values())
    fresh = {k: TargetPerson(name=p.name, birth=p.birth) for k, p in _people().items()}
    # 조사 기간이 9월 말까지 연장된 뒤 다음 달 계산
    contracts.restore(fresh, _config(end="2026-09-30"))

    a, b, c = fresh["a"], fresh["b"], fresh["c"]
    assert (a.survey_name, a.contract_end, a.contract_overridden, a.contract_restored) == \
        ("정기조사", date(2026, 9, 30), False, True)
    assert (b.contract_start, b.contract_end, b.contract_overridden) == \
        (date(2026, 8, 10), date(2026, 8, 20), True)
    # 생년월일이 없는 사람은 저장도 복원도 하지 않는다
    assert c.survey_name is None and not c.contract_restored


def test_restore_falls_back_to_saved_dates_when_survey_deleted():
    contracts.remember(_people().values())
    fresh = {"a": TargetPerson(name="김철수", birth="1990-01-01")}
    contracts.restore(fresh, Config({}))
    assert fresh["a"].contract_end == date(2026, 8, 31)


def test_restore_without_file_is_noop():
    p = {"a": TargetPerson(name="김철수", birth="1990-01-01")}
    contracts.restore(p, _config())
    assert p["a"].survey_name is None
