"""pywebview 부트스트랩. webapp/server.py의 FastAPI 앱을 로컬 서버로 띄우고
네이티브 창에 표시한다. OS 파일 다이얼로그는 js_api가 HTTP 없이 직접 처리한다."""
import socket
import time
import urllib.request
from pathlib import Path
from threading import Thread

import uvicorn
import webview

from webapp.server import create_app
from webapp.state import AppState


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(port: int, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5)
            return
        except Exception as e:
            last_error = e
            time.sleep(0.1)
    raise RuntimeError(f"서버가 {timeout}초 안에 응답하지 않았습니다(port={port}): {last_error}")


def bootstrap_server(state: AppState) -> int:
    """FastAPI 앱을 백그라운드 스레드로 띄우고, 응답이 올 때까지 기다린 뒤 포트를 반환한다."""
    app = create_app(state)
    port = find_free_port()
    thread = Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()
    _wait_until_ready(port)
    return port


class JSApi:
    def __init__(self, state: AppState):
        self.state = state

    def pick_file(self, kind: str):
        start_dir = self.state.config_obj.last_upload_dir or ""
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, directory=start_dir, file_types=("Excel Files (*.xlsx)",)
        )
        if not result:
            return None
        path = result[0]
        self.state.config_obj.set_last_upload_dir(str(Path(path).parent))
        self.state.config_obj.save()
        return path


def main():
    state = AppState()
    port = bootstrap_server(state)
    webview.create_window(
        "통계조사관 임금계산",
        f"http://127.0.0.1:{port}/",
        js_api=JSApi(state),
        width=1100,
        height=780,
    )
    webview.start()


if __name__ == "__main__":
    main()
