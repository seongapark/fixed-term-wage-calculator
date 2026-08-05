import sys
from pathlib import Path


def app_dir() -> Path:
    """exe(또는 스크립트)가 위치한 폴더. 설정파일 저장 위치 기준."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / "config.json"


def downloads_dir() -> Path:
    home = Path.home()
    d = home / "Downloads"
    if d.exists():
        return d
    return home
