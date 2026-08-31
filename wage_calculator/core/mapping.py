"""근무상황 "종별" -> 내부 분류 매핑.

청·지청마다 종별을 적는 방식이 다르다. e-사람 안내표는 종별(대분류) +
세부선택(소분류) 2단 구조인데, 실제 B파일에는

  "일반병가"                      (종별만, 세부선택 생략)
  "일반병가(진단서미첨부)"        (종별+세부선택)
  "조퇴(일반병가,진단서미첨부)"   (상위 종별 + 세부선택 통째)
  "조퇴 (일반병가, 진단서 미첨부)" (공백/구분자만 다름)
  "지각(연가처리)" / "조퇴(연가)"  (같은 뜻, 표기만 다름)

처럼 제각각 찍혀 나온다. 그래서 예전처럼 문자열 완전일치 표 하나로는
지청 하나만 표기가 달라도 ValueError로 파일 로딩 전체가 죽었다.

지금은 2단계로 판정한다.
  1) normalize(): NFKC 정규화 후 한글/영숫자만 남긴다(괄호·쉼표·중점·공백·
     하이픈 등 구분자를 전부 제거) -> 표기 흔들림 흡수.
  2) classify_by_rules(): 정규화된 문자열에 어떤 키워드가 들어있는지를
     우선순위 순서대로 본다. 세부선택이 생략돼도, 반대로 통째로 붙어 있어도
     같은 결론이 나온다.

급여 처리 방식이 종별만으로 확정되는 것(결근/공가/연가/일반병가/기타)만
규칙으로 확정하고, **나머지는 전부 "특별휴가_미정"으로 보내 사람이 유급/무급을
직접 고르게 한다**. 경조사·출산·돌봄·포상 같은 휴가는 물론, 규칙에 걸리지 않는
처음 보는 종별도 마찬가지다. 임의로 추정해 조용히 잘못 지급하는 것을 막으면서,
표기가 하나 다르다고 진행이 막히지도 않게 하기 위함이다(예외를 던지지 않는다).

어디로 보낼지 애매한 종별은 e-사람 "근무상황 종별 안내"표의 **연가일수 공제여부**
칸을 기준으로 가른다(안내표 원본은 webapp/static/reference/leave_category_guide.json).
연가를 실제로 깎는 항목("공제": 연가·반일연가·지각/외출/조퇴(연가처리)·결근)만
전용 분류를 갖고, "미공제" 항목은 유급/무급이 종별만으로 정해지지 않으므로
확인 화면으로 보낸다 - 공무상병가와 관외여행이 이 기준으로 "특별휴가_미정"이다.
(다만 일반병가와 공가·기타는 급여 처리 규칙이 이미 확립돼 있어 전용 분류를 유지한다.)

실제 유급/무급 확정은 gui/special_leave_screen.py(웹은 webapp/state.py)에서
사람이 건별로 골라 LeaveEvent.classified를 "유급특별휴가"/"무급특별휴가"로
덮어써서 이뤄진다(이 모듈을 다시 타지 않음).

기간제는 조퇴/외출/지각을 세부 종별이 아니라 "기타"로 등록하는 경우가 있다.
그래서 시간공제 대상 여부는 종별 문자열이 아니라, 그 행에 실제 사용시간(시분)이
기재되어 있는지로 판정한다 - 판정 자체는 models.build_event()에서 이뤄지고,
이 모듈은 "시간 미기재(종일) 항목"일 때의 일수 가중치만 제공한다.
"""
import re
import unicodedata

# 유급/무급이 종별만으로 정해지지 않아, 사람이 확인 화면에서 결정해야 하는 분류.
UNDETERMINED_SPECIAL = "특별휴가_미정"
PENDING_CLASSIFICATIONS = (UNDETERMINED_SPECIAL,)

# 사람이 고른 뒤 덮어쓰는 최종 분류.
DECIDED_SPECIAL = ("유급특별휴가", "무급특별휴가")

_NON_WORD = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ]+")


def normalize(raw_category) -> str:
    """표기 흔들림 제거: 전각->반각(NFKC) 후 한글/영숫자 외 문자를 모두 버린다.

    "조퇴 (일반병가, 진단서 미첨부)" / "조퇴（일반병가·진단서미첨부）"
    / "조퇴-일반병가-진단서미첨부" -> 모두 "조퇴일반병가진단서미첨부".
    """
    s = unicodedata.normalize("NFKC", str(raw_category or ""))
    return _NON_WORD.sub("", s)


# --- 키워드 규칙 (위에서부터 먼저 걸리는 것이 이긴다) ---------------------------
#
# 순서가 곧 우선순위다.
#  - "공무상"을 '병가'보다 먼저 본다: "공무상병가"/"조퇴(공무상병가)"는 일반병가와
#    달리 유급/무급을 사람이 정하도록 확인 화면으로 보낸다.
#  - "조퇴(일반병가,진단서미첨부)"는 '병가'가 '조퇴'보다 먼저 걸려 병가가 된다.
#  - "지각(연가처리)"는 병가 키워드가 없으므로 연가로 내려간다.
#  - "공무상병가"에는 '공가'라는 연속 문자열이 없어 공가와 충돌하지 않는다.
#  - 어디에도 안 걸리면 "특별휴가_미정"(=사람이 유급/무급 결정).

