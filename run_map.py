"""Serve generated maps from a terminal and keep the local server alive."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config
from utils import OUTPUTS


def map_target(output=OUTPUTS):
    directory = Path(output) / config.INDIA_OUTPUT_FOLDER
    path = directory / config.GOOGLE_MAPS_INDIA_FILENAME
    if not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError("Generate the national map first: python run_india.py --google-map-only --offline")
    return directory, path.name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    directory, filename = map_target()
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    try:
        server = ThreadingHTTPServer((config.MAP_SERVER_HOST, config.MAP_SERVER_PORT), handler)
    except OSError as err:
        print(f"Cannot start the map server: {err}. Check the existing server or MAP_SERVER_PORT in src/config.py.")
        return 1
    with server:
        url = f"http://{config.MAP_SERVER_HOST}:{server.server_port}/{filename}"
        print(f"Map: {url}\nKeep this terminal open. Press Ctrl+C to stop.", flush=True)
        if config.MAP_SERVER_OPEN_BROWSER and not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Map server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
