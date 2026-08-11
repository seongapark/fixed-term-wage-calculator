import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import bootstrap_server, find_free_port
from webapp.state import AppState


def test_find_free_port_returns_distinct_bindable_ports():
    p1 = find_free_port()
    p2 = find_free_port()
    assert p1 != p2
    assert 1024 < p1 < 65536
    assert 1024 < p2 < 65536
    print("OK: test_find_free_port_returns_distinct_bindable_ports")


def test_bootstrap_server_serves_index_html():
    state = AppState()
    port = bootstrap_server(state)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        body = resp.read().decode("utf-8")
        status = resp.status
    assert status == 200
    assert "통계조사관 임금계산" in body
    print("OK: test_bootstrap_server_serves_index_html")


if __name__ == "__main__":
    test_find_free_port_returns_distinct_bindable_ports()
    test_bootstrap_server_serves_index_html()
    print("ALL OK")
