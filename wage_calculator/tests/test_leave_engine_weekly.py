import sys
from pathlib import Path
from datetime import date, time, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import leave_engine
from core.models import build_event


def test_no_15h_reverification():
    """지각/조퇴/외출로 그 주 실근무시간 합계가 15시간 미만이어도, 결근·종일병가
    없이 매일 출근(개근)했으면 주휴가 발생해야 한다. 소정근로시간 15시간
    요건은 계약(주5일 8시간) 자체로 이미 충족되는 계약상 기준이지, 매주
    실제 근무시간으로 재검증할 대상이 아니다."""
    contract_start = date(2026, 7, 6)   # 월요일
    contract_end = date(2026, 8, 3)     # 월요일(첫 창이 계약 경계로 잘리지 않도록 충분히 김)
    events = []
    for i in range(5):
        d = contract_start + timedelta(days=i)
        # 09:00~15:45 사이 405분을 조퇴/외출로 공제 -> 실근무 75분/일, 주 합계 375분(6.25시간) < 900분(15시간)
        events.append(build_event("연가", d, time(9, 0), time(15, 45), 405))
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, events)
    first = windows[0]
    assert first.granted, f"15시간 미만이어도 개근이면 발생해야 하는데 미발생: {first.reason}"
    print("OK: test_no_15h_reverification")


def test_reaches_week_off_day_grants_last_week():
    """계약이 그 주 주휴일(7일 창의 명목상 종료일)까지 정확히 연장되면,
    그 다음 주 근무 예정이 없어도 주휴가 발생해야 한다
    (2021.4.7 행정해석 변경: 다음 주 근무 예정 여부는 무관)."""
    contract_start = date(2026, 7, 6)  # 월요일
    contract_end = date(2026, 7, 12)   # 일요일(이 7일 창의 나머지 마지막 날과 정확히 일치)
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, [])
    only_window = windows[0]
    assert only_window.granted, f"계약이 주휴일(일요일)까지 유지됐으면 발생해야 하는데: {only_window.reason}"
    print("OK: test_reaches_week_off_day_grants_last_week")


def test_friday_end_still_denies_last_week():
    """계약이 평소처럼 금요일(마지막 근무일)에 끝나면, 여전히 그 주는
    미발생이어야 한다(일반적인 계약 마지막 주 판정 결과는 바뀌지 않음)."""
    contract_start = date(2026, 7, 6)  # 월요일
    contract_end = date(2026, 7, 10)   # 금요일
    windows = leave_engine.compute_weekly_holiday_windows(contract_start, contract_end, [])
    only_window = windows[0]
    assert not only_window.granted, "계약이 금요일에 끝나면 그 주는 미발생이어야 함"
    assert only_window.reason == "근로관계가 그 주 주휴일까지 유지되지 않음(계약 종료로 주휴일 이전 근로관계 종료)", only_window.reason
    print("OK: test_friday_end_still_denies_last_week")


if __name__ == "__main__":
    test_no_15h_reverification()
    test_reaches_week_off_day_grants_last_week()
    test_friday_end_still_denies_last_week()
    print("ALL OK")
