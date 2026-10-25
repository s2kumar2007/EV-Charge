"""
Runs the whole Slice 0 pipeline in order:
  1 boundaries -> 2 chargers -> 3 VAHAN check -> 4/5 spatial join + scores -> 6 map -> 7 checks
Usage:  python run_all.py     (downloads are cached in data/raw/, so later runs work offline)
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import build_scores     # noqa: E402
import load_boundaries  # noqa: E402
import load_vahan       # noqa: E402
import make_map         # noqa: E402
import checks           # noqa: E402


def run_step(label, function):
    print(f"\n--- {label} ---")
    try:
        function()
    except Exception as err:  # noqa: BLE001
        print(f"\nSTEP FAILED: {label}\n  reason: {err}\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_step("Step 1: district boundaries", load_boundaries.main)
    run_step("Step 3: VAHAN file check", load_vahan.main)
    run_step("Steps 2, 4, 5: chargers, spatial join, gap scores", build_scores.main)
    run_step("Step 6: interactive map", make_map.main)
    run_step("Step 7: sanity checks", checks.main)
    print("\nDone. Open outputs/tn_gap_map.html in your browser.")
