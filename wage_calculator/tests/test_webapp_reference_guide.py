import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GUIDE_PATH = Path(__file__).resolve().parent.parent / "webapp" / "static" / "reference" / "leave_category_guide.json"


def test_guide_file_is_valid_json_list():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 40
    print("OK: test_guide_file_is_valid_json_list")


def test_guide_entries_have_required_keys():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    required = {"category", "subtype", "detail", "description", "deduction", "time_entry", "note"}
    for entry in data:
        assert required <= entry.keys(), entry
    print("OK: test_guide_entries_have_required_keys")


def test_guide_includes_family_care_leave_note():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    family_care = [e for e in data if e["subtype"] == "가족돌봄휴가"]
    assert len(family_care) == 1
    assert "유급" in family_care[0]["note"]
    print("OK: test_guide_includes_family_care_leave_note")


def test_guide_includes_special_leave_marking_context():
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
    categories = {e["category"] for e in data}
    assert {"연가", "지각", "외출", "조퇴", "병가", "공가", "경조사휴가", "특별휴가", "결근", "기타"} <= categories
    print("OK: test_guide_includes_special_leave_marking_context")


if __name__ == "__main__":
    test_guide_file_is_valid_json_list()
    test_guide_entries_have_required_keys()
    test_guide_includes_family_care_leave_note()
    test_guide_includes_special_leave_marking_context()
    print("ALL OK")
