"""Tests cannot accidentally download anything, and write only to a temp folder."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def isolate_downloads(monkeypatch, tmp_path):
    import requests
    import load_vahan
    def forbidden(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr(requests, "request", forbidden)
    monkeypatch.setattr(load_vahan, "RESOLUTION_LOG", tmp_path / "resolution.csv")
