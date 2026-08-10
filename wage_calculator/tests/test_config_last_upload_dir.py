import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Config


def test_last_upload_dir_defaults_to_empty_string():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    assert config.last_upload_dir == ""
    print("OK: test_last_upload_dir_defaults_to_empty_string")


def test_set_last_upload_dir_updates_to_dict():
    config = Config({"surveys": [], "rates": {}, "holidays": []})
    config.set_last_upload_dir("C:/Users/example/Desktop")
    assert config.to_dict()["last_upload_dir"] == "C:/Users/example/Desktop"
    print("OK: test_set_last_upload_dir_updates_to_dict")


def test_last_upload_dir_round_trips_through_load():
    data = {"surveys": [], "rates": {}, "holidays": [], "last_upload_dir": "D:/data"}
    config = Config(data)
    assert config.last_upload_dir == "D:/data"
    print("OK: test_last_upload_dir_round_trips_through_load")


if __name__ == "__main__":
    test_last_upload_dir_defaults_to_empty_string()
    test_set_last_upload_dir_updates_to_dict()
    test_last_upload_dir_round_trips_through_load()
    print("ALL OK")
