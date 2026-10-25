"""
STEP 6 - Interactive map (Folium / Leaflet).

Reads the files made by build_scores.py and writes outputs/tn_gap_map.html:
  * districts coloured by gap_score (yellow = few EVs per charger, dark red = many),
  * a separate purple colour for districts with NO chargers,
  * small dots for each charger (popup: name, operator, source),
  * hover tooltip + click popup per district (EVs, chargers, gap score, rank, data flag),
  * a visible note about data sources and synthetic values.
"""
import html

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd

from utils import OUTPUTS, PROCESSED, ensure_dirs

MAP_HTML = OUTPUTS / "tn_gap_map.html"
NO_CHARGER_COLOUR = "#6a1b9a"   # purple: clearly different from the yellow-red scale
SOURCE_COLOURS = {"OSM": "#1565c0", "OCM": "#2e7d32"}


def main():
    ensure_dirs()
    districts = gpd.read_file(PROCESSED / "districts_scored.geojson")
    chargers = pd.read_csv(PROCESSED / "chargers_assigned.csv").fillna("")

    # ---- Colour scale ----
    # A few districts can have huge scores. We cap the colour scale at the 95th
    # percentile so the other districts still show visible differences.
    scores = districts.loc[districts["status"] == "ok", "gap_score"].dropna()
    colormap = None
    if len(scores):
        vmin, vmax = float(scores.min()), float(np.percentile(scores, 95))
        if vmax <= vmin:
            vmax = vmin + 1
        colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
        colormap.caption = "Gap score = EVs per public charger (colours capped at 95th percentile)"

    # ---- Text shown in tooltip / popup (prepared here so missing values look clean) ----
    districts["EVs"] = districts["ev_total"].map(lambda v: f"{int(v):,}")
    districts["Chargers"] = districts["charger_count"].astype(int).astype(str)
    districts["Gap score"] = [
        "no chargers" if s == "no chargers" else f"{g:,.1f} EVs per charger"
        for s, g in zip(districts["status"], districts["gap_score"])
    ]
    districts["Rank"] = districts["rank"].map(lambda r: f"{int(r)} of {len(districts)} (1 = most underserved)")
    districts["Data flag"] = districts["data_flag"].map(
        lambda f: "real" if f == "real" else "SYNTHETIC placeholder - not real data")
    fields = ["district", "EVs", "Chargers", "Gap score", "Rank", "Data flag"]
    aliases = ["District", "EVs registered", "Public chargers", "Gap score", "Rank", "Data flag"]

    def style(feature):
        props = feature["properties"]
        if props["status"] == "no chargers":
            fill = NO_CHARGER_COLOUR
        elif colormap is not None and props["gap_score"] is not None:
            fill = colormap(min(props["gap_score"], colormap.vmax))
        else:
            fill = "#cccccc"
        # Synthetic districts get a dashed outline so they stand out.
        dashed = "6,4" if props["data_flag"] == "synthetic" else None
        return {"fillColor": fill, "fillOpacity": 0.75, "color": "#333333", "weight": 1, "dashArray": dashed}

    m = folium.Map(location=[10.9, 78.4], zoom_start=7, tiles="OpenStreetMap")

    folium.GeoJson(
        districts[fields + ["status", "gap_score", "data_flag", "geometry"]],
        name="Districts (gap score)",
        style_function=style,
        highlight_function=lambda f: {"weight": 3, "color": "#000000"},
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases, sticky=True),
        popup=folium.GeoJsonPopup(fields=fields, aliases=aliases),
    ).add_to(m)

    # ---- Chargers as small dots ----
    layer = folium.FeatureGroup(name=f"Chargers ({len(chargers)})")
    for row in chargers.itertuples():
        popup = (f"<b>{html.escape(str(row.name) or '(unnamed)')}</b><br>"
                 f"Operator: {html.escape(str(row.operator) or 'unknown')}<br>"
                 f"Source: {html.escape(str(row.source))}")
        folium.CircleMarker(
            location=[row.latitude, row.longitude], radius=3, weight=1,
            color=SOURCE_COLOURS.get(row.source, "#000000"), fill=True, fill_opacity=0.9,
            popup=folium.Popup(popup, max_width=250),
        ).add_to(layer)
    layer.add_to(m)
    folium.LayerControl().add_to(m)

    if colormap is not None:
        colormap.add_to(m)

    # ---- Legend for the special colours (bottom right) ----
    legend = f"""
    <div style="position:fixed; bottom:30px; right:10px; z-index:9999; background:white; padding:8px 10px;
                border:1px solid #999; border-radius:4px; font-size:12px; line-height:1.6;">
      <span style="background:{NO_CHARGER_COLOUR}; display:inline-block; width:14px; height:14px;
                   vertical-align:middle;"></span> No chargers (most underserved)<br>
      <span style="border:2px dashed #333; display:inline-block; width:12px; height:12px;
                   vertical-align:middle;"></span> Dashed outline = synthetic EV count<br>
      <span style="color:{SOURCE_COLOURS['OSM']}; font-size:16px;">&#9679;</span> Charger (OpenStreetMap)
      <span style="color:{SOURCE_COLOURS['OCM']}; font-size:16px;">&#9679;</span> Charger (OpenChargeMap)
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))

    # ---- Visible note (bottom left) ----
    n_syn = int((districts["data_flag"] == "synthetic").sum())
    warning = ""
    if n_syn:
        warning = (f"<br><b style='color:#b71c1c;'>WARNING: {n_syn} of {len(districts)} districts use SYNTHETIC "
                   f"placeholder EV counts (not real data).</b>")
    note = f"""
    <div style="position:fixed; bottom:10px; left:10px; z-index:9999; background:white; padding:8px 10px;
                border:1px solid #999; border-radius:4px; font-size:12px; max-width:430px;">
      Slice 0 prototype. Data sources: OpenStreetMap, VAHAN (manual export), DataMeet boundaries.
      Synthetic values are flagged.{warning}
    </div>"""
    m.get_root().html.add_child(folium.Element(note))

    m.save(str(MAP_HTML))
    print(f"Map saved -> {MAP_HTML}")


if __name__ == "__main__":
    main()
