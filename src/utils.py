"""
Small shared helpers: project folders, a name key, and downloads with retries.
No data lives here (no district lists, no spelling tables).
"""
import math
import re
import time
from pathlib import Path

import requests

import config

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"              # downloads and hand-made inputs
PROCESSED = ROOT / "data" / "processed"  # files made by our code
OUTPUTS = ROOT / "outputs"               # final CSV and HTML map


def ensure_dirs():
    for folder in (RAW, PROCESSED, OUTPUTS):
        folder.mkdir(parents=True, exist_ok=True)


def norm_key(name):
    """Make a name comparable: lowercase letters only, so 'The Nilgiris' -> 'thenilgiris'."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return ""
    key = re.sub(r"[^a-z]", "", str(name).lower())
    return key[: -len("district")] if key.endswith("district") else key


def request_with_retry(method, url, attempts=None, wait=None, **kwargs):
    """requests.request() with retries. Raises a clear RuntimeError if every attempt fails."""
    attempts = attempts or config.RETRY_ATTEMPTS
    wait = wait or config.RETRY_WAIT_S
    kwargs.setdefault("headers", {"User-Agent": config.USER_AGENT})
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as err:
            last_error = err
            print(f"  [warning] attempt {attempt}/{attempts} failed for {url}: {err}")
            if attempt < attempts:
                time.sleep(wait * attempt)
    raise RuntimeError(f"Could not download {url} after {attempts} attempts. "
                       f"Last error: {last_error}. Check your internet connection and try again.")
