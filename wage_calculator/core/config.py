import json
from dataclasses import dataclass, field, asdict
from datetime import date

from .paths import config_path, is_frozen, legacy_config_path

DEFAULT_CONFIG = {
    "surveys": [],       # [{"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]
    "rates": {},          # {"2026": {"daily_wage": 78560, "meal_allowance": 160000}, ...}
    "holidays": []        # ["YYYY-MM-DD", ...]
}


def _iso(d):
    if isinstance(d, date):
        return d.isoformat()
    return d


class Config:
    def __init__(self, data: dict):
        self.surveys = data.get("surveys", [])
        self.rates = {y: dict(r) for y, r in data.get("rates", {}).items()}
        # 옛 버전 exe(v4.0/v4.1)는 rates 항목을 옛 필드명 hourly_wage로 저장한다.
        # 여러 버전 exe가 config.json 하나를 공유하므로, 구버전이 마지막에 저장한
        # 파일을 신버전(daily_wage 기대)이 읽으면 요율이 "없다"고 오인한다. 여기서
        # 옛 필드명을 새 필드명으로 정규화해 두면 to_dict()/save()로 파일이 자가치유된다.
        for r in self.rates.values():
            if "daily_wage" not in r and "hourly_wage" in r:
                r["daily_wage"] = r.pop("hourly_wage")
        if not self.rates and "common" in data:
            # 레거시 config.json(단일 공통입력값) 마이그레이션: 현재 연도로 1회 이전.
            legacy = data["common"]
            self.rates[str(date.today().year)] = {
                "daily_wage": legacy.get("daily_wage", legacy.get("hourly_wage", 0)),
                "meal_allowance": legacy.get("meal_allowance", 0),
            }
        self.holidays = sorted(set(data.get("holidays", [])))
        self.last_upload_dir = str(data.get("last_upload_dir", ""))

    # ---- 조사종류 ----
    def add_or_update_survey(self, name: str, start: str, end: str):
        start, end = _iso(start), _iso(end)
        for s in self.surveys:
            if s["name"] == name:
                s["start"], s["end"] = start, end
                return
        self.surveys.append({"name": name, "start": start, "end": end})

    def delete_survey(self, name: str):
        self.surveys = [s for s in self.surveys if s["name"] != name]

    def get_survey(self, name: str):
        for s in self.surveys:
            if s["name"] == name:
                return s
        return None

    def survey_names(self):
        return [s["name"] for s in self.surveys]

    # ---- 공휴일 ----
    def add_holiday(self, d: str):
        d = _iso(d)
        if d not in self.holidays:
            self.holidays.append(d)
            self.holidays.sort()

    def remove_holiday(self, d: str):
        d = _iso(d)
        self.holidays = [h for h in self.holidays if h != d]

    def holidays_in_range(self, start: str, end: str):
        start, end = _iso(start), _iso(end)
        return [h for h in self.holidays if start <= h <= end]

    # ---- 파일 선택 경로 ----
    def set_last_upload_dir(self, path: str):
        self.last_upload_dir = path

    # ---- 연도별 요율 ----
    def set_year_rates(self, year: int, daily_wage: int, meal_allowance: int):
        self.rates[str(year)] = {"daily_wage": daily_wage, "meal_allowance": meal_allowance}

    def delete_year_rates(self, year: int):
        self.rates.pop(str(year), None)

    def rate_years(self):
        return sorted(int(y) for y in self.rates.keys())

    def daily_wage_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates or "daily_wage" not in self.rates[y]:
            raise ValueError(f"{year}년 일급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["daily_wage"]

    def meal_allowance_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates:
            raise ValueError(f"{year}년 일급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["meal_allowance"]

    # ---- 저장/불러오기 ----
    def to_dict(self):
        return {
            "surveys": self.surveys,
            "rates": self.rates,
            "holidays": self.holidays,
            "last_upload_dir": self.last_upload_dir,
        }

    def save(self):
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls):
        # 설정은 %APPDATA%(config_path)에 저장한다. 아직 없으면 구버전이 쓰던
        # exe 옆 경로(legacy_config_path)에서 읽어와 최초 1회 새 위치로 이전한다.
        path = config_path()
        legacy = legacy_config_path()
        if path.exists():
            source = path
        elif legacy.exists():
            source = legacy
        else:
            source = None

        if source is not None:
            try:
                data = json.loads(source.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = dict(DEFAULT_CONFIG)
        else:
            data = dict(DEFAULT_CONFIG)

        obj = cls(data)
        # 구버전 경로에서 읽어왔다면 새 위치로 이전 저장한다. 실제 배포(exe) 환경에서만
        # 수행해, 테스트·소스 실행이 사용자 %APPDATA%를 건드리지 않도록 한다.
        if source is legacy and is_frozen():
            try:
                obj.save()
            except OSError:
                pass
        return obj