_ABSENCE = ("결근",)
_OFFICIAL_INJURY = ("공무상",)
_SICK = ("병가", "질병")
_ANNUAL = ("연가",)
_PUBLIC = ("공가",)
# 관외여행은 안내표상 "기타"의 세부선택이지만, 유급/무급을 사람이 정하도록
# 확인 화면으로 보낸다. "기타(관외여행)"처럼 붙여 적는 청도 있으므로
# '기타'보다 먼저 본다.
_TRAVEL = ("관외여행",)
# 급여·주휴·연가 어디에도 영향 없는 정상 출근 취급 + 시간 기재 시 분단위 공제 대상.
_OTHER = ("기타", "조퇴", "외출", "지각")

# 반일연가 판정용.
_HALF_MARKERS = ("반일", "반차")
_HALF_TIME_MARKERS = ("오전", "오후")


def _has(s: str, keywords) -> bool:
    return any(k in s for k in keywords)


def classify_by_rules(normalized: str) -> str:
    """정규화된 종별 문자열 -> 분류. 어디에도 안 걸리면 "특별휴가_미정"."""
    if not normalized:
        return UNDETERMINED_SPECIAL
    if _has(normalized, _ABSENCE):
        return "결근"
    if _has(normalized, _OFFICIAL_INJURY):
        return UNDETERMINED_SPECIAL
    if _has(normalized, _SICK):
        return "병가"
    if _has(normalized, _ANNUAL):
        # 반일연가는 연가 잔량을 240분(4시간)만 소진하므로 별도 분류로 남긴다.
        # '오전/오후'만 붙은 경우도 반일로 본다 - 단, 조퇴/외출/지각은 그 자체가
        # 시간 기재 항목이라 실제 사용 분으로 계산되므로 반일 판정에서 뺀다.
        half = _has(normalized, _HALF_MARKERS) or (
            _has(normalized, _HALF_TIME_MARKERS) and not _has(normalized, _OTHER)
        )
        return "반일연가" if half else "연가"
    if _has(normalized, _PUBLIC):
        return "공가"
    if _has(normalized, _TRAVEL):
        return UNDETERMINED_SPECIAL
    if _has(normalized, _OTHER):
        return "기타"
    return UNDETERMINED_SPECIAL


# 대표 표기 예시표(문서용 + 빠른 조회). 실제 판정은 키워드 규칙이 하며,
# 이 표의 값이 규칙 결과와 어긋나지 않는지는 테스트가 고정한다.
CATEGORY_MAP = {
    "결근": "결근",
    "공가": "공가",
    "기타": "기타",
    "관외여행": UNDETERMINED_SPECIAL,   # 안내표상 연가일수 미공제 -> 유급/무급을 사람이 결정
    "조퇴": "기타",
    "외출": "기타",
    "지각": "기타",
    "연가": "연가",
    "반일연가(오전)": "반일연가",
    "반일연가(오후)": "반일연가",
    "조퇴(연가)": "연가",
    "외출(연가)": "연가",
    "지각(연가처리)": "연가",
    "외출(연가처리)": "연가",
    "조퇴(연가처리)": "연가",
    "일반병가": "병가",
    "공무상병가": UNDETERMINED_SPECIAL,   # 안내표상 연가일수 미공제 -> 유급/무급을 사람이 결정
    "일반병가(진단서미첨부)": "병가",
    "일반병가(진단서첨부)": "병가",
    "지각(일반병가,진단서미첨부)": "병가",
    "지각(일반병가,진단서첨부)": "병가",
    "지각(공무상병가)": UNDETERMINED_SPECIAL,
    "외출(일반병가,진단서미첨부)": "병가",
    "외출(일반병가,진단서첨부)": "병가",
    "외출(공무상병가)": UNDETERMINED_SPECIAL,
    "조퇴(일반병가,진단서미첨부)": "병가",
    "조퇴(일반병가,진단서첨부)": "병가",
    "조퇴(공무상병가)": UNDETERMINED_SPECIAL,
    "특별휴가": UNDETERMINED_SPECIAL,
    "경조사휴가": UNDETERMINED_SPECIAL,
    "사망(본인 및 배우자의 조부모·외조부모)": UNDETERMINED_SPECIAL,
    "자녀돌봄휴가": UNDETERMINED_SPECIAL,
    "가족돌봄휴가": UNDETERMINED_SPECIAL,
    "출산휴가(본인출산)": UNDETERMINED_SPECIAL,
    "대체휴무": UNDETERMINED_SPECIAL,
    "당직휴무": UNDETERMINED_SPECIAL,
    "선거휴무": UNDETERMINED_SPECIAL,
}

_NORMALIZED_MAP = {normalize(k): v for k, v in CATEGORY_MAP.items()}


def classify(raw_category) -> str:
    """종별 원문 -> 분류. 절대 예외를 던지지 않는다(못 알아보면 "특별휴가_미정")."""
    normalized = normalize(raw_category)
    if normalized in _NORMALIZED_MAP:
        return _NORMALIZED_MAP[normalized]
    return classify_by_rules(normalized)


def is_pending(classified: str) -> bool:
    """사람이 유급/무급을 확정해야 계산을 진행할 수 있는 분류인지."""
    return classified in PENDING_CLASSIFICATIONS


def full_day_weight(raw_category) -> float:
    """사용시간(시분) 미기재(종일) 항목의 일수 가중치(반일연가는 0.5일)."""
    return 0.5 if classify(raw_category) == "반일연가" else 1.0


def full_day_breaks(raw_category) -> bool:
    """(미사용) 종일 항목이 만근 판정을 깨는지 - LeaveEvent.breaks 설정용이었으나,
    현재 5-1(주휴)/5-3(연가) 판정 모두 그날 실근무 0분 여부(_worked_minutes_by_day)로
    통일되어 이 함수의 결과는 더 이상 소비되지 않는다.
    """
    return classify(raw_category) in ("결근", "병가")
