"""5-1(주휴)·5-3(연가) 판정 로직. 두 판정 모두 동일한 '깨는 사유' 규칙을 공유한다."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from . import date_utils


@dataclass
class WeeklyWindowResult:
    index: int
    start: date
    end: date            # 창의 명목상 종료일(계약기간을 넘어가도 이 값 유지)
    effective_end: date  # 실제 판정에 사용한 종료일(계약마지막일로 잘릴 수 있음)
    workdays: int
    absence_days: int
    public_leave_days: int
    sick_full_days: int
    granted: bool
    reason: str           # 미발생 사유(발생 시 "발생")
    accrual_month: int
    accrual_year: int


@dataclass
class MonthlyWindowResult:
    index: int
    start: date
    end: date
    effective_end: date
    truncated: bool
    full_attendance: bool
    accrued: bool          # 연가 1일 발생 여부
    usage_events: list = field(default_factory=list)  # 구간 내 연가/반일연가 사용 이벤트
    cum_balance_minutes: int = 0  # 구간 종료 시점 누적 잔여(분)


def _events_in_range(events, start: date, end: date):
    return [e for e in events if start <= e.d <= end]


def _worked_minutes_by_day(window_events, w_start: date, eff_end: date) -> dict:
    """창 내 월~금 각 날짜의 실근무시간(분). 전일 결근/병가(종일)는 0분,
    그 외 날은 소정근로 480분에서 그날의 조퇴/지각/외출(시간 기재분, 사유 무관 -
    "기타"로 등록된 경우 포함) 공제분만큼만 뺀다. 8시간(480분) 전부가 공제되면
    그날은 사실상 출근하지 않은 것과 같아 0분으로 처리된다."""
    by_day = {}
    for d in date_utils.daterange(w_start, eff_end):
        if d.weekday() >= 5:
            continue
        day_events = [e for e in window_events if e.d == d]
        full_day_off = any(
            e.classified in ("결근", "병가") and not e.is_time_based for e in day_events
        )
        if full_day_off:
            by_day[d] = 0
        else:
            deducted = sum(e.minutes for e in day_events if e.is_time_based)
            by_day[d] = max(480 - deducted, 0)
    return by_day


def compute_weekly_holiday_windows(contract_start: date, contract_end: date, events) -> List[WeeklyWindowResult]:
    """5-1: 계약시작일 요일 기준 7일 창을 계약기간 끝까지 반복 판정.

    주휴 발생 조건: 창의 월~금 5일이 모두 실근무(1분이라도 근무, 결근/종일병가나
    8시간 전부를 조퇴 등으로 비운 날이 없어야 함) + 근로관계가 그 주 주휴일까지
    유지(계약 종료로 창이 주휴일 이전에 잘리지 않아야 함, 2021.4.7 행정해석
    변경 반영 - 다음 주 근무 예정 여부는 무관)가 모두 만족될 때만 발생한다.
    소정근로시간 15시간 이상 요건은 계약 자체(주5일 8시간)로 이미 충족되므로
    주 단위로 재검증하지 않는다.
    """
    results = []
    idx = 1
    w_start = contract_start
    while w_start <= contract_end:
        nominal_end = w_start + timedelta(days=6)
        eff_end = min(nominal_end, contract_end)
        window_events = _events_in_range(events, w_start, eff_end)

        workdays = date_utils.networkdays(w_start, eff_end)
        absence_days = sum(e.day_weight for e in window_events if e.classified == "결근")
        public_leave_days = sum(e.day_weight for e in window_events if e.classified == "공가")
        sick_full_days = sum(
            1 for e in window_events if e.classified == "병가" and not e.is_time_based
        )

        by_day = _worked_minutes_by_day(window_events, w_start, eff_end)
        worked_days = sum(1 for m in by_day.values() if m > 0)
        reaches_week_off_day = eff_end == nominal_end

        granted = True
        reason = "발생"
        if workdays < 5:
            granted, reason = False, "근무일수 5일 미만"
        elif worked_days < 5:
            granted, reason = False, "실근무 없는 날 발생(결근·종일병가 또는 8시간 전부 공제)"
        elif not reaches_week_off_day:
            granted, reason = False, "근로관계가 그 주 주휴일까지 유지되지 않음(계약 종료로 주휴일 이전 근로관계 종료)"

        results.append(WeeklyWindowResult(
            index=idx, start=w_start, end=nominal_end, effective_end=eff_end,
            workdays=workdays, absence_days=int(absence_days),
            public_leave_days=int(public_leave_days), sick_full_days=sick_full_days,
            granted=granted, reason=reason,
            accrual_month=eff_end.month, accrual_year=eff_end.year,
        ))
        idx += 1
        w_start = w_start + timedelta(days=7)
    return results


def weekly_holidays_for_month(windows: List[WeeklyWindowResult], year: int, month: int) -> int:
    return sum(1 for w in windows if w.granted and w.accrual_year == year and w.accrual_month == month)


def _consumes_leave_candidate(event) -> bool:
    """연가 잔량을 소진하는 후보: 명시적 연가/반일연가 + 조퇴/외출/지각(시간 기재 '기타').

    결근은 제외한다. e-사람 "근무상황 종별 안내"표에는 결근이 연가일수 '공제'로
    되어 있으나 그것은 공무원 복무 기준이고, 여기서는 결근이 무단결근이라
    그날 일급·정액급식비를 아예 지급하지 않는다(payroll.absence_days).
    급여를 깎으면서 연가까지 깎으면 같은 하루로 두 번 불이익을 주게 되므로,
    결근은 급여에서만 처리하고 연가 잔량은 건드리지 않는다.
    """
    if event.classified in ("연가", "반일연가"):
        return True
    return event.is_time_based and event.classified == "기타"


def leave_usage_minutes(event, offset_map=None) -> int:
    """연가(월차) 잔량에서 차감되는 분(分).
    - 연가: 시간 기재면 그 분, 아니면 480(종일)
    - 반일연가: 240
    - 조퇴/외출/지각(시간 기재 '기타'): offset_map이 주어졌을 때만 그 사건의
      연가 상계분(covered)을 반환(=연가로 덮은 만큼만 연가를 소진). offset_map이
      없으면 0(하위호환).
    """
    if event.classified == "연가":
        return event.minutes if event.is_time_based else 480
    if event.classified == "반일연가":
        return 240
    if offset_map is not None and event.is_time_based and event.classified == "기타":
        return offset_map.get(id(event), 0)
    return 0


def compute_monthly_leave_windows(contract_start: date, contract_end: date, events) -> List[MonthlyWindowResult]:
    """5-3: 계약시작일과 같은 날짜의 전날까지를 1개월 만근구간으로 반복 판정.

    구간 종료 다음날부터 발생 연가 사용 가능 -> 발생 시점은 구간 index 자체로 충분히 표현되고,
    잔여연가는 payroll 계산 단계에서 특정 기준일까지의 발생/사용을 합산해 구한다.
    """
    results = []
    idx = 1
    w_start = contract_start
    while w_start <= contract_end:
        nominal_end = date_utils.add_months(w_start, 1) - timedelta(days=1)
        truncated = nominal_end > contract_end
        eff_end = min(nominal_end, contract_end)
        window_events = _events_in_range(events, w_start, eff_end)

        if truncated:
            full_attendance = False
            accrued = False
        else:
            # 5-3 만근도 5-1(주휴)과 동일 기준: 하루 통으로 빠진 날(실근무 0분 -
            # 결근·종일병가 또는 조퇴/외출로 8시간 전부 공제)이 하나도 없어야 만근.
            # 조퇴/지각/외출로 일부 시간만 비운 날은 출근한 날로 인정한다.
            by_day = _worked_minutes_by_day(window_events, w_start, eff_end)
            full_attendance = all(m > 0 for m in by_day.values())
            accrued = full_attendance

        usage = [e for e in window_events if _consumes_leave_candidate(e)]

        results.append(MonthlyWindowResult(
            index=idx, start=w_start, end=nominal_end, effective_end=eff_end,
            truncated=truncated, full_attendance=full_attendance, accrued=accrued,
            usage_events=usage,
        ))
        idx += 1
        w_start = nominal_end + timedelta(days=1)
    return results


def build_leave_ledger(windows: List[MonthlyWindowResult], offset_map=None) -> None:
    """각 구간의 cum_balance_minutes를 '그 구간이 실제로 끝나는 시점' 기준으로 채운다
    (증거자료용 진짜 이력 원장 - 특정 급여계산기간 마감일에 의해 잘리지 않음).
    """
    accrued_minutes = 0
    used_minutes = 0
    for w in windows:
        if w.accrued:
            accrued_minutes += 480
        for e in w.usage_events:
            used_minutes += leave_usage_minutes(e, offset_map)
        w.cum_balance_minutes = accrued_minutes - used_minutes


def leave_balance_minutes_as_of(windows: List[MonthlyWindowResult], as_of: date, offset_map=None) -> int:
    """as_of 날짜까지(포함) 발생 가능한 연가(구간 종료 다음날부터 가용) - 사용분(분).

    급여계산기간 마감일(as_of) 시점의 스냅샷 값으로, 7-4 증거자료의 구간별
    이력 원장(build_leave_ledger)과는 별개로 계산한다(진행 중인 구간은 아직
    발생분이 확정되지 않았으므로 미포함).
    """
    accrued_minutes = 0
    used_minutes = 0
    for w in windows:
        available_from = w.effective_end + timedelta(days=1)
        if w.accrued and available_from <= as_of:
            accrued_minutes += 480
        for e in w.usage_events:
            if e.d <= as_of:
                used_minutes += leave_usage_minutes(e, offset_map)
        if w.start > as_of:
            break
    return accrued_minutes - used_minutes


@dataclass
class LeaveConsumption:
    offset_by_id: dict = field(default_factory=dict)  # id(event) -> 연가로 상계된 분
    total_offset_minutes: int = 0


def simulate_leave_consumption(windows, events) -> LeaveConsumption:
    """계약 전체 이벤트를 날짜순으로 걸으며 조퇴/외출/지각(시간 기재 '기타')의
    연가 상계분을 산출한다.

    타임라인 항목의 정렬 키 (날짜, 종류):
      종류 0 = 발생(+480, available_from = 구간종료+1일)
      종류 1 = 명시적 연가/반일연가 소진(그대로 차감, 음수 허용)
      종류 2 = 조퇴/외출/지각 상계(그 시점 양의 잔량 한도 내에서만)
    같은 날짜면 발생 -> 명시적 연가 -> 조퇴/외출/지각 순으로 처리한다.
    """
    entries = []  # (date, kind, minutes, event_or_None)
    for w in windows:
        if w.accrued:
            entries.append((w.effective_end + timedelta(days=1), 0, 480, None))
    for e in events:
        if e.classified in ("연가", "반일연가"):
            entries.append((e.d, 1, leave_usage_minutes(e), e))
        elif e.is_time_based and e.classified == "기타":
            entries.append((e.d, 2, e.minutes, e))
    entries.sort(key=lambda x: (x[0], x[1]))

    balance = 0
    result = LeaveConsumption()
    for d, kind, minutes, e in entries:
        if kind == 0:
            balance += minutes
        elif kind == 1:
            balance -= minutes  # 명시적 연가: 잔량 부족해도 차감(기존 정책, 음수 허용)
        else:
            covered = min(minutes, max(balance, 0))
            result.offset_by_id[id(e)] = covered
            result.total_offset_minutes += covered
            balance -= covered
    return result
