"""Offline national tests: small invented binary extracts and polygon IDs."""
import struct
import zlib
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box
import config
import extract_india
import india_data
import pbf_reader
import dedupe_chargers


def vint(n):
    out=bytearray()
    while n>127:
        out.append((n&127)|128); n >>= 7
    return bytes(out)+bytes([n])


def field(n,value):
    return vint(n*8+2)+vint(len(value))+value


def scalar(n,value):
    return vint(n*8)+vint(value)


def packed(n,values,signed=False):
    return field(n,b''.join(vint((v<<1)^(v>>63) if signed else v) for v in values))


def block(payload):
    blob=scalar(2,len(payload))+field(3,zlib.compress(payload))
    header=field(1,b'OSMData')+scalar(3,len(blob))
    return struct.pack('>I',len(header))+header+blob


def invented_pbf(path):
    # Two nodes, one tagged charger/shop. A charging way and relation overlap it.
    strings=[b'',b'amenity',b'charging_station',b'capacity',b'4',b'highway',b'primary',b'shop',b'yes']
    table=field(1,b''.join(field(1,s) for s in strings))
    way=scalar(1,10)+packed(2,[1,5])+packed(3,[2,6])+packed(8,[1,1],True)
    relation=scalar(1,20)+packed(2,[1])+packed(3,[2])+packed(9,[10],True)+packed(10,[1])
    ways=table+field(2,field(3,way)+field(4,relation))
    dense=packed(1,[1,1],True)+packed(8,[100000,10000],True)+packed(9,[100000,10000],True)+packed(10,[1,2,3,4,7,8,0,0])
    nodes=table+field(2,field(2,dense))
    path.write_bytes(block(nodes)+block(ways))


def boundaries():
    return gpd.GeoDataFrame({'district':['Same','Same'],'district_key':['id1','id2']},geometry=[box(0,0,1,1),box(1,0,2,1)],crs=config.WGS84)


def test_pbf_extract_and_cache(tmp_path,monkeypatch):
    path=tmp_path/'invented.pbf'
    invented_pbf(path)
    monkeypatch.setattr(extract_india,'RAW',tmp_path)
    result=extract_india.extract(path)
    assert len(result['chargers'])==3 and len(result['roads']['elements'])==1 and len(result['pois']['elements'])==1
    node=next(r for r in result['chargers'] if r['source_id']=='node/1')
    assert node['latitude']==pytest.approx(.01) and node['ports']==4 and node['ports_known']
    way=next(r for r in result['chargers'] if r['source_id']=='way/10')
    assert way['latitude']==pytest.approx(.0105)
    monkeypatch.setattr(extract_india,'blocks',lambda *a,**k:pytest.fail('cache not used'))
    assert extract_india.extract(path)==result


def test_truncated_pbf_fails(tmp_path):
    path=tmp_path/'broken.pbf'; path.write_bytes(b'\x00\x00')
    with pytest.raises(ValueError,match='Truncated'):
        list(pbf_reader.blocks(path))


def test_repeated_names_use_dataset_ids(tmp_path):
    b=boundaries().rename(columns={'district':'shapeName','district_key':'shapeID'})
    path=tmp_path/'districts.geojson'; b.to_file(path,driver='GeoJSON')
    loaded=india_data.load_boundaries(path)
    assert len(loaded)==2 and loaded.district_key.is_unique
    b['shapeID']='same'; b.to_file(path,driver='GeoJSON')
    with pytest.raises(ValueError,match='unique'):
        india_data.load_boundaries(path)


def test_verified_input_gate(tmp_path):
    path=tmp_path/'population.csv'; audit=tmp_path/'audit.csv'
    pd.DataFrame({'district_key':['id1','id2','other'],'population':[123,456,789],
        'source_url':['test']*3,'observation_date':['2025']*3,'boundary_compatible':[True,False,True]}).to_csv(path,index=False)
    result=india_data.read_verified_input(boundaries(),path,'population',audit)
    assert result.population.iloc[0]==123 and pd.isna(result.population.iloc[1])
    assert set(pd.read_csv(audit).resolution_status)=={'accepted','boundary compatibility unverified','unknown boundary ID'}


def test_national_ev_periods_cannot_mix(tmp_path):
    path=tmp_path/'ev.csv'
    pd.DataFrame({'district_key':['id1','id2'],'ev_total':[10,20],'source_url':['test']*2,
       'observation_date':['2025']*2,'boundary_compatible':[True]*2,'ev_measure':['annual']*2,
       'period_start':['2024','2025'],'period_end':['2024','2025']}).to_csv(path,index=False)
    with pytest.raises(ValueError,match='mix'):
        india_data.read_verified_input(boundaries(),path,'ev_total',tmp_path/'audit.csv')


def test_missing_input_never_invents(tmp_path):
    path=tmp_path/'absent.csv'
    result=india_data.read_verified_input(boundaries(),path,'ev_total',tmp_path/'audit.csv')
    assert result.ev_total.isna().all()
    assert path.with_name('absent_TEMPLATE.csv').exists()


def test_geodesic_dedup_across_zone_border():
    from pyproj import Geod
    lon,lat,_=Geod(ellps='WGS84').fwd(6,10,90,10)
    raw=pd.DataFrame({'source':['OSM','OCM'],'source_id':['a','b'],'name':['Test']*2,'operator':['Test']*2,
        'longitude':[6,lon],'latitude':[10,lat],'ports':[2,4],'ports_known':[True]*2})
    merged,audit=dedupe_chargers.deduplicate(raw,geodesic=True)
    assert len(merged)==1 and merged.iloc[0].ports==4 and len(audit)==2
    assert merged.iloc[0].spread_m==pytest.approx(5,abs=.01)


def test_national_roads_and_empty_counts():
    result=india_data.osm_indicators(boundaries(),{'elements':[{'geometry':[{'lon':.5,'lat':.5},{'lon':1.5,'lat':.5}]}]}, {'elements':[]})
    assert result.road_km_per_km2.gt(0).all() and result.commercial_count.eq(0).all()
