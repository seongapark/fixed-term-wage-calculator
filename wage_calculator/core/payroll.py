"""5-4/5-5: 급여계산기간 산출 + 급여 항목 전체 계산."""
import math
from dataclasses import dataclass, field
from datetime import date

from . import date_utils, leave_engine


def round_down(x, unit=1):
    return math.floor(x / unit) * unit


@dataclass
class PayrollResult:
    name: str
    birth: str
    ssn: str
    bank: str
    account: str
    survey_name: str
    period_start: date
    period_end: date
    contract_start: date
    contract_end: date
    daily_wage: int
    actual_workdays: int      # 실출근(일)
    public_leave_days: float  # 공가(일)
    paid_holiday_days: int    # 유급휴일(일)
    absence_days: float       # (결근)
    total_days: float         # 계(일)
    late_out_minutes: int     # 조퇴외출 공제 분(내부 계산용, 임금내역엔 시간으로 환산되어 표시됨)
    weekly_holiday_days: int  # 주휴(일)
    calendar_month_days: int  # 월력상
    meal_eligible_days: float # 식대해당일
    remaining_leave_days: float  # 잔여연가(일)
    is_final_month: bool
    gross_pay: int             # 급여액
    late_out_deduction: int    # 조퇴외출공제
    base_pay: int               # 기본급
    weekly_holiday_pay: int     # 주휴수당
    meal_allowance: int         # 정액급식비
    leave_compensation: int     # 연가보상비
    total_payment: int          # 지급총액
    weekly_windows: list = field(default_factory=list)
    monthly_windows: list = field(default_factory=list)
    late_out_events: list = field(default_factory=list)
    special_leave_events: list = field(default_factory=list)
    special_leave_note: str = ""
    leave_offset_minutes: int = 0
    leave_shortfall_minutes: int = 0
    leave_shortfall: bool = False
    leave_offset_map: dict = field(default_factory=dict)


def compute_pay_period(contract_start: date, contract_end: date, year: int, month: int):
    month_first = date(year, month, 1)
    month_last = date(year, month, date_utils.month_calendar_days(month_first))
    period_start = max(month_first, contract_start)
    period_end = min(month_last, contract_end)
    return period_start, period_end, month_last


