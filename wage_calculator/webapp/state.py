"""tkinter GUI(gui/app.py)의 orchestration 로직을 이관한 상태 객체.

원본 App(tk.Tk)이 들고 있던 데이터와 메서드를 그대로 옮긴다 - 검증 규칙과
계산 흐름은 원본과 동일하게 유지하고, tkinter 위젯을 그리던 부분만 값을
반환하도록 바뀐다.
"""
from datetime import date
from pathlib import Path

from core import date_utils
from core.paths import downloads_dir
from output.build import (
    build_departed_workbook,
    build_workbook,
    departed_output_filename,
    output_filename,
)
from core.config import Config
from core.parser import (
    build_target_people,
    display_label,
    load_employees,
    load_giganje_rows,
    load_previous_payroll,
)
from core.payroll import calc_payroll
from core.retroactive import compute_retroactive

from core import leave_engine
from core.leave_engine import leave_usage_minutes
from core.parser import person_key


def collect_pending_groups(people):
    """people(dict[key, TargetPerson]) 전체에서 classified == "특별휴가_미정"인
    이벤트를 (person_key, source_range)로 묶어 그룹 목록을 만든다.

    반환: [{"person_key", "person_name", "start", "end", "events", "status"}, ...]
    status는 None(미정) / "유급특별휴가" / "무급특별휴가".
    """
    groups = {}
    order = []
    for key, person in people.items():
        for e in person.events:
            if e.classified != "특별휴가_미정":
                continue
            gkey = (key, e.source_range)
            if gkey not in groups:
                groups[gkey] = {
                    "person_key": key,
                    "person_name": person.name,
                    "start": e.source_range[0],
                    "end": e.source_range[1],
                    "events": [],
                    "status": None,
                }
                order.append(gkey)
            groups[gkey]["events"].append(e)
    return [groups[k] for k in order]


def _find_reason_note(giganje_rows, person_name, start, end):
    """원본 B파일 행에서 이 그룹과 같은 성명·기간의 사유/비고를 찾아 힌트로 보여준다
    (자동 판정에는 쓰지 않음 - 지역마다 기재 여부가 달라 참고용일 뿐)."""
    for row in giganje_rows:
        if str(row.get("성명") or "").strip() != person_name:
            continue
        if str(row.get("종별") or "").strip() != "특별휴가":
            continue
        date_field = row.get("사용기간(날짜)")
        if date_field is None:
            continue
        try:
            row_start, row_end = date_utils.parse_date_range(date_field)
        except (ValueError, TypeError):
            continue
        if row_start == start and row_end == end:
            return str(row.get("사유") or ""), str(row.get("비고") or "")
    return "", ""


