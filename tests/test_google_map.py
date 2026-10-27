"""Native map tests use fake keys, invented data and no internet."""
import json
from pathlib import Path
import re
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box
import config
import make_google_map as google_map


def inputs():
    boundaries = gpd.GeoDataFrame({"district": ["Same", "Same"], "district_key": ["a", "b"], "ev_total": [np.nan, 10]},
        geometry=[box(0,0,1,1), box(1,0,2,1)], crs=config.WGS84)
    chargers = pd.DataFrame({"latitude": [.5, .5], "longitude": [.5, 3], "district_key": ["a", None],
        "name": ["Test </script><script>bad()</script>", "Other"], "ports": [2, 1], "ports_known": [True, False]})
    return boundaries, chargers


def test_payload_preserves_missing_and_national_ids():
    boundaries, chargers = inputs()
    index = pd.DataFrame({"district_key": ["a", "b"], "composite_score": [None, .5], "population": [None, 100]})
    coverage = pd.DataFrame({"district_key": ["a", "b"], "charger_count": [1, 0]})
    data = google_map.prepare_payload(boundaries, chargers, index, coverage)
    assert data["summary"]["districts"] == 2 and data["summary"]["mapped_chargers"] == 1
    assert data["summary"]["charger_records"] == 2
    props = data["districts"]["features"][0]["properties"]
    assert props["ev_total"] is None and props["composite_score"] is None and props["population"] is None
    assert data["districts"]["features"][1]["properties"]["charger_count"] == 0
    assert data["bounds"] == [0,0,2,1]


def test_render_escapes_script_labels_and_uses_configured_loader():
    data = google_map.prepare_payload(*inputs())
    document = google_map.render_document(data, "fake-browser-key")
    assert "Test </script>" not in document
    match = re.search(r'<script id="chargegap-data" type="application/json">(.*?)</script>', document, re.S)
    assert json.loads(match.group(1)) == data
    assert 'key=fake-browser-key' in document and 'loading=async' in document
    assert 'gm_authFailure' in document and 'HTTP referrer restrictions' in document
    assert 'new google.maps.Data' in document and 'fitBounds' in document
    assert 'No data for this indicator' in document
    assert '__CHARGEGAP_' not in document


def test_missing_key_and_bad_coordinates_are_explicit():
    with pytest.raises(ValueError, match=".env"):
        google_map.render_document({}, "")
    boundaries, chargers = inputs()
    chargers.loc[0, "latitude"] = float('inf')
    with pytest.raises(ValueError, match="invalid coordinates"):
        google_map.prepare_payload(boundaries, chargers)


def test_duplicate_polygon_ids_rejected():
    boundaries, chargers = inputs()
    boundaries["district_key"] = "duplicate"
    with pytest.raises(ValueError, match="unique"):
        google_map.prepare_payload(boundaries, chargers)


def test_file_generation_uses_env_without_logging_key(tmp_path, monkeypatch, capsys):
    boundaries, chargers = inputs()
    processed, output = tmp_path / "processed", tmp_path / "output"
    processed.mkdir(); output.mkdir()
    boundaries.to_file(processed / config.GOOGLE_MAPS_BOUNDARY_INPUT, driver="GeoJSON")
    chargers.to_csv(processed / config.GOOGLE_MAPS_CHARGER_INPUT, index=False)
    monkeypatch.setenv(config.GOOGLE_MAPS_API_KEY_ENV, "fake-local-test-key")
    report = google_map.main(processed, output)
    assert report["districts"] == 2 and (output / config.GOOGLE_MAPS_INDIA_FILENAME).exists()
    assert "fake-local-test-key" not in capsys.readouterr().out
    assert "fake-local-test-key" not in (output / config.GOOGLE_MAPS_INDIA_FILENAME).with_suffix('.manifest.json').read_text()


def test_no_key_does_not_overwrite_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(google_map, "load_dotenv", lambda *a: None)
    monkeypatch.delenv(config.GOOGLE_MAPS_API_KEY_ENV, raising=False)
    result = google_map.main(tmp_path, tmp_path)
    assert result["status"] == "missing API key"
    assert not (tmp_path / config.GOOGLE_MAPS_INDIA_FILENAME).exists()


