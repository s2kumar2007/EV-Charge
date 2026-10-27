"""National district identities, verified inputs and locally measured OSM data."""
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
import config
from utils import ROOT, RAW, norm_key
from build_scores import assign_chargers_to_districts, count_units, rank_districts


def load_boundaries(path=None):
    path = ROOT / config.INDIA_BOUNDARY_FILE if path is None else Path(path)
    if not path.exists():
        raise FileNotFoundError(f"National boundary file missing: {path}")
    frame = gpd.read_file(path)
    required = [config.INDIA_BOUNDARY_NAME, config.INDIA_BOUNDARY_ID]
    if not set(required).issubset(frame):
        raise ValueError(f"National boundaries need {required}; found {list(frame.columns)}")
    if frame.crs is None:
        raise ValueError("Boundary CRS is missing; do not guess coordinate units")
    frame = frame.rename(columns={required[0]:"district", required[1]:"district_key"})
    frame = frame[["district","district_key","geometry"]].to_crs(config.WGS84)
    frame.geometry = frame.geometry.make_valid()
    if frame.district_key.isna().any() or frame.district_key.duplicated().any():
        raise ValueError("National dataset IDs must be nonempty and unique")
    if frame.district.isna().any() or frame.district.astype(str).str.strip().eq("").any():
        raise ValueError("National district names must be nonempty")
    if frame.geometry.is_empty.any() or frame.geometry.isna().any() or not frame.geom_type.isin(["Polygon","MultiPolygon"]).all():
        raise ValueError("National boundaries contain missing/non-polygon geometry after repair")
    frame.district_key = frame.district_key.astype(str)
    return frame.sort_values("district_key").reset_index(drop=True)


def read_verified_input(boundaries, path, value, audit_path):
    """Join on source polygon ID only: identical district names are ambiguous.

    A user must confirm compatible boundaries, observation date and source.
    We cannot infer these facts from matching district spellings.
    """
    columns = ["district_key",value,"source_url","observation_date","boundary_compatible"]
    if value == "ev_total":
        columns += ["ev_measure","period_start","period_end"]
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path.with_name(path.stem+"_TEMPLATE.csv"),index=False)
        pd.DataFrame(columns=[*columns,"resolution_status"]).to_csv(audit_path,index=False)
        print(f"Missing {path.name}: {value} stays empty. Template created.",flush=True)
        return pd.DataFrame({"district_key":boundaries.district_key,value:np.nan})
    table = pd.read_csv(path,dtype={"district_key":str})
    if not set(columns).issubset(table):
        raise ValueError(f"{path.name} needs columns {columns}")
    if table.district_key.duplicated().any():
        raise ValueError(f"Duplicate district IDs in {path.name}; aggregate reviewed RTO rows before import")
    numbers = pd.to_numeric(table[value],errors="coerce")
    malformed = table[value].notna() & numbers.isna()
    if malformed.any() or (~np.isfinite(numbers.dropna())).any() or (numbers.dropna()<0).any():
        raise ValueError(f"Invalid {value} in {path.name}")
    if value == "population" and numbers.dropna().eq(0).any():
        raise ValueError("Population must be positive")
    table[value] = numbers
    compatible = table.boundary_compatible.astype(str).str.lower().isin(config.VALIDATION_ACCEPTED_TRUE)
    known = table.district_key.isin(boundaries.district_key)
    provenance = table.source_url.fillna("").astype(str).str.strip().ne("") & table.observation_date.fillna("").astype(str).str.strip().ne("")
    table["resolution_status"] = np.select([~known,~compatible,~provenance],
        ["unknown boundary ID","boundary compatibility unverified","missing source/date"],default="accepted")
    if value == "ev_total":
        if not {"ev_measure","period_start","period_end"}.issubset(table):
            raise ValueError("National EV input also needs ev_measure,period_start,period_end")
        observed = table.loc[table[value].notna() & table.resolution_status.eq("accepted")]
        if observed[["ev_measure","period_start","period_end"]].isna().any().any():
            raise ValueError("EV measurement and period cannot be blank")
        if len(observed[["ev_measure","period_start","period_end"]].drop_duplicates()) > 1:
            raise ValueError("National ranking cannot mix EV measurement types or registration periods")
    table.to_csv(audit_path,index=False)
    used = table[table.resolution_status.eq("accepted")]
    result = boundaries[["district_key"]].merge(used.drop(columns="resolution_status"),on="district_key",how="left",validate="one_to_one")
    print(f"{value}: {result[value].notna().sum()}/{len(boundaries)} verified districts",flush=True)
    return result


def osm_indicators(boundaries, roads, pois):
    """Use each district's own estimated UTM zone, avoiding India-wide distortion."""
    features = []
    for way in roads["elements"]:
        coords = [(p["lon"],p["lat"]) for p in way["geometry"]]
        if len(coords)<2:
            raise ValueError("Main road has incomplete geometry")
        features.append({"geometry":LineString(coords)})
    lines = gpd.GeoDataFrame(features,geometry="geometry",crs=config.WGS84) if features else gpd.GeoDataFrame(geometry=[],crs=config.WGS84)
    points = pd.DataFrame(pois["elements"]).rename(columns={"lon":"longitude","lat":"latitude"})
    if points.empty:
        points = pd.DataFrame(columns=["longitude","latitude"])
    assigned = assign_chargers_to_districts(points,boundaries)
    counts = assigned.groupby("district_key").size()
    rows=[]
    for i, district in enumerate(boundaries.itertuples()):
        polygon = gpd.GeoSeries([district.geometry],crs=boundaries.crs)
        local_crs = polygon.estimate_utm_crs()
        if local_crs is None:
            raise ValueError(f"Cannot choose local projection for {district.district_key}")
        projected = polygon.to_crs(local_crs).iloc[0]
        area = projected.area/config.METRES_PER_KM**2
        if area<=0:
            raise ValueError("District has no measurable area")
        candidates = lines.iloc[lines.sindex.query(district.geometry,predicate="intersects")]
        clipped = candidates.to_crs(local_crs).geometry.intersection(projected)
        length = clipped.union_all().length/config.METRES_PER_KM if len(clipped) else 0
        rows.append({"district_key":district.district_key,"area_km2":area,"road_km_per_km2":length/area,
                     "commercial_count":int(counts.get(district.district_key,0)),
                     "commercial_per_km2":counts.get(district.district_key,0)/area})
        if (i+1)%config.INDIA_DISTRICT_PROGRESS == 0:
            print(f"Local road/area calculations: {i+1}/{len(boundaries)}",flush=True)
    return pd.DataFrame(rows)


def scores(boundaries, ev, assigned, raw_assigned):
    table = boundaries[["district","district_key"]].merge(ev,on="district_key",validate="one_to_one")
    table["charger_count"],table["port_count"] = count_units(assigned,table.district_key)
    table["raw_charger_count"],table["raw_port_count"] = count_units(raw_assigned,table.district_key)
    table["data_flag"] = np.where(table.ev_total.notna(),"real","missing")
    return rank_districts(table)