class AppState:
    def __init__(self):
        self.config_obj = Config.load()
        self._reset_data()

    def _reset_data(self):
        self.employees = {}
        self.giganje_rows = []
        self.people = {}
        self.missing_names = []
        self.ambiguous_names = []
        self.work_year = None
        self.work_month = None
        self.results = []
        self.previous_payroll = {}
        self.retro_adjustments = {}
        self.retro_details = {}
        self.departed_results = []
        self.pending_leave_groups = []

    def reset(self):
        self._reset_data()

    def load_files(self, a_path, b_path, prev_payroll_path=None):
        self._reset_data()
        self.employees = load_employees(a_path)
        self.giganje_rows = load_giganje_rows(b_path)
        self.people, self.missing_names, self.ambiguous_names = build_target_people(
            self.giganje_rows, self.employees
        )
        self.previous_payroll = load_previous_payroll(prev_payroll_path) if prev_payroll_path else {}
        self.pending_leave_groups = collect_pending_groups(self.people)
        return {
            "ambiguous_names": list(self.ambiguous_names),
            "has_pending_special_leave": bool(self.pending_leave_groups),
        }

    def special_leave_groups(self):
        out = []
        for idx, g in enumerate(self.pending_leave_groups):
            reason, note = _find_reason_note(self.giganje_rows, g["person_name"], g["start"], g["end"])
            out.append({
                "index": idx,
                "person_name": g["person_name"],
                "start": g["start"].isoformat(),
                "end": g["end"].isoformat(),
                "reason": reason,
                "note": note,
                "status": g["status"],
            })
        return out

    VALID_SPECIAL_LEAVE_STATUSES = {"유급특별휴가", "무급특별휴가"}

    def confirm_special_leave(self, statuses):
        if len(statuses) != len(self.pending_leave_groups):
            raise ValueError("특별휴가 상태 값 개수가 대기 중인 건수와 맞지 않습니다.")
        if any(not s for s in statuses):
            raise ValueError("모든 건에 유급/무급을 지정해야 진행할 수 있습니다.")
        if any(s not in self.VALID_SPECIAL_LEAVE_STATUSES for s in statuses):
            raise ValueError("특별휴가 상태 값은 '유급특별휴가' 또는 '무급특별휴가'만 지정할 수 있습니다.")
        for g, status in zip(self.pending_leave_groups, statuses):
            g["status"] = status
            for e in g["events"]:
                e.classified = status

    def targets(self):
        all_names = [p.name for p in self.people.values()]
        out = []
        for key, person in self.people.items():
            out.append({
                "key": key,
                "label": display_label(person.name, person.birth, all_names),
                "survey_name": person.survey_name or "",
                "contract_start": person.contract_start.isoformat() if person.contract_start else "",
                "contract_end": person.contract_end.isoformat() if person.contract_end else "",
            })
        return out

    def survey_names(self):
        return self.config_obj.survey_names()

    def batch_assign(self, keys, survey_name):
        survey = self.config_obj.get_survey(survey_name)
        if survey is None:
            raise ValueError(f"등록되지 않은 담당조사입니다: {survey_name}")
        start = date_utils.parse_date(survey["start"])
        end = date_utils.parse_date(survey["end"])
        for key in keys:
            person = self.people[key]
            person.survey_name = survey_name
            person.contract_start = start
            person.contract_end = end
            person.contract_overridden = False

    def edit_contract(self, key, start, end):
        person = self.people[key]
        person.contract_start = date_utils.parse_date(start)
        person.contract_end = date_utils.parse_date(end)
        person.contract_overridden = True

    def prepare_calculation(self, year, month):
        """대상자 확인 화면의 '계산 실행' 검증. 통과하면 work_year/work_month를
        세팅하고 담당조사 미지정 인원 명단을 돌려준다(경고 표시용, 차단은 아님)."""
        if self.ambiguous_names:
            raise ValueError(
                "동명이인을 구분할 수 없는 대상자가 있어 계산을 진행할 수 없습니다: "
                + ", ".join(self.ambiguous_names)
            )
        if not (1 <= month <= 12):
            raise ValueError("급여산정 연/월을 올바르게 입력하세요.")
        if any(g["status"] is None for g in self.pending_leave_groups):
            raise ValueError("특별휴가 유급/무급을 먼저 지정해야 계산을 진행할 수 있습니다.")
        self.work_year = year
        self.work_month = month
        return [p.name for p in self.people.values() if not p.survey_name]

    def confirm_info(self):
        year, month = self.work_year, self.work_month
        month_first = date(year, month, 1)
        month_last = date(year, month, date_utils.month_calendar_days(month_first))
        holidays = self.config_obj.holidays_in_range(month_first.isoformat(), month_last.isoformat())
        overridden = [p.name for p in self.people.values() if p.contract_overridden]
        return {
            "year": year,
            "month": month,
            "holidays": holidays,
            "daily_wage": self.config_obj.daily_wage_for(year),
            "meal_allowance": self.config_obj.meal_allowance_for(year),
            "overridden_names": overridden,
        }

    def run_calculation(self):
        targets = [p for p in self.people.values() if p.survey_name and p.contract_start and p.contract_end]
        results = []
        errors = []
        for person in targets:
            try:
                results.append(calc_payroll(person, self.config_obj, self.work_year, self.work_month))
            except Exception as e:
                errors.append(f"{person.name}: {e}")
        self.results = results

        self.retro_adjustments = {}
        self.retro_details = {}
        self.departed_results = []
        if self.previous_payroll:
            prev_year, prev_month = date_utils.previous_month(self.work_year, self.work_month)
            try:
                retro = compute_retroactive(
                    self.people, self.previous_payroll, self.giganje_rows,
                    self.config_obj, prev_year, prev_month,
                )
                self.retro_adjustments = retro.adjustments
                self.retro_details = retro.details
                self.departed_results = retro.departed
                errors.extend(retro.errors)
            except Exception as e:
                errors.append(f"소급계산 오류: {e}")
        return errors

    def results_summary(self):
        all_names = [r.name for r in self.results]
        out = []
        for r in self.results:
            out.append({
                "key": person_key(r.name, r.birth),
                "label": display_label(r.name, r.birth, all_names),
                "survey": r.survey_name,
                "period": f"{r.period_start.isoformat()}~{r.period_end.isoformat()}",
                "total_days": r.total_days,
                "weekly_holiday_days": r.weekly_holiday_days,
                "remaining_leave_days": round(r.remaining_leave_days, 2),
                "total_payment": r.total_payment,
            })
        return out

    def evidence_names(self):
        all_names = [r.name for r in self.results]
        return [
            {"key": person_key(r.name, r.birth), "label": display_label(r.name, r.birth, all_names)}
            for r in self.results
        ]

    def _result_by_key(self, key):
        for r in self.results:
            if person_key(r.name, r.birth) == key:
                return r
        return None

    def evidence_for(self, key):
        result = self._result_by_key(key)
        if result is None:
            return None

        raw_rows = []
        for row in self.giganje_rows:
            if row["성명"] != result.name:
                continue
            # A파일에 생년월일이 없어서(선택 컬럼) result.birth가 빈 값인 경우는
            # 이름만으로 매칭한다 - core/parser.py의 build_target_people()이
            # 동명이인이 없는 사람은 이미 이름만으로 B파일 행을 붙이는 것과
            # 동일한 기준이다(계산 엔진이 이미 그렇게 신뢰하고 있으므로, 산정근거
            # 화면만 더 엄격하게 굴어서 원본을 못 보여줄 이유가 없다).
            if result.birth:
                row_birth = row.get("생년월일")
                if row_birth is None or str(row_birth).strip() == "":
                    continue
                try:
                    if date_utils.parse_date(row_birth).isoformat() != result.birth:
                        continue
                except ValueError:
                    continue
            raw_rows.append({
                "category": row.get("종별") or "",
                "period": row.get("사용기간(날짜)") or "",
                "time": row.get("사용시간(시분)") or "",
                "reason": row.get("사유") or "",
                "note": row.get("비고") or "",
            })

        weekly = [{
            "index": w.index,
            "start": w.start.isoformat(),
            "effective_end": w.effective_end.isoformat(),
            "workdays": w.workdays,
            "absence_days": w.absence_days,
            "public_leave_days": w.public_leave_days,
            "sick_full_days": w.sick_full_days,
            "granted": w.granted,
            "reason": w.reason,
        } for w in result.weekly_windows]

        late_out = [{
            "date": e.d.isoformat(),
            "category": e.raw_category,
            "start": e.time_start.strftime("%H:%M"),
            "end": e.time_end.strftime("%H:%M"),
            "lunch_included": "포함" if (e.time_start < date_utils.LUNCH_START and e.time_end > date_utils.LUNCH_END) else "미포함",
            "minutes": e.minutes,
        } for e in result.late_out_events]

        total_days = (result.period_end - result.period_start).days + 1
        meal = {
            "period_start": result.period_start.isoformat(),
            "period_end": result.period_end.isoformat(),
            "total_days": total_days,
            "absence_days": result.absence_days,
            "meal_eligible_days": result.meal_eligible_days,
        }

        leave_rows = []
        for w in result.monthly_windows:
            if w.start > result.period_end:
                continue
            usage_text = ", ".join(
                f"{e.d.strftime('%m-%d')}:{leave_usage_minutes(e)}" for e in w.usage_events
            )
            concluded = w.effective_end <= result.period_end
            status = ("만근" if w.full_attendance else ("기간중 종료" if w.truncated else "미만근")) if concluded else "진행중"
            as_of = min(w.effective_end, result.period_end)
            balance_at_row = leave_engine.leave_balance_minutes_as_of(result.monthly_windows, as_of)
            leave_rows.append({
                "index": w.index,
                "start": w.start.isoformat(),
                "effective_end": w.effective_end.isoformat(),
                "status": status,
                "accrued": (1 if w.accrued else 0) if concluded else 0,
                "usage": usage_text,
                "balance_minutes": balance_at_row,
            })
        leave_final = {
            "remaining_leave_days": round(result.remaining_leave_days, 4),
            "remaining_leave_minutes": round(result.remaining_leave_days * 480),
        }

        return {
            "raw_rows": raw_rows,
            "weekly": weekly,
            "late_out": late_out,
            "late_out_total_minutes": result.late_out_minutes,
            "meal": meal,
            "leave": leave_rows,
            "leave_final": leave_final,
        }

    def download(self):
        wb = build_workbook(
            self.results, self.config_obj,
            giganje_rows=self.giganje_rows,
            retro_adjustments=self.retro_adjustments,
            retro_details=self.retro_details,
        )
        filename = output_filename(self.work_year, self.work_month)
        path = Path(downloads_dir()) / filename
        wb.save(path)
        saved = [str(path)]

        if self.departed_results:
            departed_wb = build_departed_workbook(self.departed_results)
            departed_path = Path(downloads_dir()) / departed_output_filename(self.work_year, self.work_month)
            departed_wb.save(departed_path)
            saved.append(str(departed_path))
        return saved
