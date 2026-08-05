"""날짜/시간 파싱 및 분단위 계산 유틸. 근무관리 전체 단위는 1분(반올림 없음)."""
from datetime import date, datetime, time, timedelta


def parse_date(s):
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()


def parse_date_range(s):
    """'YYYY-MM-DD' 또는 'YYYY-MM-DD~YYYY-MM-DD' -> (start_date, end_date)"""
    if isinstance(s, (date, datetime)):
        d = parse_date(s)
        return d, d
    text = str(s).strip()
    if "~" in text:
        a, b = text.split("~", 1)
        return parse_date(a.strip()), parse_date(b.strip())
    return parse_date(text), parse_date(text)


def parse_time(s):
    if isinstance(s, datetime):
        return s.time()
    if isinstance(s, time):
        return s
    text = str(s).strip()
    h, m = text.split(":")
    return time(int(h), int(m))


def parse_time_range(s):
    """'HH:MM~HH:MM' -> (start_time, end_time). 빈 값이면 None."""
    if s is None or str(s).strip() == "":
        return None
    text = str(s).strip()
    a, b = text.split("~", 1)
    return parse_time(a.strip()), parse_time(b.strip())


def minutes_between(t1: time, t2: time) -> int:
    return (t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)


LUNCH_START = time(12, 0)
LUNCH_END = time(13, 0)


def deduct_minutes(start: time, end: time) -> int:
    """조퇴/지각/외출 공제 분(分). 점심시간(12~13시)과 겹치는 구간은 원래 무급
    휴게시간이라 공제 대상에서 제외한다(전체를 감싸는 경우뿐 아니라, 점심시간
    중간에 걸치거나 그 안에서 시작/종료하는 경우도 겹치는 만큼만 뺀다)."""
    total = minutes_between(start, end)
    overlap_start = max(start, LUNCH_START)
    overlap_end = min(end, LUNCH_END)
    if overlap_start < overlap_end:
        total -= minutes_between(overlap_start, overlap_end)
    return max(total, 0)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def networkdays(start: date, end: date) -> int:
    """월~금 일수 (양끝 포함, start > end면 0)"""
    if start > end:
        return 0
    days = (end - start).days + 1
    full_weeks, rem = divmod(days, 7)
    count = full_weeks * 5
    for i in range(rem):
        wd = (start + timedelta(days=full_weeks * 7 + i)).weekday()
        if wd < 5:
            count += 1
    return count


def add_months(d: date, months: int) -> date:
    """월 단위 이동, 말일 보정 없이 '같은 날짜'로 이동(31일 등 없는 달은 말일로 보정)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_calendar_days(d: date) -> int:
    import calendar
    return calendar.monthrange(d.year, d.month)[1]


_CENTURY_BY_GENDER_DIGIT = {
    "1": 1900, "2": 1900, "5": 1900, "6": 1900,
    "3": 2000, "4": 2000, "7": 2000, "8": 2000,
    "9": 1800, "0": 1800,
}


def birth_from_ssn(ssn: str) -> str:
    """주민등록번호 앞 7자리로 생년월일(YYYY-MM-DD)을 역산한다.

    B파일(근무상황)에는 생년월일만 있고 주민번호가 없어, 전월 임금내역
    파일(주민번호만 있음)의 사람을 당월 B파일과 매칭할 때(소급계산의
    완전퇴사자 처리) 사용한다."""
    digits = str(ssn).replace("-", "").strip()
    if len(digits) < 7 or not digits[:7].isdigit():
        raise ValueError(f"주민번호 형식이 올바르지 않습니다: {ssn!r}")
    yy, mm, dd, gender_digit = digits[0:2], digits[2:4], digits[4:6], digits[6]
    century = _CENTURY_BY_GENDER_DIGIT.get(gender_digit)
    if century is None:
        raise ValueError(f"주민번호 성별 구분 숫자가 올바르지 않습니다: {ssn!r}")
    year = century + int(yy)
    return f"{year:04d}-{mm}-{dd}"


def previous_month(year: int, month: int) -> tuple:
    """(year, month)의 바로 전 달을 (year, month) 튜플로 반환. 1월의 전월은
    전년도 12월(연도 경계 처리)."""
    if month == 1:
        return year - 1, 12
    return year, month - 1
