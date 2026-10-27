"""The map launcher is tested with fake files and an in-memory server."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_map
import config


def test_map_target_requires_existing_nonempty_html(tmp_path):
    with pytest.raises(FileNotFoundError, match="Generate"):
        run_map.map_target(tmp_path)
    directory = tmp_path / config.INDIA_OUTPUT_FOLDER
    directory.mkdir()
    path = directory / config.GOOGLE_MAPS_INDIA_FILENAME
    path.write_text("<html>Fake map</html>")
    assert run_map.map_target(tmp_path) == (directory, path.name)


def test_server_uses_map_directory_and_stays_open(tmp_path, monkeypatch, capsys):
    class Server:
        server_port = 12345
        def __init__(self, address, handler):
            assert address == (config.MAP_SERVER_HOST, config.MAP_SERVER_PORT)
            assert handler.keywords["directory"] == str(tmp_path)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def serve_forever(self): raise KeyboardInterrupt()
    monkeypatch.setattr(run_map, "map_target", lambda: (tmp_path, "fake.html"))
    monkeypatch.setattr(run_map, "ThreadingHTTPServer", Server)
    monkeypatch.setattr(run_map.webbrowser, "open", lambda url: pytest.fail("no browser requested"))
    assert run_map.main(["--no-browser"]) == 0
    assert "12345/fake.html" in capsys.readouterr().out
