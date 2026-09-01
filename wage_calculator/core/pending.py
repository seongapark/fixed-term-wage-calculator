"""확인 화면에 올릴 건을 모으고, 사람이 고른 판정을 이벤트·원본 행에 적용한다.

화면(webapp)이 아니라 여기에 두는 이유: 판정 규칙은 화면과 무관한 순수 로직이고,
전월 결과파일에서 판정을 복원하는 파서(core/parser.py)도 같은 열 이름·값을 써야
하기 때문이다.

확인 화면에 올라오는 건은 두 종류다.
  1) 종별이 9종에 없는 건 - 규칙이 아무것도 정해주지 못하므로 기본값 없이 올린다.
  2) 인식된 종별이지만 사유·비고에 값이 있는 건 - 특별한 사정이 적혀 있을 수
     있으므로 사람이 한 번 본다. 규칙이 정한 값을 기본값으로 채워 올린다.

전월 결과파일에서 판정을 이어받은 건(event.decided)은 다시 묻지 않는다.
"""
from . import mapping

PAID_COL = "지급판정"
ACCRUAL_COL = "주휴연가판정"

PAID_YES = "유급"
PAID_NO = "무급"
ACCRUAL_YES = "발생"
ACCRUAL_NO = "미발생"


def _has_text(value) -> bool:
    return value is not None and str(value).strip() != ""


def needs_confirmation(event) -> bool:
    """이 이벤트를 확인 화면에 올려야 하는가."""
    if event.decided:
        return False
    if mapping.is_pending(event.classified):
        return True
    row = event.source_row or {}
    return _has_text(row.get("사유")) or _has_text(row.get("비고"))


def collect_groups(people) -> list:
    """people(dict[key, TargetPerson]) 전체에서 확인 대상 이벤트를 원본 행 단위로 묶는다.

    원본 B파일 행 1개가 그룹 1개다(여러 날로 펼쳐진 이벤트는 한 그룹). 원본 행
    참조가 없는 이벤트(테스트용으로 직접 만든 경우)는 (사용기간, 종별)로 묶는다.
    """
    groups = {}
    order = []
    for key, person in people.items():
        for e in person.events:
            if not needs_confirmation(e):
                continue
            gkey = (key, id(e.source_row)) if e.source_row is not None else (key, e.source_range, e.raw_category)
            if gkey not in groups:
                row = e.source_row or {}
                known = not mapping.is_pending(e.classified)
                groups[gkey] = {
                    "person_key": key,
                    "person_name": person.name,
                    "raw_category": e.raw_category,
                    "classified": e.classified,
                    "start": e.source_range[0],
                    "end": e.source_range[1],
                    "reason": str(row.get("사유") or ""),
                    "note": str(row.get("비고") or ""),
                    "events": [],
                    "row": e.source_row,
                    # 인식된 종별만 규칙이 답을 갖고 있다. 미인식 종별은 기본값 없이 올린다.
                    "default_paid": (not e.unpaid) if known else None,
                    "default_accrual": (not e.breaks) if known else None,
                    "paid": None,
                    "accrual": None,
                }
                order.append(gkey)
            groups[gkey]["events"].append(e)
    return [groups[k] for k in order]


def apply_decisions(groups, decisions) -> None:
    """사람이 고른 판정을 이벤트의 두 축과 원본 행에 적용한다.

    decisions: [{"paid": bool, "accrual": bool}, ...] - groups와 같은 순서·개수.

    인식된 9종의 classified는 덮어쓰지 않는다. 덮어쓰면 "연가"의 잔량 소진처럼
    종별로만 결정되는 성질이 사라진다. 미인식 종별만 표시용으로 유급/무급
    특별휴가로 바꾼다(비고 문구와 공가 합산에 쓰인다).
    """
    if len(decisions) != len(groups):
        raise ValueError("판정 값 개수가 대기 중인 건수와 맞지 않습니다.")
    for decision in decisions:
        if decision.get("paid") is None or decision.get("accrual") is None:
            raise ValueError("모든 건에 유급/무급과 주휴·연가 발생 여부를 지정해야 진행할 수 있습니다.")

    for group, decision in zip(groups, decisions):
        paid = bool(decision["paid"])
        accrual = bool(decision["accrual"])
        group["paid"] = paid
        group["accrual"] = accrual
        for e in group["events"]:
            e.unpaid = not paid
            e.breaks = not accrual
            e.decided = True
            if mapping.is_pending(e.classified):
                e.classified = "유급특별휴가" if paid else "무급특별휴가"
        row = group["row"]
        if row is not None:
            row[PAID_COL] = PAID_YES if paid else PAID_NO
            row[ACCRUAL_COL] = ACCRUAL_YES if accrual else ACCRUAL_NO


def is_decided(groups) -> bool:
    """모든 건에 판정이 들어갔는가(계산 진행 가능 여부)."""
    return all(g["paid"] is not None and g["accrual"] is not None for g in groups)
