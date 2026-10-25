"""
Small shared helpers used by every step of the pipeline.

Three jobs:
  1. Know where the project folders are (so scripts work from any directory).
  2. Make district names comparable ("Kancheepuram" == "Kanchipuram").
  3. Download things politely: retry a few times and fail with a clear message.
"""
import math
import re
import time
from pathlib import Path

import requests

# The project root is the folder above src/.
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # downloads and hand-made inputs (never edited by code)
PROCESSED = ROOT / "data" / "processed"  # intermediate files made by our code
OUTPUTS = ROOT / "outputs"             # final results: CSV and HTML map


def ensure_dirs():
    """Create the data/outputs folders if they do not exist yet."""
    for folder in (RAW, PROCESSED, OUTPUTS):
        folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# District name matching
# ---------------------------------------------------------------------------
# The same district is spelled differently in different datasets. We reduce every
# name to a "key" (lowercase letters only) and then map known alternative
# spellings onto the spelling used in the DataMeet boundary file.
NAME_ALIASES = {
    "kanchipuram": "kancheepuram",
    "kanyakumari": "kanniyakumari",
    "nagapattinam": "nagappattinam",
    "nilgiris": "thenilgiris",
    "nilgiri": "thenilgiris",
    "tiruvallur": "thiruvallur",
    "tuticorin": "thoothukkudi",
    "thoothukudi": "thoothukkudi",
    "trichy": "tiruchirappalli",
    "tiruchirapalli": "tiruchirappalli",
    "tiruchi": "tiruchirappalli",
    "thiruppur": "tiruppur",
    "thiruvannamalai": "tiruvannamalai",
    "tiruvarur": "thiruvarur",
    "villupuram": "viluppuram",
    "virudhunagar": "virudunagar",
    "sivagangai": "sivaganga",
    "ramnad": "ramanathapuram",
    "pudukkotai": "pudukkottai",
    "tanjore": "thanjavur",
}


def norm_key(name):
    """Turn a district name into a comparable key, e.g. 'The Nilgiris' -> 'thenilgiris'."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return ""
    key = re.sub(r"[^a-z]", "", str(name).lower())
    if key.endswith("district"):
        key = key[: -len("district")]
    return NAME_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# Downloading with retries
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "ChargeGap-Slice0/0.1 (educational prototype)"}


def request_with_retry(method, url, attempts=4, wait=5, **kwargs):
    """
    Call requests.request() and retry if the network or server fails.
    Waits a little longer after each failure. If every attempt fails we raise
    a RuntimeError with a plain-language message (so nothing fails silently).
    """
    kwargs.setdefault("headers", HEADERS)
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()  # turns HTTP 404/429/504 into an error
            return response
        except requests.RequestException as err:
            last_error = err
            print(f"  [warning] attempt {attempt}/{attempts} failed for {url}: {err}")
            if attempt < attempts:
                time.sleep(wait * attempt)
    raise RuntimeError(
        f"Could not download {url} after {attempts} attempts. Last error: {last_error}. "
        "Check your internet connection and try again."
    )