def calc_payroll(person, config, year: int, month: int) -> PayrollResult:
    contract_start = person.contract_start
    contract_end = person.contract_end
    period_start, period_end, month_last = compute_pay_period(contract_start, contract_end, year, month)

    daily_wage = config.daily_wage_for(year)
    daily_meal = round_down(config.meal_allowance_for(year) / 209 * 8, 1)

    period_events = [e for e in person.events if period_start <= e.d <= period_end]

    public_leave_days = sum(e.day_weight for e in period_events if e.classified in ("공가", "유급특별휴가"))
    absence_days = sum(e.day_weight for e in period_events if e.classified in ("결근", "무급특별휴가"))
    special_leave_events = [e for e in period_events if e.classified in ("유급특별휴가", "무급특별휴가")]

    holidays = config.holidays_in_range(period_start.isoformat(), period_end.isoformat())
    paid_holiday_days = len(holidays)

    workdays = date_utils.networkdays(period_start, period_end)
    actual_workdays = workdays - public_leave_days - (paid_holiday_days + absence_days)
    total_days = actual_workdays + paid_holiday_days + public_leave_days

    monthly_windows = leave_engine.compute_monthly_leave_windows(contract_start, contract_end, person.events)
    consumption = leave_engine.simulate_leave_consumption(monthly_windows, person.events)
    offset_map = consumption.offset_by_id
    leave_engine.build_leave_ledger(monthly_windows, offset_map)
    balance_minutes = leave_engine.leave_balance_minutes_as_of(monthly_windows, period_end, offset_map)
    remaining_leave_days = balance_minutes / 480

    late_out_events = [e for e in period_events if e.is_time_based]
    # 급여 공제분 = 전체 시간공제분 - 연가로 상계된 조퇴/외출/지각 분
    gita_covered = sum(
        offset_map.get(id(e), 0)
        for e in late_out_events if e.classified == "기타"
    )
    late_out_minutes = sum(e.minutes for e in late_out_events) - gita_covered
    gita_used = sum(e.minutes for e in late_out_events if e.classified == "기타")
    leave_offset_minutes = gita_covered
    leave_shortfall_minutes = gita_used - gita_covered
    leave_shortfall = leave_shortfall_minutes > 0

    weekly_windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, person.events)
    weekly_holiday_days = leave_engine.weekly_holidays_for_month(weekly_windows, year, month)

    calendar_month_days = date_utils.month_calendar_days(month_last)
    period_total_days = (period_end - period_start).days + 1
    meal_eligible_days = period_total_days - absence_days

    is_final_month = period_end == contract_end

    gross_pay = daily_wage * total_days
    # late_out_minutes(분단위)는 내부적으로 그대로 유지해 공제액을 분단위로 정확히
    # 계산한다(시간 단위 반올림 금지). 임금내역 "조퇴외출(시간)" 컬럼에는 가독성을
    # 위해 output/wage_sheet.py에서 시간(소수) 단위로 환산해 표시한다.
    late_out_deduction = round_down((config.daily_wage_for(year) / 8 / 60) * late_out_minutes, 10)
    base_pay = round_down(gross_pay - late_out_deduction, 10)
    weekly_holiday_pay = daily_wage * weekly_holiday_days
    meal_allowance = round_down(daily_meal_allowance(config, year, meal_eligible_days, calendar_month_days), 10)
    leave_compensation = round_down((daily_wage + daily_meal) * remaining_leave_days, 1) if is_final_month else 0
    total_payment = round_down(base_pay + weekly_holiday_pay + meal_allowance + leave_compensation, 10)

    return PayrollResult(
        name=person.name, birth=person.birth, ssn=person.ssn, bank=person.bank, account=person.account,
        survey_name=person.survey_name or "",
        period_start=period_start, period_end=period_end,
        contract_start=contract_start, contract_end=contract_end,
        daily_wage=daily_wage,
        actual_workdays=actual_workdays, public_leave_days=public_leave_days,
        paid_holiday_days=paid_holiday_days, absence_days=absence_days,
        total_days=total_days, late_out_minutes=late_out_minutes,
        weekly_holiday_days=weekly_holiday_days, calendar_month_days=calendar_month_days,
        meal_eligible_days=meal_eligible_days, remaining_leave_days=remaining_leave_days,
        is_final_month=is_final_month,
        gross_pay=gross_pay, late_out_deduction=late_out_deduction, base_pay=base_pay,
        weekly_holiday_pay=weekly_holiday_pay, meal_allowance=meal_allowance,
        leave_compensation=leave_compensation, total_payment=total_payment,
        weekly_windows=weekly_windows, monthly_windows=monthly_windows,
        late_out_events=late_out_events,
        special_leave_events=special_leave_events,
        special_leave_note=_format_special_leave_note(special_leave_events),
        leave_offset_minutes=leave_offset_minutes,
        leave_shortfall_minutes=leave_shortfall_minutes,
        leave_shortfall=leave_shortfall,
        leave_offset_map=offset_map,
    )


def _format_special_leave_note(events) -> str:
    """특별휴가 이벤트 목록을 (유급/무급 구분 + 날짜) 비고 텍스트로 요약.
    같은 원본 행(source_range)에서 나온 이벤트는 한 항목으로 묶는다.
    그룹은 각 그룹의 최초 날짜 기준으로 정렬해, B파일 행 순서와 무관하게
    항상 날짜 순으로 출력되게 한다."""
    groups = {}
    order = []
    for e in events:
        key = (e.classified, e.source_range)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e.d)
    order.sort(key=lambda key: min(groups[key]))
    parts = []
    for classified, source_range in order:
        label = "유급" if classified == "유급특별휴가" else "무급"
        dates = sorted(groups[(classified, source_range)])
        # 날짜가 전부 연속(하루 간격)일 때만 "~" 범위로 표시한다. 주말이 낀
        # 경우처럼 중간이 비면 실제 사용일만 콤마로 나열해, 쉬지 않은 날까지
        # 포함된 것처럼 보이는 걸 막는다.
        contiguous = all(
            (dates[i] - dates[i - 1]).days == 1 for i in range(1, len(dates))
        )
        if len(dates) == 1:
            date_text = f"{dates[0].month}/{dates[0].day}"
        elif contiguous:
            start, end = dates[0], dates[-1]
            date_text = f"{start.month}/{start.day}~{end.month}/{end.day}"
        else:
            date_text = ", ".join(f"{d.month}/{d.day}" for d in dates)
        parts.append(f"특별휴가({label}) {date_text}")
    return ", ".join(parts)


def daily_meal_allowance(config, year, meal_eligible_days, calendar_month_days):
    return config.meal_allowance_for(year) * meal_eligible_days / calendar_month_days
