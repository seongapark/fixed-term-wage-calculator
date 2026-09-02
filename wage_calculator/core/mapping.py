"""근무상황 "종별" 판정.

기간제 조사관 근무상황의 처리 기준은 아래 9종으로 갈린다. 정규화(전각->반각,
앞뒤 공백 제거) 후 이 9개 또는 ALIASES의 표기와 **완전일치**할 때만 인식하고,
그 밖의 표기는 예외를 던지지 않고 전부 확인 화면으로 보낸다(사람이 유급/무급과
주휴·연가 발생을 고른다).

예전에는 청·지청별 표기 차이를 키워드 우선순위 규칙으로 흡수했다. 그 결과
조퇴·외출·지각이 기타와 같은 분류가 되어 "기타는 연가로 상계하지 않는다"를
표현할 수 없었다. 표기를 넓게 받아들이는 대신, 벗어나면 사람이 판단한다.

급여·만근 처리는 여기서 문자열로 결정되지 않는다. 이 모듈은 종별의 '성질'만
표로 제공하고, 실제 값은 models.build_event()가 이벤트의 두 축(unpaid/breaks)에
싣는다 - 사람이 확인 화면에서 채우는 값과 같은 모양이라야 엔진이 둘을 구분하지
않기 때문이다.
"""
import unicodedata

# 유급/무급이 종별만으로 정해지지 않아, 사람이 확인 화면에서 결정해야 하는 분류.
UNDETERMINED_SPECIAL = "특별휴가_미정"
PENDING_CLASSIFICATIONS = (UNDETERMINED_SPECIAL,)

# 사람이 고른 뒤 미인식 종별에만 덮어쓰는 표시용 분류(인식된 9종은 덮지 않는다).
DECIDED_SPECIAL = ("유급특별휴가", "무급특별휴가")

KNOWN_CATEGORIES = (
    "연가", "반일연가", "공가", "일반병가", "결근", "조퇴", "외출", "지각", "기타",
)

# 같은 처리를 받는 다른 표기. 오전/오후는 반차를 어느 쪽으로 쓰는지만 다를 뿐
# 급여·연가 처리가 완전히 같으므로(둘 다 240분 소진) "반일연가"로 모은다.
# 여기 없는 표기는 규칙으로 추정하지 않고 확인 화면으로 보낸다 - 이 표는
# 키워드 규칙이 아니라 **닫힌 목록**이라는 점이 중요하다.
ALIASES = {
    "반일연가(오전)": "반일연가",
    "반일연가(오후)": "반일연가",
}

# 그 시간·일수를 급여에서 깎는 종별(조퇴/외출/지각은 보유 연가로 상계된 만큼은 깎이지 않는다).
UNPAID = ("결근", "조퇴", "외출", "지각", "기타")

# 사용시간 없이 종일로 찍히면 그날을 실근무 0분으로 보는 종별(만근이 깨진다).
BREAKS_WHEN_FULL_DAY = ("결근", "일반병가", "기타")

# 시간 기재분이 보유 연가로 상계되는 종별.
OFFSETTABLE = ("조퇴", "외출", "지각")

# 보유 연가를 소진하거나 상계하는 종별 전체(연가·반일연가는 직접 소진).
LEAVE_CONSUMING = ("연가", "반일연가") + OFFSETTABLE


def normalize(raw_category) -> str:
    """전각->반각(NFKC) + 공백 전부 제거.

    인식하는 종별 표기에는 의미 있는 공백이 하나도 없다. 그래서 "반일연가 (오전)"
    처럼 청·지청마다 공백이 들어가도 같은 것으로 본다.

    괄호·쉼표 같은 구분자는 지우지 않는다 - 지우면 "조퇴(연가처리)"가 인식 목록
    어디에도 안 맞는다는 사실이 흐려진다(그건 사람이 판단할 건이다)."""
    try:
        text = str(raw_category or "")
    except Exception:
        return ""
    return "".join(unicodedata.normalize("NFKC", text).split())


def classify(raw_category) -> str:
    """종별 원문 -> 9종 중 하나 또는 "특별휴가_미정". 절대 예외를 던지지 않는다.

    원문 표기는 LeaveEvent.raw_category에 그대로 남는다(확인 화면·비고에 쓰인다).
    여기서 돌려주는 것은 처리 기준을 정하는 분류다."""
    normalized = normalize(raw_category)
    if normalized in KNOWN_CATEGORIES:
        return normalized
    if normalized in ALIASES:
        return ALIASES[normalized]
    return UNDETERMINED_SPECIAL


def is_pending(classified: str) -> bool:
    """사람이 판정해야 계산을 진행할 수 있는 분류인지."""
    return classified in PENDING_CLASSIFICATIONS


def full_day_weight(raw_category) -> float:
    """사용시간(시분) 미기재(종일) 항목의 일수 가중치(반일연가는 0.5일)."""
    return 0.5 if classify(raw_category) == "반일연가" else 1.0
