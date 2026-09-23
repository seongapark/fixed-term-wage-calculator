"""대상자별 담당조사·계약기간을 %APPDATA%의 contracts.json에 기억해, 다음 달 계산 때
같은 사람(성명_생년월일)에게 자동으로 채워 준다.

일괄지정으로 들어간 사람은 담당조사 이름만 의미가 있다 - 기간은 불러올 때 현재
조사종류 설정에서 다시 가져와, 조사 기간이 연장되면 전원에게 그대로 반영된다.
개별 수정(contract_overridden)한 사람만 저장된 날짜를 그대로 쓴다.
"""
import json

from . import date_utils
from .paths import user_data_dir


def contracts_path():
    return user_data_dir() / "contracts.json"


def _key(person):
    # 생년월일이 없으면 동명이인과 섞일 수 있어 저장·복원 대상에서 뺀다.
    return f"{person.name}_{person.birth}" if person.birth else None


def load() -> dict:
    try:
        return json.loads(contracts_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def restore(people: dict, config) -> None:
    store = load()
    for person in people.values():
        rec = store.get(_key(person))
        if not rec:
            continue
        survey = config.get_survey(rec["survey"])
        if survey is not None and not rec.get("overridden"):
            start, end = survey["start"], survey["end"]
        else:
            # 개별 수정했거나, 조사종류가 설정에서 지워졌으면 저장된 날짜를 쓴다.
            start, end = rec["start"], rec["end"]
        person.survey_name = rec["survey"]
        person.contract_start = date_utils.parse_date(start)
        person.contract_end = date_utils.parse_date(end)
        person.contract_overridden = bool(rec.get("overridden"))
        person.contract_restored = True


def remember(people) -> None:
    """계산에 쓰인 사람들의 담당조사·계약기간을 저장한다. 이번 A파일에 없는 사람의
    기록은 지우지 않는다(휴직 등으로 한 달 빠졌다 돌아올 수 있다)."""
    store = load()
    for person in people:
        key = _key(person)
        if key and person.survey_name and person.contract_start and person.contract_end:
            store[key] = {
                "survey": person.survey_name,
                "start": person.contract_start.isoformat(),
                "end": person.contract_end.isoformat(),
                "overridden": getattr(person, "contract_overridden", False),
            }
    path = contracts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
