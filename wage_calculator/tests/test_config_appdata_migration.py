import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.config as config_module
from core.config import Config


def _patch_paths(monkeypatch, new_path, legacy_path, frozen):
    monkeypatch.setattr(config_module, "config_path", lambda: new_path)
    monkeypatch.setattr(config_module, "legacy_config_path", lambda: legacy_path)
    monkeypatch.setattr(config_module, "is_frozen", lambda: frozen)


def test_load_reads_legacy_when_new_path_absent(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": [],
    }), encoding="utf-8")
    new_path = tmp_path / "appdata" / "config.json"
    _patch_paths(monkeypatch, new_path, legacy, frozen=False)

    config = Config.load()
    assert config.daily_wage_for(2026) == 78560
    print("OK: test_load_reads_legacy_when_new_path_absent")


def test_frozen_migrates_legacy_to_new_path(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "surveys": [], "rates": {"2026": {"daily_wage": 78560, "meal_allowance": 160000}}, "holidays": [],
    }), encoding="utf-8")
    new_path = tmp_path / "appdata" / "config.json"
    _patch_paths(monkeypatch, new_path, legacy, frozen=True)

    Config.load()
    # exe(frozen) 환경에서는 새 위치(%APPDATA%)로 자동 이전돼 파일이 생성돼야 한다.
    assert new_path.exists()
    migrated = json.loads(new_path.read_text(encoding="utf-8"))
    assert migrated["rates"]["2026"]["daily_wage"] == 78560
    print("OK: test_frozen_migrates_legacy_to_new_path")


def test_non_frozen_does_not_write_new_path(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"surveys": [], "rates": {}, "holidays": []}), encoding="utf-8")
    new_path = tmp_path / "appdata" / "config.json"
    _patch_paths(monkeypatch, new_path, legacy, frozen=False)

    Config.load()
    # 소스/테스트 실행은 사용자 %APPDATA%를 건드리면 안 된다.
    assert not new_path.exists()
    print("OK: test_non_frozen_does_not_write_new_path")


def test_new_path_takes_precedence_over_legacy(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"surveys": [], "rates": {"2026": {"daily_wage": 111, "meal_allowance": 1}}, "holidays": []}), encoding="utf-8")
    new_path = tmp_path / "appdata" / "config.json"
    new_path.parent.mkdir(parents=True)
    new_path.write_text(json.dumps({"surveys": [], "rates": {"2026": {"daily_wage": 999, "meal_allowance": 9}}, "holidays": []}), encoding="utf-8")
    _patch_paths(monkeypatch, new_path, legacy, frozen=True)

    config = Config.load()
    assert config.daily_wage_for(2026) == 999
    print("OK: test_new_path_takes_precedence_over_legacy")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-q"])
