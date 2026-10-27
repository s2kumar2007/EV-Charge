"""Run both slices; a failed required step names itself and exits with status 1."""
import argparse
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config
import build_scores
import checks
import fetch_chargers
import fetch_indicators
import gap_index
import hotspots
import load_boundaries
import load_population
import load_vahan
import make_map


def run_step(label, function, *args, **kwargs):
    print(f"\n--- {label} ---", flush=True)
    try:
        return function(*args, **kwargs)
    except Exception as err:
        print(f"\nSTEP FAILED: {label}\nReason: {err}", flush=True)
        traceback.print_exc()
        raise SystemExit(1) from err


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", choices=["0", "all"], default="all", help="Keep just Slice 0, or run both slices.")
    parser.add_argument("--refresh", action="store_true", help="Download current OSM/OCM/source data again.")
    parser.add_argument("--offline", action="store_true", help="Use cached downloads only.")
    args = parser.parse_args(argv)
    if args.refresh and args.offline:
        parser.error("--refresh and --offline cannot be used together")
    config.OFFLINE = args.offline
    config.REFRESH_DOWNLOADS = args.refresh
    boundaries = run_step("Step 1: district boundaries", load_boundaries.load_boundaries, force=args.refresh)
    print(f"{len(boundaries)} districts in {config.STATE_NAME}; new districts may be missing.")
    chargers = run_step("Step 2: public chargers", fetch_chargers.fetch_chargers, boundaries, force=args.refresh)
    run_step("Step 3a: VAHAN input and template", load_vahan.main)
    ev, _ = run_step("Step 3b: resolve EV names", load_vahan.load_vahan, boundaries)
    run_step("Steps 4 and 5: spatial join and Slice 0 scores", build_scores.main, chargers, boundaries, ev, use_dedup=False)
    run_step("Step 6: Slice 0 map", make_map.main, include_slice1=False)
    run_step("Step 7: Slice 0 checks", checks.main, include_slice1=False)
    if args.slice == "all":
        # The original score CSV remains the raw Slice 0 result. Selected Slice 1
        # counts go to a second CSV, leaving earlier outputs reproducible.
        selected = run_step("Step 8: deduplication, audit, radius sensitivity and selected scores",
                            build_scores.main, chargers, boundaries, ev, use_dedup=config.DEDUP_ENABLED)
        population = run_step("Step 9: compatible population", load_population.main, boundaries)
        osm = run_step("Step 10: OSM road and commercial density", fetch_indicators.main, boundaries)
        index = run_step("Step 11: composite index and weight sensitivity", gap_index.main, selected, population, osm)
        run_step("Step 12: Moran's I and Gi* hotspots", hotspots.main, boundaries, index)
        run_step("Step 13: map layers", make_map.main, include_slice1=True)
        run_step("Step 14: complete checks", checks.main, include_slice1=True)
    print(f"\nDone. Open outputs/{config.MAP_FILENAME}. Missing data remain unranked.")


if __name__ == "__main__":
    main()
