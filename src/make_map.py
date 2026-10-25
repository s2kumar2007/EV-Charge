"""
STEP 6 - Interactive map (Folium / Leaflet) -> outputs/tn_gap_map.html
Map position comes from the district boundaries; colours and options come from config.py.
"""
import html

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd

import config
from utils import OUTPUTS, PROCESSED, ensure_dirs

MAP_HTML = OUTPUTS / "tn_gap_map.html"


def main():
    ensure_dirs()
    districts = gpd.read_file(PROCESSED / "districts_scored.geojson")
    chargers = pd.read_csv(PROCESSED / "chargers_assigned.csv").fillna("")
    chargers = chargers[chargers["district"] != ""]            # only chargers inside the districts

    scores = districts.loc[districts["status"] == "ok", "gap_score"].dropna()
    colormap = None
    if len(scores):
        vmin, vmax = float(scores.min()), float(np.percentile(scores, config.COLOUR_SCALE_PERCENTILE))
        vmax = vmax if vmax > vmin else vmin + 1
        colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
        colormap.caption = (f"Gap score = EVs per public charger (colours capped at "
                            f"percentile {config.COLOUR_SCALE_PERCENTILE})")

    n = len(districts)
    districts["EVs"] = districts["ev_total"].map(lambda v: "no data" if pd.isna(v) else f"{int(v):,}")
    districts["Chargers"] = districts["charger_count"].astype(int).astype(str)
    districts["Gap score"] = [s if s != "ok" else f"{g:,.1f} EVs per charger"
                              for s, g in zip(districts["status"], districts["gap_score"])]
    districts["Rank"] = districts["rank"].map(
        lambda r: "not ranked" if pd.isna(r) else f"{int(r)} of {n} (1 = most underserved)")
    flag_text = {"real": "real", "synthetic": "SYNTHETIC placeholder - not real data", "missing": "no EV data"}
    districts["Data flag"] = districts["data_flag"].map(lambda f: flag_text.get(f, f))
    fields = ["district", "EVs", "Chargers", "Gap score", "Rank", "Data flag"]
    aliases = ["District", "EVs registered", "Public chargers", "Gap score", "Rank", "Data flag"]

    def style(feature):
        p = feature["properties"]
        if p["status"] == "no chargers":
            fill = config.NO_CHARGER_COLOUR
        elif p["status"] == "no EV data" or p["gap_score"] is None or colormap is None:
            fill = config.NO_DATA_COLOUR
        else:
            fill = colormap(min(p["gap_score"], colormap.vmax))
        return {"fillColor": fill, "fillOpacity": 0.75, "color": "#333333", "weight": 1,
                "dashArray": "6,4" if p["data_flag"] == "synthetic" else None}

    m = folium.Map(tiles=config.MAP_TILES)
    west, south, east, north = districts.total_bounds
    m.fit_bounds([[south, west], [north, east]])                 # position comes from the data

    folium.GeoJson(districts[fields + ["status", "gap_score", "data_flag", "geometry"]],
                   name="Districts (gap score)", style_function=style,
                   highlight_function=lambda f: {"weight": 3, "color": "#000000"},
                   tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases, sticky=True),
                   popup=folium.GeoJsonPopup(fields=fields, aliases=aliases)).add_to(m)

    layer = folium.FeatureGroup(name=f"Chargers ({len(chargers)})")
    for row in chargers.itertuples():
        popup = (f"<b>{html.escape(str(row.name) or '(unnamed)')}</b><br>"
                 f"Operator: {html.escape(str(row.operator) or 'unknown')}<br>Source: {html.escape(str(row.source))}")
        folium.CircleMarker(location=[row.latitude, row.longitude], radius=3, weight=1,
                            color=config.SOURCE_COLOURS.get(row.source, config.UNKNOWN_SOURCE_COLOUR),
                            fill=True, fill_opacity=0.9, popup=folium.Popup(popup, max_width=250)).add_to(layer)
    layer.add_to(m)
    folium.LayerControl().add_to(m)
    if colormap is not None:
        colormap.add_to(m)

    statuses = set(districts["status"])
    items = []
    if "no chargers" in statuses:
        items.append(f'<span style="background:{config.NO_CHARGER_COLOUR};display:inline-block;width:14px;'
                     f'height:14px;vertical-align:middle;"></span> No chargers')
    if "no EV data" in statuses:
        items.append(f'<span style="background:{config.NO_DATA_COLOUR};display:inline-block;width:14px;'
                     f'height:14px;vertical-align:middle;"></span> No EV data (not ranked)')
    if (districts["data_flag"] == "synthetic").any():
        items.append('<span style="border:2px dashed #333;display:inline-block;width:12px;height:12px;'
                     'vertical-align:middle;"></span> Dashed outline = synthetic EV count')
    for source in sorted(set(chargers["source"])):
        colour = config.SOURCE_COLOURS.get(source, config.UNKNOWN_SOURCE_COLOUR)
        items.append(f'<span style="color:{colour};font-size:16px;">&#9679;</span> Charger ({html.escape(source)})')
    if items:
        m.get_root().html.add_child(folium.Element(
            '<div style="position:fixed;bottom:30px;right:10px;z-index:9999;background:white;padding:8px 10px;'
            'border:1px solid #999;border-radius:4px;font-size:12px;line-height:1.6;">' + "<br>".join(items) + "</div>"))

    warnings = []
    n_syn = int((districts["data_flag"] == "synthetic").sum())
    n_missing = int((districts["data_flag"] == "missing").sum())
    if n_syn:
        warnings.append(f"{n_syn} of {n} districts use SYNTHETIC placeholder EV counts (not real data).")
    if n_missing:
        warnings.append(f"{n_missing} of {n} districts have no EV data and are not ranked.")
    warn_html = "".join(f"<br><b style='color:#b71c1c;'>WARNING: {w}</b>" for w in warnings)
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:10px;left:10px;z-index:9999;background:white;padding:8px 10px;'
        'border:1px solid #999;border-radius:4px;font-size:12px;max-width:430px;">'
        "Slice 0 prototype. Data: OpenStreetMap contributors (chargers), VAHAN (EV counts), "
        f"{html.escape(config.BOUNDARY_REPO)} (boundaries).{warn_html}</div>"))
    m.save(str(MAP_HTML))
    print(f"Map saved -> {MAP_HTML}")


if __name__ == "__main__":
    main()
