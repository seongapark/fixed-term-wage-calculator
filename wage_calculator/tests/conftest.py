import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import contracts


@pytest.fixture(autouse=True)
def _isolated_contracts(tmp_path, monkeypatch):
    # 계산을 돌리는 테스트가 사용자 %APPDATA%의 contracts.json을 읽거나 덮어쓰지 않게 한다.
    monkeypatch.setattr(contracts, "contracts_path", lambda: tmp_path / "contracts.json")
