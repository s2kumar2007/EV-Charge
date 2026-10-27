"""Cache external script/link resources without hiding failed downloads."""
import argparse
import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import config
from utils import RAW, request_with_retry, save_json


class ExternalAssets(HTMLParser):
    """Read actual HTML attributes rather than matching JavaScript strings."""
    def __init__(self):
        super().__init__()
        self.urls = set()
        self.local = set()

    def handle_starttag(self, tag, attrs):
        attribute = "src" if tag == "script" else "href" if tag == "link" else None
        value = dict(attrs).get(attribute) if attribute else None
        if value:
            if value.startswith(("https://", "http://", "//")):
                self.urls.add(value)
            elif not value.startswith(("data:", "blob:", "#")):
                self.local.add(value)


def inspect_assets(document, directory):
    parser = ExternalAssets()
    parser.feed(document)
    missing = [value for value in parser.local if not (directory / value).is_file() or (directory / value).stat().st_size == 0]
    return {"offline_assets": not parser.urls and not missing, "external_urls": sorted(parser.urls), "missing_local": sorted(missing)}


def rewrite_assets(document, directory, cache_directory=None, downloader=None):
    """Download each unique URL once; only rewrite after non-empty files exist."""
    directory = Path(directory)
    cache_directory = RAW / config.MAP_ASSET_CACHE_DIR if cache_directory is None else Path(cache_directory)
    downloader = downloader or (lambda url: request_with_retry("GET", url).content)
    parser = ExternalAssets()
    parser.feed(document)
    failures, replacements = [], {}
    for original in sorted(parser.urls):
        url = "https:" + original if original.startswith("//") else original
        extension = Path(urlsplit(url).path).suffix or config.MAP_ASSET_FALLBACK_EXTENSION
        name = hashlib.sha256(url.encode()).hexdigest() + extension
        cached = cache_directory / name
        destination = directory / config.MAP_ASSET_FOLDER / name
        try:
            if not destination.exists() or destination.stat().st_size == 0:
                if not cached.exists() or cached.stat().st_size == 0:
                    payload = downloader(url)
                    if not payload:
                        raise ValueError("Empty response; original URL retained")
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    pending = cached.with_suffix(cached.suffix + ".tmp")
                    pending.write_bytes(payload)
                    pending.replace(cached)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cached, destination)
            if destination.stat().st_size == 0:
                raise ValueError("Cached resource is empty")
            replacements[original] = f"{config.MAP_ASSET_FOLDER}/{name}"
        except (RuntimeError, OSError, ValueError) as err:
            failures.append(original)
            print(f"[WARNING] Map asset failed: {original}: {err}")
    # Replace URL attributes only. Inline code and tile URLs remain untouched.
    pattern = re.compile(r"(?P<prefix>\b(?:src|href)\s*=\s*)(?P<quote>[\"'])(?P<url>.*?)(?P=quote)", re.I)
    def replace(match):
        value = replacements.get(html.unescape(match.group("url")))
        return match.group("prefix") + match.group("quote") + value + match.group("quote") if value else match.group(0)
    return pattern.sub(replace, document), failures


def main(path, downloader=None):
    path = Path(path)
    document, failures = rewrite_assets(path.read_text(encoding="utf-8"), path.parent, downloader=downloader)
    path.write_text(document, encoding="utf-8")
    report = inspect_assets(document, path.parent)
    report["failed_urls"] = failures
    save_json(path.with_suffix(".assets.json"), report)
    print(f"Offline JS/CSS assets: {'yes' if report['offline_assets'] else 'no'}; failed URLs: {failures}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file")
    main(parser.parse_args().html_file)
