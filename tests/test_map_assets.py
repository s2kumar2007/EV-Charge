"""Resource downloads are fake byte functions; no internet is used."""
from pathlib import Path
import cache_map_assets as assets


def test_attributes_duplicates_and_nonempty(tmp_path):
    text = """<script src='https://fake.invalid/a.js'></script><script src="https://fake.invalid/a.js"></script>
    <link rel="stylesheet" href="//fake.invalid/style?x=1&amp;y=2"><script>const u='https://fake.invalid/a.js';</script>"""
    calls = []
    def download(url):
        calls.append(url)
        return b"fake-resource"
    result, failed = assets.rewrite_assets(text, tmp_path, tmp_path / "cache", download)
    assert not failed and len(calls) == 2
    assert "const u='https://fake.invalid/a.js'" in result
    assert assets.inspect_assets(result, tmp_path)["offline_assets"]
    assert all(p.stat().st_size for p in (tmp_path / "assets").iterdir())
    again, failed = assets.rewrite_assets(text, tmp_path, tmp_path / "cache", lambda u: (_ for _ in ()).throw(AssertionError("download twice")))
    assert again == result and not failed


def test_empty_and_failed_resources_retain_urls(tmp_path):
    text = '<script src="https://fake.invalid/a.js"></script><link href="https://fake.invalid/b.css">'
    def download(url):
        if url.endswith("a.js"):
            return b""
        raise RuntimeError("fake unavailable")
    result, failed = assets.rewrite_assets(text, tmp_path, tmp_path / "cache", download)
    assert result == text and len(failed) == 2
    assert not assets.inspect_assets(result, tmp_path)["offline_assets"]


def test_missing_or_empty_local_asset_is_not_offline(tmp_path):
    text = '<script src="assets/empty.js"></script>'
    assert not assets.inspect_assets(text, tmp_path)["offline_assets"]
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/empty.js").write_bytes(b"")
    assert not assets.inspect_assets(text, tmp_path)["offline_assets"]
