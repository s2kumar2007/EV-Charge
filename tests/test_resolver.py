"""
Offline test of the name matching (no internet needed except the boundary download).
Run:  python tests/test_resolver.py
The geocoder is replaced by a fake one that returns made-up coordinates for the test only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import load_boundaries  # noqa: E402
from resolve_districts import clean_rto_name, resolve_one  # noqa: E402

b = load_boundaries.load_boundaries()
keys = set(b["district_key"])

# fake geocoder: (lat, lon) points chosen inside real districts for the test only
fake = {"Mayiladuthurai district, Tamil Nadu, India": [11.10, 79.65],
        "Chennai Central, Tamil Nadu, India": [13.08, 80.27]}
geo = lambda q: {k.lower(): v for k, v in fake.items()}.get(q.lower())  # noqa: E731

cases = [("Tirupur", "district", "fuzzy"), ("Pudukottai", "district", "fuzzy"),
         ("Tirupattur", "district", "fuzzy"), ("Vilupuram", "district", "fuzzy"),
         ("Thirunelveli", "district", "fuzzy"), ("Kanyakumari", "district", "exact"),
         ("Mayiladuthurai", "district", "geocode"),
         ("CHENNAI CENTRAL RTO - TN01", "rto", "geocode"),
         ("SALEM", "district", "exact")]
failed = 0
for name, kind, expected in cases:
    key, method = resolve_one(name, b, kind, geo)
    ok = method == expected and key in keys
    failed += not ok
    print(("PASS " if ok else "FAIL "), f"{name!r:35} -> {key} [{method}] (expected {expected})")

assert clean_rto_name("CHENNAI (CENTRAL) RTO - TN01") == "CHENNAI"
print("\nAll passed." if not failed else f"\n{failed} FAILED.")
sys.exit(1 if failed else 0)
