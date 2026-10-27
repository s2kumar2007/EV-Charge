"""Load the explicitly selected boundary provider without changing its default."""
import argparse
import config
from boundary_sources import load_provider, pinned_state, pinned_national, download_geoboundaries, geoboundaries_state, compare_providers
from utils import PROCESSED, OUTPUTS, ensure_dirs, save_json


def load_boundaries(force=False):
    ensure_dirs()
    frame = load_provider(force=force)
    frame.to_file(PROCESSED / f"districts_{config.STATE_SLUG}.geojson", driver="GeoJSON")
    save_json(PROCESSED / "boundary_manifest.json", frame.attrs["source_manifest"])
    return frame


def main(compare=False, national=False):
    ensure_dirs()
    frame = load_provider(national=True) if national else load_boundaries()
    print(f"Boundaries: {len(frame)} districts; provider={config.BOUNDARY_PROVIDER}")
    print(config.BOUNDARY_RIGHTS_NOTE if config.BOUNDARY_PROVIDER == "pinned_repo" else "Retain the downloaded ADM1/ADM2 release attribution and licence.")
    if compare:
        try:
            report = compare_providers(pinned_national(), download_geoboundaries("ADM2")) if national else compare_providers(pinned_state(), geoboundaries_state())
            destination = OUTPUTS / config.INDIA_OUTPUT_FOLDER if national else OUTPUTS
            save_json(destination / config.BOUNDARY_COMPARISON_FILE, report)
        except (RuntimeError, OSError, ValueError) as err:
            print(f"PARTIAL: boundary comparison blocked: {err}")
            print("MANUAL: with internet, run python src/load_boundaries.py --compare. Download both ADM1/ADM2 metadata and their gjDownloadURL files if direct access is blocked.")
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--national", action="store_true")
    args = parser.parse_args()
    main(args.compare, args.national)
