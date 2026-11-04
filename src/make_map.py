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
    # Highway corridor gaps layer
    corridor_path = OUTPUTS / getattr(config, "CORRIDOR_OUTPUT_GEOJSON", "corridor_gaps.geojson")
    if corridor_path.exists():
        try:
            corridor_gdf = gpd.read_file(corridor_path)
            hc_corridors = corridor_gdf[corridor_gdf.get("filter_mode", "high_confidence") == "high_confidence"].copy()
            if not hc_corridors.empty:
                def corridor_style(feature):
                    p = feature["properties"]
                    if p.get("flag_heavy_gap"):
                        return {"color": "#7b1fa2", "weight": 5, "opacity": 0.9, "dashArray": "8, 4"}
                    elif p.get("flag_regular_gap"):
                        return {"color": "#d32f2f", "weight": 4, "opacity": 0.85, "dashArray": "6, 4"}
                    else:
                        return {"color": "#2e7d32", "weight": 3, "opacity": 0.75}

                corridor_fields = ["corridor_name", "from_location", "to_location", "gap_km", "drivers", "guideline_status", "confidence", "data_flag"]
                corridor_aliases = ["Corridor", "From", "To", "Gap (km)", "Assessment", "Guideline", "Confidence", "Data Flag"]
                popup_fields = [f for f in corridor_fields if f in hc_corridors.columns]
                aliases = [corridor_aliases[corridor_fields.index(f)] for f in popup_fields]

                folium.GeoJson(
                    hc_corridors,
                    name="Highway corridor gaps (MoP 2024: 20km/100km)",
                    style_function=corridor_style,
                    tooltip=folium.GeoJsonTooltip(fields=popup_fields, aliases=aliases),
                    popup=folium.GeoJsonPopup(fields=popup_fields, aliases=aliases),
                    show=False,
                ).add_to(m)
        except Exception as err:
            print(f"  [warning] Could not add corridor gaps layer to map: {err}")
    # Recommended New Charging Sites layer (from site optimizer)
    rec_sites_file = OUTPUTS / getattr(config, "OPTIMISER_OUTPUT_GEOJSON", "recommended_sites.geojson")
    if include_slice1 and rec_sites_file.exists():
        try:
            rec_gdf = gpd.read_file(rec_sites_file)
            if not rec_gdf.empty:
                rec_fg = folium.FeatureGroup(name="Recommended New Sites (MCLP & FRLM)", show=True)
                for _, site_row in rec_gdf.iterrows():
                    lat = float(site_row.geometry.y)
                    lon = float(site_row.geometry.x)
                    rank = site_row.get("rank", 1)
                    s_name = site_row.get("name", "New Site")
                    s_type = site_row.get("site_type", "charging_site")
                    ports = site_row.get("ports_recommended", 4)
                    drivers = site_row.get("drivers", "")
                    d_flag = site_row.get("data_flag", "recommended")

                    popup_html = (
                        f"<div style='font-family: sans-serif; font-size: 13px; min-width: 200px;'>"
                        f"<b>#{rank} Recommended Site: {html.escape(str(s_name))}</b><br>"
                        f"<b>Type:</b> {html.escape(str(s_type))}<br>"
                        f"<b>Recommended Ports:</b> {ports}<br>"
                        f"<b>Drivers:</b> {html.escape(str(drivers))}<br>"
                        f"<b>Data Flag:</b> {html.escape(str(d_flag))}"
                        f"</div>"
                    )

                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=7,
                        color="#f57f17",
                        fill=True,
                        fill_color="#ffd600",
                        fill_opacity=0.9,
                        weight=2,
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"#{rank} {s_name} ({ports} ports)",
                    ).add_to(rec_fg)
                rec_fg.add_to(m)
        except Exception as err:
            print(f"  [warning] Could not add recommended sites layer to map: {err}")

    # Bayesian Uncertainty Layer (from bayes_layer.py)
    bayes_file = OUTPUTS / "bayes_district_posteriors.csv"
    if include_slice1 and bayes_file.exists():
        try:
            bayes_df = pd.read_csv(bayes_file)
            bayes_gdf = districts.merge(bayes_df, on=["district_key"], how="left", suffixes=("", "_bayes"))
            bayes_fg = folium.FeatureGroup(name="Bayesian Uncertainty (80% Credible Interval)", show=False)

            def bayes_style(feature):
                props = feature.get("properties", {})
                gap = props.get("most_likely_gap", "")
                p10 = props.get("req_p10")
                p90 = props.get("req_p90")
                width = props.get("req_ci_80_width", 0)
                flag = str(props.get("data_flag", "")).lower()

                if flag == "insufficient_data" or p10 is None or pd.isna(p10):
                    fill = "#9e9e9e"
                elif gap == "severe":
                    fill = "#c62828"
                elif gap == "moderate":
                    fill = "#ef6c00"
                else:
                    fill = "#2e7d32"

                opacity = max(0.25, min(0.85, 0.85 - (float(width if width is not None and not pd.isna(width) else 0) / 1000.0) * 0.5))
                dash = "5, 5" if props.get("prior_dominated") is True or "synthetic" in flag else None

                return {
                    "fillColor": fill,
                    "color": "#333333",
                    "weight": 1.5,
                    "fillOpacity": opacity,
                    "dashArray": dash,
                }

            for idx, r in bayes_gdf.iterrows():
                d_name = r.get("district", r.get("district_key", "District"))
                p10 = r.get("req_p10", "N/A")
                p50 = r.get("req_p50", "N/A")
                p90 = r.get("req_p90", "N/A")
                w = r.get("req_ci_80_width", "N/A")
                p_sev = r.get("prob_severe", 0.0)
                p_mod = r.get("prob_moderate", 0.0)
                p_ade = r.get("prob_adequate", 0.0)
                drivers = r.get("drivers", "N/A")
                agr = r.get("model_agreement", "N/A")
                p_dom = "Yes (Dirichlet shift > 25%)" if r.get("prior_dominated") else "No (Data-dominated)"
                flag = r.get("data_flag", "real")

                p_html = (
                    f"<div style='font-family: sans-serif; font-size: 13px; min-width: 240px;'>"
                    f"<b>{html.escape(str(d_name))}</b> (Bayesian Uncertainty)<br>"
                    f"<b>80% Credible Interval:</b> {p10} to {p90} ports (median: {p50})<br>"
                    f"<b>Uncertainty Width:</b> {w} ports<br>"
                    f"<b>Gap Probabilities:</b> Severe {float(p_sev if not pd.isna(p_sev) else 0):.0%}, Mod {float(p_mod if not pd.isna(p_mod) else 0):.0%}, Adeq {float(p_ade if not pd.isna(p_ade) else 0):.0%}<br>"
                    f"<b>Drivers:</b> {html.escape(str(drivers))}<br>"
                    f"<b>MC Agreement:</b> {html.escape(str(agr))}<br>"
                    f"<b>Prior Dominated:</b> {p_dom}<br>"
                    f"<b>Data Flag:</b> {html.escape(str(flag))}<br>"
                    f"<small style='color: #666;'><i>Priors: expert assumptions in config/bn_priors.yaml</i></small>"
                    f"</div>"
                )
                bayes_gdf.at[idx, "bayes_popup"] = p_html

            needed_cols = [
                "geometry", "district_key", "district", "bayes_popup", "req_p10", "req_p50",
                "req_p90", "req_ci_80_width", "most_likely_gap", "prob_severe", "prob_moderate",
                "prob_adequate", "drivers", "model_agreement", "prior_dominated", "data_flag"
            ]
            clean_gdf = bayes_gdf[[c for c in needed_cols if c in bayes_gdf.columns]].copy()
            for col in clean_gdf.columns:
                if pd.api.types.is_datetime64_any_dtype(clean_gdf[col]):
                    clean_gdf[col] = clean_gdf[col].map(lambda v: v.isoformat() if pd.notna(v) else None)

            folium.GeoJson(
                clean_gdf,
                style_function=bayes_style,
                popup=folium.GeoJsonPopup(fields=["bayes_popup"], labels=False),
                tooltip=folium.GeoJsonTooltip(fields=["district", "req_p10", "req_p90", "most_likely_gap"], aliases=["District:", "P10 Ports:", "P90 Ports:", "Gap Class:"]),
            ).add_to(bayes_fg)
            bayes_fg.add_to(m)
        except Exception as err:
            print(f"  [warning] Could not add Bayesian uncertainty layer to map: {err}")

    folium.LayerControl(collapsed=False).add_to(m)
    synthetic = int(districts.data_flag.astype(str).str.contains("synthetic", case=False).sum())
    missing = int(districts.ev_total.isna().sum())
    notes = [config.MAP_SOURCE_NOTE, f"{len(districts)} boundary districts; new districts may be missing.",
             f"Missing EV data: {missing}; synthetic: {synthetic}; excluded from composite: {excluded}.",
             "Grey: no data; purple: no chargers; dashed: synthetic; Gi*: red hot / blue cold, FDR corrected.",
             "Few districts: hotspots are indicative, not conclusive. Basemap tiles need internet.",
             "Bayesian Uncertainty: 80% credible intervals from expert priors (CEA/NITI Aayog); unobserved data marginalized."]
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
