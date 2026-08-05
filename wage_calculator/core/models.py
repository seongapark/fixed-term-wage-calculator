from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional, Tuple

from . import mapping


@dataclass
class LeaveEvent:
    """근무상황 원본 1행이 펼쳐진, 특정 하루에 대한 사건 1건."""
    raw_category: str
    classified: str          # 결근/공가/기타/반일연가/병가/연가/특별휴가_미정/유급특별휴가/무급특별휴가
    d: date
    is_time_based: bool
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    minutes: int = 0          # 조퇴/지각/외출 공제 분
    day_weight: float = 1.0   # 종일 기준 일수(반일연가=0.5, 조퇴/지각/외출=0)
    breaks: bool = False      # 5-1/5-3 판정을 깨는 사유인지
    source_range: Optional[Tuple[date, date]] = None  # (원본 B파일 행의 사용기간 시작일, 종료일) - 같은 행에서 펼쳐진 이벤트 그룹 식별용


@dataclass
class Employee:
    """A파일(개인정보)."""
    name: str
    ssn: str
    bank: str
    account: str
    birth: str = ""  # A파일에 '생년월일' 컬럼이 있을 때만 채워짐(동명이인 구분용)


@dataclass
class TargetPerson:
    """계산 대상자 1명 (A+B 매칭 + 담당조사/계약기간)."""
    name: str
    dept: str = ""
    rank: str = ""
    birth: str = ""
    ssn: str = ""
    bank: str = ""
    account: str = ""
    survey_name: Optional[str] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    contract_overridden: bool = False
    events: list = field(default_factory=list)  # list[LeaveEvent]


def build_event(raw_category: str, d: date, time_start=None, time_end=None, minutes: int = 0, source_range=None) -> LeaveEvent:
    classified = mapping.classify(raw_category)
    # 사용시간(시분)이 실제로 기재된 행이면 종별(사유) 무관하게 시간공제 대상.
    # 기간제는 조퇴/외출/지각을 "기타"로 등록하는 경우가 있어, 종별 문자열이
    # 아니라 실제 시간값 유무로 판정해야 그런 행도 정확히 분단위 공제된다.
    time_based = time_start is not None
    weight = 0.0 if time_based else mapping.full_day_weight(raw_category)
    breaks = True if time_based else mapping.full_day_breaks(raw_category)
    return LeaveEvent(
        raw_category=raw_category,
        classified=classified,
        d=d,
        is_time_based=time_based,
        time_start=time_start,
        time_end=time_end,
        minutes=minutes if time_based else 0,
        day_weight=weight,
        breaks=breaks,
        source_range=source_range or (d, d),
    )
