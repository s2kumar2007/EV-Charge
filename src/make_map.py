"""Folium map with the original gap layer and additional Slice 1 overlays."""
import html
import json
import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import config
from map_links import google_links
from utils import OUTPUTS, PROCESSED, ensure_dirs

MAP_HTML = OUTPUTS / config.MAP_FILENAME


def format_value(value):
    return "no data" if pd.isna(value) else html.escape(str(value))


def colour_scale(values, palette, caption):
    numbers = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    low = float(numbers.min()) if len(numbers) else 0
    high = float(np.percentile(numbers, config.COLOUR_SCALE_PERCENTILE)) if len(numbers) else config.COLOUR_CONSTANT_SPAN
    if high <= low:
        high = low + config.COLOUR_CONSTANT_SPAN
    scale = cm.LinearColormap(palette, vmin=low, vmax=high, caption=caption)
    return scale


def polygon_style(fill, synthetic=False):
    return {"fillColor": fill, "fillOpacity": config.POLYGON_OPACITY,
            "color": config.OUTLINE_COLOUR, "weight": config.OUTLINE_WEIGHT,
            "dashArray": config.SYNTHETIC_DASH if synthetic else None}


def add_polygon_layer(m, districts, name, fields, style, show=True):
    # Escape labels supplied by CSVs before inserting them into popup HTML.
    view = districts.copy()
    # GeoJSON readers may recognise source dates as timestamps. Leaflet needs
    # JSON strings, not Python timestamp objects, even for non-popup columns.
    for column in view.columns:
        if pd.api.types.is_datetime64_any_dtype(view[column]):
            view[column] = view[column].map(lambda value: value.isoformat() if pd.notna(value) else None)
    popup_fields = []
    for field in fields:
        if field not in view:
            continue
        label = f"display_{field}"
        view[label] = view[field].map(format_value)
        popup_fields.append(label)
    folium.GeoJson(view, name=name, show=show, style_function=style,
                   highlight_function=lambda feature: {"weight": config.HIGHLIGHT_WEIGHT, "color": config.HIGHLIGHT_COLOUR},
                   tooltip=folium.GeoJsonTooltip(fields=popup_fields, aliases=[c.removeprefix("display_") for c in popup_fields]),
                   popup=folium.GeoJsonPopup(fields=popup_fields, aliases=[c.removeprefix("display_") for c in popup_fields])).add_to(m)


def cache_map_assets(document):
    """Keep the existing map API while sharing the audited cache implementation."""
    from cache_map_assets import rewrite_assets
    return rewrite_assets(document, MAP_HTML.parent)


