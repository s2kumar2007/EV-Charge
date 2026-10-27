"""Shared folders, comparison keys and careful cached downloads."""
import hashlib
import json
import math
import re
import time
import unicodedata
from pathlib import Path

import requests
import config

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
SAMPLES = ROOT / "data" / "samples"


def ensure_dirs():
    for folder in (RAW, PROCESSED, OUTPUTS, SAMPLES):
        folder.mkdir(parents=True, exist_ok=True)


def norm_key(name):
    """Compare letters only; punctuation is not a spelling correction."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return ""
    words = unicodedata.normalize(config.NAME_UNICODE_NORMALIZATION, str(name)).lower().strip().split()
    while words and words[0] in config.NAME_IGNORED_LEADING_WORDS:
        words.pop(0)
    key = re.sub(r"[^a-z]", "", " ".join(words))
    return key[:-len("district")] if key.endswith("district") else key


def request_with_retry(method, url, attempts=None, wait=None, **kwargs):
    """Report failures without printing API keys or private query parameters."""
    if config.OFFLINE:
        raise RuntimeError(f"Offline mode: no cached answer for {url}. Run online first.")
    attempts = config.RETRY_ATTEMPTS if attempts is None else attempts
    wait = config.RETRY_WAIT_S if wait is None else wait
    kwargs.setdefault("headers", {"User-Agent": config.USER_AGENT})
    kwargs.setdefault("timeout", config.NETWORK_TIMEOUT_S)
    if attempts < 1:
        raise ValueError("RETRY_ATTEMPTS must be at least one.")
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as err:
            reason = type(err).__name__
            print(f"  [warning] {url}: {reason}, attempt {attempt}/{attempts}")
            if attempt < attempts:
                time.sleep(wait * attempt)
    raise RuntimeError(f"Download failed for {url}: {reason} after {attempts} attempts. Check connectivity or use a cached download.")


def save_json(path, value):
    """Replace a cache atomically so an interrupted download cannot ruin it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def cached_json(path, method, url, force=False, validator=None, **kwargs):
    """Cache the response and its date, source and query fingerprint."""
    from datetime import datetime, timezone
    if path.exists() and not force:
        value = json.loads(path.read_text(encoding="utf-8"))
        if validator:
            validator(value)
        return value
    value = request_with_retry(method, url, **kwargs).json()
    if validator:
        validator(value)
    save_json(path, value)
    # Keys are deliberately excluded from metadata.
    query = {"data": kwargs.get("data", {}),
             "params": {k: v for k, v in kwargs.get("params", {}).items() if k.lower() not in config.PRIVATE_PARAMETER_KEYS}}
    save_json(path.with_suffix(path.suffix + ".meta.json"), {
        "url": url, "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "query_sha256": hashlib.sha256(str(query).encode()).hexdigest(),
    })
    return value


def validate_overpass(value):
    if not isinstance(value, dict) or "elements" not in value or value.get("remark"):
        raise ValueError("Overpass returned an incomplete or invalid answer; it was not cached.")


def fetch_overpass(query, label, force=False):
    """Query-specific caches prevent mixing states or changed bounding boxes."""
    ensure_dirs()
    digest = hashlib.sha256(query.encode()).hexdigest()
    path = RAW / f"{label}_{config.STATE_SLUG}_{digest}.json"
    errors = []
    for endpoint in config.OVERPASS_ENDPOINTS:
        try:
            return cached_json(path, "POST", endpoint, force=force,
                               validator=validate_overpass, data={"data": query},
                               timeout=config.OVERPASS_TIMEOUT_S + config.NETWORK_TIMEOUT_PADDING_S)
        except (RuntimeError, ValueError) as err:
            errors.append(str(err))
            print(f"  [warning] {endpoint}: {err}")
    raise RuntimeError(f"All Overpass endpoints failed for {label}. " + " | ".join(errors))
