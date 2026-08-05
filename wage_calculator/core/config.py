import json
from dataclasses import dataclass, field, asdict
from datetime import date

from .paths import config_path

DEFAULT_CONFIG = {
    "surveys": [],       # [{"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]
    "rates": {},          # {"2026": {"hourly_wage": 9820, "meal_allowance": 160000}, ...}
    "holidays": []        # ["YYYY-MM-DD", ...]
}


def _iso(d):
    if isinstance(d, date):
        return d.isoformat()
    return d


class Config:
    def __init__(self, data: dict):
        self.surveys = data.get("surveys", [])
        self.rates = dict(data.get("rates", {}))
        if not self.rates and "common" in data:
            # 레거시 config.json(단일 공통입력값) 마이그레이션: 현재 연도로 1회 이전.
            legacy = data["common"]
            self.rates[str(date.today().year)] = {
                "hourly_wage": legacy.get("hourly_wage", 0),
                "meal_allowance": legacy.get("meal_allowance", 0),
            }
        self.holidays = sorted(set(data.get("holidays", [])))

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

    # ---- 연도별 요율 ----
    def set_year_rates(self, year: int, hourly_wage: int, meal_allowance: int):
        self.rates[str(year)] = {"hourly_wage": hourly_wage, "meal_allowance": meal_allowance}

    def delete_year_rates(self, year: int):
        self.rates.pop(str(year), None)

    def rate_years(self):
        return sorted(int(y) for y in self.rates.keys())

    def hourly_wage_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates:
            raise ValueError(f"{year}년 시급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["hourly_wage"]

    def meal_allowance_for(self, year: int) -> int:
        y = str(year)
        if y not in self.rates:
            raise ValueError(f"{year}년 시급/식대 요율이 설정되지 않았습니다. 설정 화면에서 추가하세요.")
        return self.rates[y]["meal_allowance"]

    # ---- 저장/불러오기 ----
    def to_dict(self):
        return {"surveys": self.surveys, "rates": self.rates, "holidays": self.holidays}

    def save(self):
        path = config_path()
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls):
        path = config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = dict(DEFAULT_CONFIG)
        else:
            data = dict(DEFAULT_CONFIG)
        return cls(data)
