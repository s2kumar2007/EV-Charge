"""Extract chargers, main roads and commercial nodes from one national PBF."""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import config
from pbf_reader import blocks, tags
from fetch_chargers import parse_osm
from utils import ROOT, RAW


def is_charger(labels):
    return labels.get("amenity") == config.INDIA_CHARGER_AMENITY


def is_poi(labels):
    return "shop" in labels or labels.get("amenity") in config.INDIA_COMMERCIAL_AMENITIES


def source_identity(path):
    """Hash the actual snapshot, so replacing a file cannot reuse stale results."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def extract(path=None, refresh=False):
    path = ROOT / config.INDIA_PBF_FILE if path is None else Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Place the India OSM PBF at {path}")
    identity = source_identity(path)
    cache = RAW / f"india_pbf_{identity['sha256']}_v{config.INDIA_READER_VERSION}.json.gz"
    if cache.exists() and not refresh:
        with gzip.open(cache, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    ways, relations = {}, []
    print("Reading road/charger ways and charger relations", flush=True)
    for block in blocks(path):
        strings = block.strings.s
        for group in block.groups:
            for way in group.ways:
                label = tags(way, strings)
                if label.get("highway") in config.INDIA_ROAD_CLASSES or is_charger(label):
                    ways[way.id] = {"id": way.id, "tags": label, "refs": np.cumsum(way.refs, dtype=np.int64).tolist()}
            for relation in group.relations:
                label = tags(relation, strings)
                if is_charger(label):
                    members = list(zip(relation.types, np.cumsum(relation.memids, dtype=np.int64).tolist()))
                    relations.append({"id": relation.id, "tags": label, "members": members})
    # Relations can refer to untagged polygons. Read those ways explicitly.
    extra = {ident for rel in relations for kind, ident in rel["members"] if kind == 1} - ways.keys()
    if extra:
        print(f"Reading {len(extra)} additional relation member ways", flush=True)
        for block in blocks(path):
            for group in block.groups:
                for way in group.ways:
                    if way.id in extra:
                        ways[way.id] = {"id": way.id, "tags": tags(way, block.strings.s), "refs": np.cumsum(way.refs, dtype=np.int64).tolist()}
    needed = {ref for way in ways.values() for ref in way["refs"]}
    needed.update(ident for rel in relations for kind, ident in rel["members"] if kind == 0)
    wanted = np.array(sorted(needed), dtype=np.int64)
    locations, chargers, pois = {}, [], []
    def tagged_node(ident, lon, lat, label):
        if is_charger(label):
            chargers.append({"type":"node", "id":int(ident), "lon":lon, "lat":lat, "tags":label})
        if is_poi(label):
            pois.append({"id":int(ident), "lon":lon, "lat":lat})
    print(f"Reading coordinates for {len(needed)} road/member nodes plus tagged nodes", flush=True)
    for block in blocks(path, nodes=True):
        strings = block.strings.s
        granularity = block.granularity if block.HasField("granularity") else config.INDIA_PBF_DEFAULT_GRANULARITY
        factor = config.INDIA_PBF_COORDINATE_SCALE
        for group in block.groups:
            for node in group.nodes:
                lat = (block.lat_offset + granularity * node.lat) * factor
                lon = (block.lon_offset + granularity * node.lon) * factor
                if node.id in needed:
                    locations[node.id] = (lon,lat)
                tagged_node(node.id,lon,lat,tags(node,strings))
            if not group.HasField("dense"):
                continue
            dense = group.dense
            ids = np.cumsum(dense.id, dtype=np.int64)
            lat = (block.lat_offset + granularity * np.cumsum(dense.lat,dtype=np.int64)) * factor
            lon = (block.lon_offset + granularity * np.cumsum(dense.lon,dtype=np.int64)) * factor
            if not (len(ids) == len(lat) == len(lon)):
                raise ValueError("Dense OSM node coordinate arrays do not reconcile")
            positions = np.searchsorted(wanted, ids)
            candidate = np.flatnonzero(positions < len(wanted))
            selected = candidate[wanted[positions[candidate]] == ids[candidate]]
            for i in selected:
                locations[int(ids[i])] = (float(lon[i]),float(lat[i]))
            kv = np.asarray(dense.keys_vals,dtype=np.int64)
            if not len(kv):
                continue  # PBF permits no tag array for a completely untagged block.
            ends = np.flatnonzero(kv == 0)
            if len(ends) != len(ids):
                raise ValueError("Dense OSM tag delimiters do not reconcile")
            starts = np.r_[0, ends[:-1]+1]
            for i in np.flatnonzero(ends > starts):
                pairs = kv[starts[i]:ends[i]]
                if len(pairs) % 2:
                    raise ValueError("Dense OSM tags have an incomplete key/value pair")
                label = {strings[k].decode("utf-8"):strings[v].decode("utf-8") for k,v in zip(pairs[::2],pairs[1::2])}
                tagged_node(ids[i],float(lon[i]),float(lat[i]),label)
    missing = needed - locations.keys()
    if missing:
        raise ValueError(f"PBF lacks {len(missing)} referenced coordinates; use a complete extract. No partial counts saved.")
    def centre(refs):
        xy = np.array([locations[ref] for ref in refs])
        if not len(xy):
            raise ValueError("Charger geometry has no nodes")
        # Match Overpass centre: centre of the member geometry's bounding box.
        point = (xy.min(axis=0)+xy.max(axis=0))/2
        return {"lon":float(point[0]),"lat":float(point[1])}
    roads = []
    for way in ways.values():
        if way["tags"].get("highway") in config.INDIA_ROAD_CLASSES:
            roads.append({"id":way["id"],"geometry":[{"lon":locations[r][0],"lat":locations[r][1]} for r in way["refs"]]})
        if is_charger(way["tags"]):
            chargers.append({"type":"way","id":way["id"],"tags":way["tags"],"center":centre(way["refs"])})
    for rel in relations:
        refs = []
        for kind, ident in rel["members"]:
            if kind == 0:
                refs.append(ident)
            elif kind == 1:
                if ident not in ways:
                    raise ValueError("Charger relation references a missing member way")
                refs.extend(ways[ident]["refs"])
            else:
                raise ValueError("Nested charger relation needs review; refusing an incomplete location")
        chargers.append({"type":"relation","id":rel["id"],"tags":rel["tags"],"center":centre(refs)})
    result = {"source":identity,"chargers":parse_osm({"elements":chargers}),"roads":{"elements":roads},"pois":{"elements":pois}}
    cache.parent.mkdir(parents=True,exist_ok=True)
    pending = cache.with_suffix(".tmp")
    with gzip.open(pending,"wt",encoding="utf-8") as stream:
        json.dump(result,stream)
    pending.replace(cache)
    print(f"Extracted {len(chargers)} chargers, {len(roads)} main-road ways, {len(pois)} commercial nodes",flush=True)
    return result
