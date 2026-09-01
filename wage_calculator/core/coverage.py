"""B파일(근무상황) 조회기간이 계약 시작월~계산월을 덮는지 월 단위로 검증.

왜 필요한가
------------
연가(월차) 발생과 주휴수당은 "계약 시작일부터" 누적 판정한다(leave_engine).
그런데 B파일에는 근무상황이 있었던 행만 들어 있고 조회기간 정보가 없어서,
어떤 달에 행이 하나도 없을 때 그것이

  (a) 그 달은 전원 만근이라 기록할 게 없었다
  (b) 애초에 그 달을 조회하지 않아 파일에 없다

중 무엇인지 파일만 봐서는 구분되지 않는다. 지금까지는 무조건 (a)로 보고
그 달을 만근 처리했기 때문에, 계약이 7~9월인 사람의 8월 급여를 계산하면서
8월 근무상황만 첨부하면 7월이 통째로 만근이 되어 연가가 그냥 발생하고
주휴 판정까지 오염됐다.

판정 기준
----------
현장 전제: 부서 단위로 뽑으면 어느 달이든 근무상황이 최소 한 건은 나온다.
따라서 B파일 전체(사람 구분 없이)에서 실제로 관측된 (연,월) 집합을 곧
"조회된 달"로 본다. 계산 대상자마다 [계약시작월 ~ min(계산월, 계약종료월)]
전 구간이 그 집합에 들어 있어야 하며, 하나라도 빠지면 계산을 진행하지 않고
계약 시작월부터 다시 조회해 달라고 안내한다.
"""
from . import date_utils


def _month_iter(start_ym, end_ym):
    y, m = start_ym
    end_y, end_m = end_ym
    while (y, m) <= (end_y, end_m):
        yield (y, m)
        m += 1
        if m > 12:
            y, m = y + 1, 1


def covered_months(giganje_rows) -> set:
    """B파일 전체 행의 사용기간에서 관측된 (연, 월) 집합.

    한 행의 사용기간이 여러 달에 걸치면(예: 2026-08-28~2026-09-02) 그 사이
    달을 모두 포함한다. 날짜를 읽을 수 없는 행은 조용히 건너뛴다(조회기간
    추정이 목적이라, 형식 오류 한 줄로 검증 자체를 실패시킬 이유가 없다).
    """
    months = set()
    for row in giganje_rows:
        date_field = row.get("사용기간(날짜)")
        if date_field is None or str(date_field).strip() == "":
            continue
        try:
            start_d, end_d = date_utils.parse_date_range(date_field)
        except (ValueError, TypeError):
            continue
        months.update(_month_iter((start_d.year, start_d.month), (end_d.year, end_d.month)))
    return months


def required_months(contract_start, contract_end, year: int, month: int) -> list:
    """이 사람의 계산에 근무상황이 반드시 있어야 하는 (연, 월) 목록.

    계약 시작월부터 계산월까지. 계약이 계산월보다 먼저 끝났으면 계약 종료월까지만.
    계약이 계산월 이후에 시작하면(이번 달 계산 대상이 아님) 빈 목록.
    """
    if contract_start is None or contract_end is None:
        return []
    start_ym = (contract_start.year, contract_start.month)
    end_ym = min((year, month), (contract_end.year, contract_end.month))
    if start_ym > end_ym:
        return []
    return list(_month_iter(start_ym, end_ym))


def find_coverage_gaps(people, giganje_rows, year: int, month: int) -> list:
    """계산 대상자별로 근무상황이 빠진 달을 찾는다.

    반환: [{"key", "name", "contract_start", "contract_end", "missing": [(연,월), ...]}, ...]
    담당조사(=계약기간) 미지정 인원은 이번 계산 대상이 아니므로 건너뛴다.
    """
    covered = covered_months(giganje_rows)
    gaps = []
    for key, person in people.items():
        if not (person.survey_name and person.contract_start and person.contract_end):
            continue
        missing = [ym for ym in required_months(person.contract_start, person.contract_end, year, month)
                   if ym not in covered]
        if missing:
            gaps.append({
                "key": key,
                "name": person.name,
                "contract_start": person.contract_start,
                "contract_end": person.contract_end,
                "missing": missing,
            })
    return gaps


def _fmt(ym) -> str:
    return f"{ym[0]}-{ym[1]:02d}"


def format_gap_message(gaps, giganje_rows, year: int, month: int) -> str:
    """계산 차단 안내문. 어느 달이 왜 필요한지와 다시 조회할 기간을 알려준다."""
    if not gaps:
        return ""
    covered = sorted(covered_months(giganje_rows))
    missing_all = sorted({ym for g in gaps for ym in g["missing"]})
    earliest = min((g["contract_start"].year, g["contract_start"].month) for g in gaps)
    names = sorted({g["name"] for g in gaps})
    name_text = ", ".join(names[:10]) + (f" 외 {len(names) - 10}명" if len(names) > 10 else "")
    return (
        "근무상황 파일에 빠진 달이 있어 계산을 진행할 수 없습니다.\n\n"
        f"- 근무상황 파일에서 확인된 달: {', '.join(_fmt(ym) for ym in covered) or '없음'}\n"
        f"- 빠진 달: {', '.join(_fmt(ym) for ym in missing_all)}\n"
        f"- 해당 대상자: {name_text}\n\n"
        "연가(월차) 발생과 주휴수당은 계약 시작일부터 누적으로 판정하기 때문에,\n"
        "빠진 달은 '전원 만근'으로 잘못 처리되어 연가·주휴가 실제보다 많이 잡힙니다.\n\n"
        "다음 중 하나로 채우세요.\n"
        "1) 전월에 이 프로그램으로 만든 임금내역 파일을 '전월 임금내역'으로 함께 첨부합니다\n"
        "   (그 파일의 '근무상황(기간제)' 시트가 지난 달 근무상황을 그대로 담고 있습니다).\n"
        f"2) e-사람에서 {_fmt(earliest)}부터 {_fmt((year, month))}까지 전체 기간의 근무상황을\n"
        "   다시 조회해 첨부합니다."
    )
