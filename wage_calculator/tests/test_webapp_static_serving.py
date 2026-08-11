import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from webapp.server import create_app


def test_root_serves_index_html():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "통계조사관 임금계산" in resp.text
    print("OK: test_root_serves_index_html")


def test_static_css_is_served():
    app = create_app()
    client = TestClient(app)
    for path in ["/css/tokens.css", "/css/base.css"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    print("OK: test_static_css_is_served")


def test_api_routes_still_work_after_static_mount():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    print("OK: test_api_routes_still_work_after_static_mount")


if __name__ == "__main__":
    test_root_serves_index_html()
    test_static_css_is_served()
    test_api_routes_still_work_after_static_mount()
    print("ALL OK")
