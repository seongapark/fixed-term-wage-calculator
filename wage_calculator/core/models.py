from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional, Tuple

from . import mapping


@dataclass
class LeaveEvent:
    """근무상황 원본 1행이 펼쳐진, 특정 하루에 대한 사건 1건.

    급여·만근 처리는 종별 문자열이 아니라 아래 두 축이 결정한다. 규칙이 채우는
    값과 사람이 확인 화면에서 채우는 값이 같은 모양이라, 엔진은 둘을 구분하지
    않는다.
    """
    raw_category: str
    classified: str          # 9종 중 하나 / 특별휴가_미정 / 유급특별휴가 / 무급특별휴가
    d: date
    is_time_based: bool
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    minutes: int = 0          # 조퇴/외출/지각/기타 공제 분
    day_weight: float = 1.0   # 종일 기준 일수(반일연가=0.5, 시간 기재=0)
    unpaid: bool = False      # 그 시간·일수를 급여에서 깎는가(식대도 종일이면 같이 빠진다)
    breaks: bool = False      # 그날을 실근무 0분으로 보는가(주휴·연가 만근이 깨진다)
    decided: bool = False     # 전월 결과파일에서 사람 판정을 이어받았는가(확인 화면에 다시 올리지 않는다)
    source_range: Optional[Tuple[date, date]] = None  # (원본 B파일 행의 사용기간 시작일, 종료일)
    source_row: Optional[dict] = None                 # 원본 B파일 행 dict 참조(확인 화면이 판정을 되쓴다)


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


def build_event(raw_category: str, d: date, time_start=None, time_end=None, minutes: int = 0,
                source_range=None, source_row=None) -> LeaveEvent:
    classified = mapping.classify(raw_category)
    # 사용시간(시분)이 실제로 기재된 행이면 종별 무관하게 시간공제 대상이다.
    time_based = time_start is not None
    weight = 0.0 if time_based else mapping.full_day_weight(raw_category)
    unpaid = classified in mapping.UNPAID
    # 종일(시간 미기재)로 찍힌 결근·일반병가·기타만 그날을 통째로 비운 것으로 본다.
    # 시간 기재 건이 8시간을 다 채우는지는 leave_engine이 분 단위로 따로 판정한다.
    breaks = (not time_based) and classified in mapping.BREAKS_WHEN_FULL_DAY
    return LeaveEvent(
        raw_category=raw_category,
        classified=classified,
        d=d,
        is_time_based=time_based,
        time_start=time_start,
        time_end=time_end,
        minutes=minutes if time_based else 0,
        day_weight=weight,
        unpaid=unpaid,
        breaks=breaks,
        source_range=source_range or (d, d),
        source_row=source_row,
    )
