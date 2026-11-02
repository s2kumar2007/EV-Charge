"""
Launch script for ChargeGap India interactive API and Leaflet dashboard.
Starts Uvicorn server and prints user-facing URL.
"""
import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import config


def launch_dashboard(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False) -> None:
    """Start Uvicorn server hosting FastAPI and interactive Leaflet dashboard."""
    url = f"http://{host}:{port}"
    print(f"\n=======================================================", flush=True)
    print(f"  ChargeGap India - Interactive Dashboard & API", flush=True)
    print(f"  Hosting at: {url}", flush=True)
    print(f"  API Docs at: {url}/docs", flush=True)
    print(f"=======================================================\n", flush=True)

    if open_browser:
        def _open():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("api.main:app", host=host, port=port, log_level="info", reload=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ChargeGap India interactive dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    launch_dashboard(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