def test_google_only_runner_reuses_saved_outputs(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import run_india
    monkeypatch.setattr(run_india, "ensure_dirs", lambda: None)
    monkeypatch.setattr(run_india, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(run_india, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(run_india.india_data, "load_boundaries", lambda: pytest.fail("must not reload boundaries"))
    calls = []
    monkeypatch.setattr(run_india.make_google_map, "main", lambda p, o: calls.append((p, o)) or {"status": "fake generated"})
    result = run_india.main(["--google-map-only", "--offline"])
    assert result["status"] == "fake generated" and len(calls) == 1


def test_inline_ui_with_fake_google_api(tmp_path):
    import shutil, subprocess
    if not shutil.which("node"):
        pytest.skip("Node is needed for the offline JavaScript execution test")
    payload = google_map.prepare_payload(*inputs())
    document = google_map.render_document(payload, "fake-node-test-key")
    script = re.search(r'<script>(.*?)</script>', document, re.S).group(1)
    options = json.loads(re.search(r'<script id="chargegap-options" type="application/json">(.*?)</script>', document, re.S).group(1))
    harness = r"""
const vm=require('vm');const assert=require('assert');
class Element {
 constructor(){this.textContent='';this.value='';this.handlers={};this.children=[];}
 appendChild(node){this.children.push(node);}
 addEventListener(name,callback){this.handlers[name]=callback;}
}
const nodes={};const layers=[];
const document={getElementById:id=>nodes[id]||(nodes[id]=new Element()),createElement:()=>new Element(),createTextNode:text=>({textContent:text})};
class Feature {
 constructor(raw){this.raw=raw;}
 getProperty(name){return this.raw.properties[name];}
 getGeometry(){return {forEachLatLng:fn=>fn({lat:()=>.5,lng:()=>.5}),get:()=>({lat:()=>.5,lng:()=>.5})};}
}
class Data {
 constructor({map}){this.map=map;this.features=[];this.listeners={};layers.push(this);}
 addGeoJson(raw){this.features=raw.features.map(f=>new Feature(f));}
 setStyle(style){this.style=style;}
 forEach(fn){this.features.forEach(fn);}
 addListener(event,fn){this.listeners[event]=fn;}
 setMap(map){this.map=map;}
}
class Bounds {extend(){return this;}getCenter(){return {lat:()=>.5,lng:()=>.5};}}
class InfoWindow {setContent(c){this.content=c;}setPosition(){}open(){}close(){}}
const google={maps:{Map:class {fitBounds(){}},Data,LatLngBounds:Bounds,InfoWindow,SymbolPath:{CIRCLE:'circle'}}};
document.getElementById('chargegap-data').textContent=JSON.stringify(PAYLOAD);
document.getElementById('chargegap-options').textContent=JSON.stringify(OPTIONS);
const sandbox={window:{},document,google,URL,setTimeout:()=>{}};
vm.runInNewContext(SCRIPT,sandbox);
sandbox.window.initChargeGapGoogleMap();
assert(nodes.status.textContent.includes('National snapshot loaded'));
assert.strictEqual(nodes['district-count'].textContent,2);
assert.strictEqual(nodes['charger-count'].textContent,1);
assert.strictEqual(nodes.find.disabled,false);
nodes.layer.value='ev_pressure';nodes.layer.handlers.change();
assert(nodes.legend.textContent.includes('No data for this indicator'));
assert.strictEqual(layers[0].style(layers[0].features[0]).fillColor,OPTIONS.missingColour);
nodes['district-search'].value='Same';nodes.find.handlers.click();
assert(nodes.selection.textContent.includes('Several districts match'));
nodes['district-search'].value='Same [a]';nodes.find.handlers.click();
assert(nodes.selection.textContent.includes('Same'));
nodes['charger-toggle'].handlers.change({target:{checked:false}});
assert.strictEqual(layers[1].map,null);
layers[1].listeners.click({feature:layers[1].features[0]});
sandbox.window.gm_authFailure();assert(nodes.status.textContent.includes('could not load or authorise'));
console.log('Offline Google Maps UI: PASS');
"""
    harness = 'const PAYLOAD='+json.dumps(payload)+';const OPTIONS='+json.dumps(options)+';const SCRIPT='+json.dumps(script)+';\n'+harness
    path = tmp_path / "offline_google_map.cjs"
    path.write_text(harness, encoding="utf-8")
    result = subprocess.run(["node", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Offline Google Maps UI: PASS" in result.stdout
