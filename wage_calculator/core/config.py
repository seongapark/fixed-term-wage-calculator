import json
from dataclasses import dataclass, field, asdict
from datetime import date

from .paths import config_path

DEFAULT_CONFIG = {
    "surveys": [],       # [{"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]
    "common": {
        "hourly_wage": 9820,      # 시급환산
        "meal_allowance": 160000  # 월 식대
    },
    "holidays": []        # ["YYYY-MM-DD", ...]
}


def _iso(d):
    if isinstance(d, date):
        return d.isoformat()
    return d


class Config:
    def __init__(self, data: dict):
        self.surveys = data.get("surveys", [])
        self.common = data.get("common", dict(DEFAULT_CONFIG["common"]))
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

    # ---- 공통 입력값 ----
    @property
    def hourly_wage(self):
        return self.common.get("hourly_wage", 0)

    @hourly_wage.setter
    def hourly_wage(self, v):
        self.common["hourly_wage"] = v

    @property
    def meal_allowance(self):
        return self.common.get("meal_allowance", 0)

    @meal_allowance.setter
    def meal_allowance(self, v):
        self.common["meal_allowance"] = v

    # ---- 저장/불러오기 ----
    def to_dict(self):
        return {"surveys": self.surveys, "common": self.common, "holidays": self.holidays}

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
