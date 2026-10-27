"""Build India-wide outputs from the supplied PBF and district polygons.

This entry point keeps state outputs untouched. It always produces supply
coverage; demand rankings require verified national EV/population inputs.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
import config
import dedupe_chargers
import gap_index
import hotspots
import india_data
import make_map
import make_google_map
from build_scores import assign_chargers_to_districts
from extract_india import extract, source_identity
from pbf_reader import header_metadata
from refresh_india import download_latest
from run_all import run_step
from utils import ROOT, RAW, PROCESSED, OUTPUTS, ensure_dirs, save_json


@contextmanager
def output_locations(processed, output):
    # Existing map/index code writes through module paths. Restore them even
    # on error so calling the state runner in the same process stays safe.
    edits=[(make_map,'PROCESSED',processed),(make_map,'OUTPUTS',output),
           (make_map,'MAP_HTML',output/config.INDIA_MAP_FILE),
           (gap_index,'OUTPUTS',output),(hotspots,'OUTPUTS',output),
           (config,'MAP_SOURCE_NOTE',config.INDIA_MAP_NOTE)]
    previous=[(module,key,getattr(module,key)) for module,key,_ in edits]
    try:
        for module,key,value in edits:
            setattr(module,key,value)
        yield
    finally:
        for module,key,value in previous:
            setattr(module,key,value)


def reconcile(raw,assigned,table):
    inside=int(assigned.district_key.notna().sum()); outside=int(assigned.district_key.isna().sum())
    if len(raw)!=inside+outside or int(table.charger_count.sum())!=inside:
        raise ValueError('National charger counts do not reconcile')
    return {'fetched':len(raw),'inside':inside,'outside':outside}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--google-map-only', action='store_true', help='Generate Google Maps HTML from existing national outputs without fetching or recalculating data')
    parser.add_argument('--refresh',action='store_true',help='Re-extract local PBF; does not download a new snapshot')
    parser.add_argument('--offline',action='store_true',help='Also prohibit map-library downloads')
    parser.add_argument('--download-latest',action='store_true',help='Download the current free Geofabrik India snapshot before processing')
    args=parser.parse_args(argv)
    if args.offline and args.download_latest:
        parser.error('--offline cannot be combined with --download-latest')
    config.OFFLINE=args.offline
    config.REFRESH_DOWNLOADS=args.refresh
    ensure_dirs()
    processed=PROCESSED/config.INDIA_OUTPUT_FOLDER; output=OUTPUTS/config.INDIA_OUTPUT_FOLDER
    processed.mkdir(parents=True,exist_ok=True); output.mkdir(parents=True,exist_ok=True)
    if args.google_map_only:
        return run_step('India: Google Maps from saved national outputs', make_google_map.main, processed, output)
    with output_locations(processed,output):
        boundaries=run_step('India 1: supplied district boundaries',india_data.load_boundaries)
        boundaries[['district','district_key']].to_csv(output/'district_directory.csv',index=False)
        duplicates=boundaries[boundaries.district.duplicated(keep=False)]
        duplicates[['district','district_key']].to_csv(output/'repeated_district_names.csv',index=False)
        pbf_path=run_step('India live refresh',download_latest) if args.download_latest else ROOT/config.INDIA_PBF_FILE
        data=run_step('India 2: locally extract chargers, roads and commercial nodes',extract,path=pbf_path,refresh=args.refresh)
        raw=pd.DataFrame(data['chargers'],columns=['source','name','operator','latitude','longitude','source_id','ports','ports_known'])
        raw.to_csv(processed/'chargers_raw.csv',index=False)
        merged,audit=run_step('India 3: geodesic deduplication',dedupe_chargers.deduplicate,raw,geodesic=True)
        merged.to_csv(processed/'chargers_deduplicated.csv',index=False)
        audit.to_csv(processed/'chargers_merge_audit.csv',index=False)
        sensitivity=pd.DataFrame([{'radius_m':r,'raw_count':len(raw),
            'charger_count':len(dedupe_chargers.deduplicate(raw,r,geodesic=True)[0])} for r in config.DEDUP_RADII_M])
        sensitivity.to_csv(output/'dedup_radius_sensitivity.csv',index=False)
        sample=merged.sample(n=min(len(merged),config.VALIDATION_SAMPLE_SIZE),random_state=config.VALIDATION_SEED).copy()
        sample['checked_ok']=''; sample['notes']=''
        sample_path=output/'validation_sample.csv'
        if sample_path.exists():
            sample_path=output/f"validation_sample_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.csv"
        sample.to_csv(sample_path,index=False)
        ev=run_step('India 4: verified national EV input',india_data.read_verified_input,boundaries,
                    RAW/config.INDIA_EV_FILE,'ev_total',processed/'ev_input_audit.csv')
        population=run_step('India 5: verified compatible population',india_data.read_verified_input,boundaries,
                    RAW/config.INDIA_POPULATION_FILE,'population',processed/'population_input_audit.csv')
        population['population_source']=population.get('source_url',pd.Series('missing',index=population.index)).fillna('missing')
        population.to_csv(processed/'district_population.csv',index=False)
        raw_assigned=assign_chargers_to_districts(raw,boundaries)
        assigned=assign_chargers_to_districts(merged,boundaries)
        for frame,name in [(raw_assigned,'chargers'),(assigned,'chargers_deduplicated')]:
            frame.to_csv(processed/f'{name}_assigned.csv',index=False)
            frame[frame.district_key.isna()].to_csv(processed/f'{name}_unassigned.csv',index=False)
        basic=india_data.scores(boundaries,ev,raw_assigned,raw_assigned)
        selected=india_data.scores(boundaries,ev,assigned,raw_assigned)
        basic.to_csv(output/'district_gap_scores.csv',index=False)
        selected.to_csv(output/'district_gap_scores_deduplicated.csv',index=False)
        raw_counts=reconcile(raw,raw_assigned,basic); dedup_counts=reconcile(merged,assigned,selected)
        osm=run_step('India 6: district-local roads and commercial densities',india_data.osm_indicators,boundaries,data['roads'],data['pois'])
        osm.to_csv(processed/'district_osm_indicators.csv',index=False)
        index=run_step('India 7: national composite and weight sensitivity',gap_index.main,selected,population,osm)
        hot=run_step('India 8: national Moran and Gi-star',hotspots.main,boundaries,index)
        # Simplification affects display only. Calculations above use full polygons.
        display=boundaries.copy()
        for i,row in boundaries.iterrows():
            polygon=gpd.GeoSeries([row.geometry],crs=boundaries.crs)
            local=polygon.estimate_utm_crs()
            display.loc[i,'geometry']=polygon.to_crs(local).simplify(config.INDIA_MAP_SIMPLIFY_M,preserve_topology=True).to_crs(boundaries.crs).iloc[0]
        display=display.merge(basic,on=['district','district_key'],validate='one_to_one')
        display.to_file(processed/'districts_scored.geojson',driver='GeoJSON')
        snapshot=header_metadata(pbf_path) if pbf_path.exists() else {'snapshot_utc':None}
        config.MAP_SOURCE_NOTE += f" OSM snapshot UTC: {snapshot.get('snapshot_utc') or 'unknown'}; file: {data['source']['file']}. Display polygons simplified; calculations use full geometry."
        run_step('India 9: interactive national map',make_map.main,coverage=selected)
        manifest={'osm_header':snapshot,'generated_utc':datetime.now(timezone.utc).isoformat(),'boundary_source':boundaries.attrs.get('source_manifest', {'provider':config.BOUNDARY_PROVIDER, 'warning':'No boundary manifest provided by caller'}),
            'osm_source':data['source'],'district_count':len(boundaries),'raw_chargers':raw_counts,'deduplicated_chargers':dedup_counts,
            'duplicates_removed':len(raw)-len(merged),'road_ways':len(data['roads']['elements']),'commercial_nodes':len(data['pois']['elements']),
            'districts_with_ev':int(basic.ev_total.notna().sum()),'districts_with_population':int(population.population.notna().sum()),
            'composite_ranked':int(index['rank'].notna().sum()),'synthetic':bool(basic.data_flag.astype(str).str.contains('synthetic',case=False).any()),
            'pysal_installed':bool(importlib.util.find_spec('libpysal') and importlib.util.find_spec('esda')),
            'limitations':['OSM snapshot refreshed on request, not a continuously live fleet feed','Southern extract overlaps national extract and is excluded',
                'Boundary IDs are dataset-specific, not LGD codes','Boundary year/licence require matching release metadata',
                'National EV and population inputs require explicit provenance and compatible boundaries',
                'OSM coverage/public access/uptime incomplete; review charger merge validation sample']}
        save_json(output/'run_manifest.json',manifest)
        if config.GOOGLE_MAPS_ENABLED:
            manifest['google_maps'] = run_step('India 10: Google Maps national view', make_google_map.main, processed, output)
            save_json(output/'run_manifest.json',manifest)
        print('\nNational checks:',manifest,flush=True)
        print('\nRadius sensitivity:\n'+sensitivity.to_string(index=False),flush=True)
        print('\nConfidence:\n'+merged.confidence.describe().to_string(),flush=True)
        print(f"\nOpen {output/config.INDIA_MAP_FILE}",flush=True)
        return manifest


if __name__=='__main__':
    main()