def main(include_slice1=True, coverage=None):
    ensure_dirs()
    districts = gpd.read_file(PROCESSED / "districts_scored.geojson")
    raw = pd.read_csv(PROCESSED / "chargers_assigned.csv").fillna({"name": "", "operator": ""})
    raw = raw[raw.district.notna()]
    m = folium.Map(tiles=config.MAP_TILES)
    west, south, east, north = districts.total_bounds
    m.fit_bounds([[south, west], [north, east]])
    scale = colour_scale(districts.loc[districts.status == "ok", "gap_score"], config.MAP_PALETTE,
                         f"Slice 0: EVs per {config.GAP_UNIT}; colour cap p{config.COLOUR_SCALE_PERCENTILE}")

    def basic_style(feature):
        p = feature["properties"]
        if p["status"] == "no EV data":
            fill = config.NO_DATA_COLOUR
        elif p["status"] == "no chargers":
            fill = config.NO_CHARGER_COLOUR
        else:
            fill = scale(min(p["gap_score"], scale.vmax))
        return polygon_style(fill, "synthetic" in str(p["data_flag"]).lower())

    add_polygon_layer(m, districts, "Districts (gap score)",
                      ["district", "district_key", "ev_total", "ev_year", "ev_measure", "charger_count", "port_count", "gap_score", "gap_unit", "rank", "data_flag", "status"], basic_style, show=coverage is None)
    scale.add_to(m)
    if coverage is not None:
        cover = districts[["district", "district_key", "geometry"]].merge(
            coverage[["district_key", "charger_count", "port_count"]], on="district_key", validate="one_to_one")
        cover_scale = colour_scale(cover.charger_count, config.MAP_PALETTE, "Mapped deduplicated stations (supply only)")
        def coverage_style(feature):
            return polygon_style(cover_scale(min(feature["properties"]["charger_count"], cover_scale.vmax)))
        add_polygon_layer(m, cover, "Charger coverage (supply only)",
                          ["district", "district_key", "charger_count", "port_count"], coverage_style)
        cover_scale.add_to(m)
    raw_layer = folium.FeatureGroup(name="Chargers (raw source records)", show=not include_slice1)
    for row in raw.itertuples():
        popup = f"<b>{html.escape(str(row.name) or '(unnamed)')}</b><br>Operator: {html.escape(str(row.operator) or 'unknown')}<br>Source: {html.escape(str(row.source))}"
        popup += google_links(row.latitude, row.longitude)
        folium.CircleMarker([row.latitude, row.longitude], radius=config.MARKER_RADIUS,
                            color=config.SOURCE_COLOURS.get(row.source, config.UNKNOWN_SOURCE_COLOUR),
                            weight=config.OUTLINE_WEIGHT, fill=True, fill_opacity=config.MARKER_OPACITY,
                            popup=folium.Popup(popup, max_width=config.POPUP_MAX_WIDTH)).add_to(raw_layer)
    raw_layer.add_to(m)
    excluded = 0
    population_labels = []
    if include_slice1 and (OUTPUTS / "district_gap_index.csv").exists():
        index = pd.read_csv(OUTPUTS / "district_gap_index.csv")
        hotspots = pd.read_csv(OUTPUTS / "district_hotspots.csv")
        geo = districts[["district_key", "geometry"]].merge(index, on="district_key", how="left").merge(
            hotspots.drop(columns=["district"], errors="ignore"), on="district_key", how="left")
        excluded = int(geo["rank"].isna().sum())
        population_labels = index.get("population_indicator_label", pd.Series(dtype=str)).dropna().unique().tolist()
        composite_scale = colour_scale(geo.composite_score, config.MAP_PALETTE, "Composite demand gap (entropy weights)")
        def composite_style(feature):
            p = feature["properties"]
            score = p.get("composite_score")
            fill = composite_scale(min(score, composite_scale.vmax)) if score is not None else config.NO_DATA_COLOUR
            return polygon_style(fill, "synthetic" in str(p.get("data_flag", "")).lower())
        fields = ["district", *config.INDICATORS, "population_source", "composite_score", "rank", "min_rank", "max_rank", "top_k_share", "class_raw", "class_fdr", "index_status", "missing_indicators", "data_flag"]
        add_polygon_layer(m, geo, "Composite index", fields, composite_style, show=False)
        composite_scale.add_to(m)
        def hotspot_style(feature):
            p = feature["properties"]
            label = str(p.get("class_fdr", "not tested"))
            colour = config.HOT_COLOUR if label.startswith("hot spot") else config.COLD_COLOUR if label.startswith("cold spot") else config.NOT_SIGNIFICANT_COLOUR if label == "not significant" else config.NO_DATA_COLOUR
            return polygon_style(colour, "synthetic" in str(p.get("data_flag", "")).lower())
        add_polygon_layer(m, geo, "Hotspots (Gi*)", fields + ["z_score", "p_value", "p_value_fdr", "reason"], hotspot_style, show=False)
        if config.DEDUP_ENABLED and (PROCESSED / "chargers_deduplicated_assigned.csv").exists():
            merged = pd.read_csv(PROCESSED / "chargers_deduplicated_assigned.csv").fillna({"name": "", "operator": ""})
            confidence_scale = cm.LinearColormap(config.CONFIDENCE_PALETTE, vmin=0, vmax=1, caption="Charger confidence (heuristic, not probability)")
            layer = folium.FeatureGroup(name="Chargers (deduplicated, coloured by confidence)")
            for row in merged[merged.district.notna()].itertuples():
                popup = "<br>".join(f"{key}: {format_value(getattr(row, key))}" for key in ["name", "operator", "sources", "n_source_records", "ports", "ports_known", "confidence"])
                popup += google_links(row.latitude, row.longitude)
                folium.CircleMarker([row.latitude, row.longitude], radius=config.MARKER_RADIUS, color=confidence_scale(row.confidence),
                                    weight=config.OUTLINE_WEIGHT, fill=True, fill_opacity=config.MARKER_OPACITY,
                                    popup=folium.Popup(popup, max_width=config.POPUP_MAX_WIDTH)).add_to(layer)
            layer.add_to(m)
            confidence_scale.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    synthetic = int(districts.data_flag.astype(str).str.contains("synthetic", case=False).sum())
    missing = int(districts.ev_total.isna().sum())
    notes = [config.MAP_SOURCE_NOTE, f"{len(districts)} boundary districts; new districts may be missing.",
             f"Missing EV data: {missing}; synthetic: {synthetic}; excluded from composite: {excluded}.",
             "Grey: no data; purple: no chargers; dashed: synthetic; Gi*: red hot / blue cold, FDR corrected.",
             "Few districts: hotspots are indicative, not conclusive. Basemap tiles need internet."]
    if include_slice1:
        notes.extend(population_labels)
    if "ev_measure" in districts:
        for measure in districts.ev_measure.dropna().unique():
            notes.append(f"EV observation: {measure}")
        if "ev_year" in districts:
            notes.append("EV observation years: " + ", ".join(map(str, districts.ev_year.dropna().unique())))
    if synthetic or config.USE_SYNTHETIC_TEST_DATA:
        notes.append("SYNTHETIC TEST DATA IN USE - do not use these results in the submission.")
    m.get_root().html.add_child(folium.Element(f'<div style="{config.MAP_NOTE_CSS}">' + "<br>".join(html.escape(note) for note in notes) + "</div>"))
    document = m.get_root().render()
    missing_assets = []
    if config.MAP_OFFLINE_MODE or config.CACHE_MAP_ASSETS:
        document, missing_assets = cache_map_assets(document)
    from cache_map_assets import inspect_assets
    from utils import save_json
    asset_report = inspect_assets(document, MAP_HTML.parent)
    if not asset_report["offline_assets"]:
        warning = f'<div style="{config.MAP_ASSET_WARNING_CSS}">Map libraries need internet. Cache the assets for offline vector display; basemap tiles stay online.</div>'
        document = document.replace("</body>", warning + "</body>")
    MAP_HTML.write_text(document, encoding="utf-8")
    save_json(MAP_HTML.with_suffix(".assets.json"), asset_report)
    print(f"Map saved: {MAP_HTML}; uncached JS/CSS assets: {len(asset_report['external_urls'])}")
    return m


if __name__ == "__main__":
    main()
