"""Stream a current free national extract, retaining the previous valid cache."""
import time
import requests
import config
from pbf_reader import header_metadata
from utils import RAW


def download_latest(destination=None):
    if config.OFFLINE:
        raise ValueError('Live download cannot run in offline mode')
    destination = RAW/config.INDIA_LATEST_PBF_CACHE if destination is None else destination
    destination.parent.mkdir(parents=True,exist_ok=True)
    pending = destination.with_suffix(destination.suffix+'.part')
    for attempt in range(config.RETRY_ATTEMPTS):
        try:
            size=0
            with requests.get(config.INDIA_LATEST_PBF_URL,stream=True,timeout=config.NETWORK_TIMEOUT_S,
                              headers={'User-Agent':config.USER_AGENT}) as response:
                response.raise_for_status()
                with pending.open('wb') as stream:
                    for chunk in response.iter_content(chunk_size=config.DOWNLOAD_CHUNK_BYTES):
                        if chunk:
                            stream.write(chunk); size+=len(chunk)
                expected=response.headers.get('Content-Length')
                if expected is not None and size!=int(expected):
                    raise ValueError('National download ended before its declared byte count')
            if size<config.INDIA_LIVE_MIN_BYTES:
                raise ValueError('National download is too small; previous cache preserved')
            metadata=header_metadata(pending)
            if not metadata.get('snapshot_utc'):
                raise ValueError('Downloaded PBF has no verifiable snapshot timestamp')
            pending.replace(destination)
            print(f"Downloaded {size} bytes; OSM snapshot {metadata['snapshot_utc']}",flush=True)
            return destination
        except (requests.RequestException,ValueError,OSError) as err:
            print(f'National refresh attempt {attempt+1}/{config.RETRY_ATTEMPTS}: {type(err).__name__}',flush=True)
            if attempt+1==config.RETRY_ATTEMPTS:
                raise RuntimeError('National live refresh failed; previous valid extract was preserved. Retry online or run without --download-latest.') from err
            time.sleep(config.RETRY_WAIT_S)
