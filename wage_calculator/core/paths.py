import os
import sys
from pathlib import Path

APP_NAME = "통계조사관임금계산"


def is_frozen() -> bool:
    """PyInstaller 등으로 빌드된 exe로 실행 중인지."""
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    """exe(또는 스크립트)가 위치한 폴더."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """사용자별 설정 폴더(%APPDATA%\\<APP_NAME>). exe 위치·버전과 무관하게 항상 같은 곳이라,
    여러 버전 exe가 설정파일 하나를 공유하며 서로 덮어쓰던 문제가 생기지 않는다."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    return root / APP_NAME


def config_path() -> Path:
    return user_data_dir() / "config.json"


def legacy_config_path() -> Path:
    """구버전이 쓰던 exe 옆 경로. 최초 1회 새 위치로 이전(migration)할 때만 참조한다."""
    return app_dir() / "config.json"


def downloads_dir() -> Path:
    home = Path.home()
    d = home / "Downloads"
    if d.exists():
        return d
    return home
