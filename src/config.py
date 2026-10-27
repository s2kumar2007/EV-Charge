"""
All settings live in this one file. The other files contain logic only.
To run the project for another state, change STATE_NAME and STATE_SLUG.
"""

# ---- Which state ----------------------------------------------------------
STATE_NAME = "Tamil Nadu"          # used in geocoding questions
STATE_SLUG = "tamil-nadu"          # the state's file name in the boundary repository

# ---- District boundaries (downloaded from the internet) -------------------
# Pinned to one exact commit so the map never changes under you.
BOUNDARY_REPO = "udit-001/india-maps-data"
BOUNDARY_COMMIT = "273a91960b2317c8431e562942293de959e2bd68"
BOUNDARY_URL = (f"https://raw.githubusercontent.com/{BOUNDARY_REPO}/{BOUNDARY_COMMIT}"
                f"/geojson/states/{STATE_SLUG}.geojson")
BOUNDARY_DISTRICT_COLUMN = "district"

# ---- Charger sources ------------------------------------------------------
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_TIMEOUT_S = 180
OCM_URL = "https://api.openchargemap.io/v3/poi/"
OCM_MAX_RESULTS = 5000

# ---- Name matching and geocoding -----------------------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_PAUSE_S = 1.1            # Nominatim's rule: at most 1 request per second
FUZZY_CUTOFF = 0.88                # how similar two spellings must be (0 to 1)
AMBIGUITY_MARGIN = 0.03            # if two districts match almost equally, do not guess
USER_AGENT = "ChargeGap-Slice0/0.2 (educational prototype)"
RETRY_ATTEMPTS = 4
RETRY_WAIT_S = 5

# ---- VAHAN EV data --------------------------------------------------------
# If data/raw/vahan_tn_ev_by_district.csv is missing, load_vahan.py falls back to this sample in data/samples/
VAHAN_SAMPLE_FILE = "vahan_tn_ev_by_district.csv"
# Only load data/samples/vahan_tn_ev_by_district_SYNTHETIC_TEST.csv when explicitly turned on for testing
USE_SYNTHETIC_TEST_DATA = False

# ---- Scoring --------------------------------------------------------------
# "first"    : districts with 0 chargers rank as most underserved (biggest EV count first)
# "smoothed" : score = EVs / max(chargers, 1), so tiny-EV districts do not jump to rank 1
NO_CHARGER_POLICY = "smoothed"
# Whether gap score measures EVs per station ("stations") or EVs per port ("ports")
GAP_UNIT = "stations"

# Synthetic EV numbers are OFF by default. If you turn this on, missing districts get random
# values between the smallest and largest REAL value, and are flagged "synthetic".
ALLOW_SYNTHETIC = False
SYNTHETIC_SEED = 2026

# ---- Map appearance -------------------------------------------------------
MAP_TILES = "OpenStreetMap"
COLOUR_SCALE_PERCENTILE = 95       # colours are capped here so one outlier does not wash out the rest
NO_CHARGER_COLOUR = "#6a1b9a"
NO_DATA_COLOUR = "#bdbdbd"
SOURCE_COLOURS = {"OSM": "#1565c0", "OCM": "#2e7d32"}
UNKNOWN_SOURCE_COLOUR = "#000000"

# ---- Shared settings -----------------------------------------------------
WGS84 = "EPSG:4326"
NETWORK_TIMEOUT_S = 120
NETWORK_TIMEOUT_PADDING_S = 60
ERROR_PREVIEW_CHARS = 200
DEFAULT_PORTS = 1
PER_100K = 100000
METRES_PER_KM = 1000
SCORE_DECIMALS = 6
VAHAN_FILE = "vahan_tn_ev_by_district.csv"
VAHAN_TEMPLATE = "vahan_tn_ev_by_district_TEMPLATE.csv"
SYNTHETIC_TEST_FILENAME = "vahan_tn_ev_by_district_SYNTHETIC_TEST.csv"
VEHICLE_COLUMNS = ["two_wheeler", "three_wheeler", "four_wheeler", "bus"]
TEMPLATE_COLUMNS = ["district", "ev_total", *VEHICLE_COLUMNS, "population", "data_flag"]
COUNTRY_NAME = "India"
RTO_BRACKETS_PATTERN = r"\([^)]*\)|\[[^]]*\]"
RTO_CODE_PATTERN = r"\b[A-Za-z]{2}[- ]?\d{1,3}\b"
RTO_WORD_PATTERN = r"\b(RTO|RTA|regional transport office)\b"
MAP_FILENAME = "tn_gap_map.html"
REFRESH_DOWNLOADS = False  # --refresh updates downloads, never cached geocoder answers.
OFFLINE = False           # --offline forbids every uncached network request.
OSM_CHARGER_FILTER = '["amenity"="charging_station"]'
OSM_ROAD_FILTER = '["highway"~"^(trunk|primary)$"]'
OSM_POI_FILTERS = ['["shop"]', '["amenity"~"^(fuel|restaurant|marketplace)$"]']
OVERPASS_ENDPOINTS += ["https://overpass.private.coffee/api/interpreter"]

# ---- Deduplication: editable assumptions, not observed facts --------------
DEDUP_ENABLED = True
DEDUP_RADIUS_M = 40.0
DEDUP_RADII_M = [10.0, 25.0, 40.0, 75.0, 100.0]
DEDUP_NAME_SIMILARITY = 0.80
DEDUP_OPERATOR_SIMILARITY = 0.85
DEDUP_UNNAMED_RADIUS_FRACTION = 0.25
# Equal heuristic weights are editable. Confidence is NOT a probability.
CONFIDENCE_WEIGHTS = {"sources": 1.0, "name": 1.0, "operator": 1.0, "ports": 1.0, "spread": 1.0}
CONFIDENCE_SOURCE_TARGET = 2
VALIDATION_SAMPLE_SIZE = 30
VALIDATION_SEED = 2026
VALIDATION_ACCEPTED_TRUE = ["true", "yes", "1"]
VALIDATION_ACCEPTED_FALSE = ["false", "no", "0"]

# ---- Population: open Census 2011 compilation ----------------------------
POPULATION_DATASET = "indiaset/census-2011"
POPULATION_CITATION = "Jaiswal, Ansuman (2026), India Census 2011 - District Level, IndiaSet"
POPULATION_SOURCE_URL = f"https://huggingface.co/datasets/{POPULATION_DATASET}"
POPULATION_URL = "https://datasets-server.huggingface.co/rows"
POPULATION_LICENCE = "CC-BY-4.0 (compilation); source: Census of India 2011"
POPULATION_YEAR = 2011
POPULATION_API_CONFIG = "default"
POPULATION_API_SPLIT = "train"
POPULATION_PAGE_SIZE = 100
POPULATION_STATE_COLUMN = "state_name"
POPULATION_DISTRICT_COLUMN = "district_name"
POPULATION_COUNT_COLUMN = "pop_total"
POPULATION_MANUAL_FILE = "population.csv"
# Do not silently apply pre-split populations to newer district polygons.
# Verify boundary compatibility before enabling downloaded historic values.
POPULATION_BOUNDARIES_VERIFIED = False

# ---- Composite index: higher values mean greater demand in every column --
INDICATORS = ["ev_pressure", "evs_per_100k", "road_km_per_km2", "commercial_per_km2"]
INDICATOR_SOURCES = {
    "ev_pressure": "VAHAN EV total / selected OSM + optional OCM stations or ports",
    "evs_per_100k": "annual new EV registrations per 100,000 people (2022 population estimate)",
    "road_km_per_km2": "OSM trunk/primary ways clipped to district / district area",
    "commercial_per_km2": "OSM shop or fuel/restaurant/marketplace nodes / district area",
}
SCALING_METHOD = "minmax"  # or robust: clip at data quantiles, then min-max
ROBUST_QUANTILES = [0.05, 0.95]
NUMERIC_TOLERANCE = 1e-10
AHP_MATRIX = [[1.0 for _ in INDICATORS] for _ in INDICATORS]
AHP_RANDOM_INDEX = 0.90  # Saaty's random consistency index for four indicators.
AHP_MAX_CONSISTENCY_RATIO = 0.10
WEIGHT_RUNS = 1000
WEIGHT_SEED = 2026
DIRICHLET_CONCENTRATION = 50.0
TOP_K = 5
REPORT_TOP_N = 5

# ---- Spatial statistics --------------------------------------------------
HOTSPOT_PERMUTATIONS = 999
HOTSPOT_SEED = 2026
HOTSPOT_CONFIDENCE_LEVELS = [90, 95, 99]
HOTSPOT_MIN_OBSERVATIONS = 3
HOTSPOT_SMALL_N = 50
HOTSPOT_JOBS = 1
HOTSPOT_ISLAND_WEIGHT = 0
HOTSPOT_TWO_SIDED_MULTIPLIER = 2.0  # double the folded permutation tail

# ---- Presentation settings -----------------------------------------------
MAP_PALETTE = ["#ffffcc", "#fd8d3c", "#bd0026"]
CONFIDENCE_PALETTE = ["#d73027", "#fee08b", "#1a9850"]
HOT_COLOUR = "#d73027"
COLD_COLOUR = "#4575b4"
NOT_SIGNIFICANT_COLOUR = "#eeeeee"
OUTLINE_COLOUR = "#333333"
HIGHLIGHT_COLOUR = "#000000"
OUTLINE_WEIGHT = 1
HIGHLIGHT_WEIGHT = 3
POLYGON_OPACITY = 0.75
MARKER_RADIUS = 3
MARKER_OPACITY = 0.9
POPUP_MAX_WIDTH = 400
SYNTHETIC_DASH = "6,4"
COLOUR_CONSTANT_SPAN = 1.0
MAP_SOURCE_NOTE = "OSM contributors (ODbL); optional OpenChargeMap (provider terms); VAHAN (manual export); third-party boundaries. Population: Census 2011 compilation (CC-BY-4.0), only after boundary review."
BOUNDARY_LICENCE = "No explicit data licence found in repository; verify permission before redistribution."
# CDN dependencies are cached alongside downloads. Basemap tiles stay online;
# the offline map still shows its district polygons and charger circles.
CACHE_MAP_ASSETS = False  # Legacy opt-in; prefer MAP_OFFLINE_MODE below.
MAP_ASSET_FOLDER = "assets"
# Map note styles are editable here rather than scattered through rendering code.
MAP_NOTE_CSS = "position:fixed;bottom:10px;left:10px;z-index:9999;background:white;padding:10px;max-width:480px;font-size:12px;border:1px solid grey"
MAP_ASSET_WARNING_CSS = "position:fixed;top:0;left:0;z-index:9999;background:white"
PRIVATE_PARAMETER_KEYS = {"key", "api_key", "token"}
NOMINATIM_POLICY_URL = "https://operations.osmfoundation.org/policies/nominatim/"

# ---- Public tables collected from official documents ---------------------
PUBLIC_EV_SOURCE_URL = "https://sansad.in/getFile/loksabhaquestions/annex/187/AU4552_wCyeso.pdf?source=pqals"
PUBLIC_EV_SOURCE_DATE = "2026-03-19"
PUBLIC_EV_YEARS = [2023, 2024, 2025]
PUBLIC_EV_SELECTED_YEAR = 2025
PUBLIC_EV_TABLE_FIRST_LINE = 135
PUBLIC_EV_TABLE_LAST_LINE = 718
PUBLIC_EV_CATEGORY_CODES = ["2WIC", "2WN", "2WT", "3WIC", "3WN", "3WT", "4WIC", "HGV", "HMV", "HPV", "LGV", "LMV", "LPV", "MGV", "MMV", "MPV", "OTH"]
PUBLIC_EV_EXTRACT_FILES = ["parliament_ev_web_extract.json", "public_sources_search.json"]
PUBLIC_EV_DESCRIPTION = "EV input: official 2025 NEW registrations (not cumulative fleet), published 19 March 2026. Ambiguous PDF cells remain missing."
PUBLIC_POPULATION_SOURCE_URL = "https://des.tn.gov.in/sites/default/files/2025-07/2.VITAL%20STATISTICS.pdf"
PUBLIC_POPULATION_YEAR = 2022
PUBLIC_POPULATION_FIRST_LINE = 30
PUBLIC_POPULATION_LAST_LINE = 67
NAME_IGNORED_LEADING_WORDS = ["the"]  # Generic articles, never district-specific aliases.
PUBLIC_SOURCE_SNAPSHOT_DIR = "official_sources"

# India-wide local run; state settings above remain unchanged.
INDIA_BOUNDARY_FILE = "geoBoundaries-IND-ADM2.geojson"
INDIA_PBF_FILE = "india-261025.osm.pbf"
INDIA_BOUNDARY_NAME = "shapeName"
INDIA_BOUNDARY_ID = "shapeID"  # Dataset identifier, not an official LGD code.
INDIA_OUTPUT_FOLDER = "india"
INDIA_EV_FILE = "vahan_india_ev_by_district.csv"
INDIA_POPULATION_FILE = "population_india.csv"
INDIA_MAP_FILE = "india_gap_map.html"
INDIA_ROAD_CLASSES = {"trunk", "primary"}
INDIA_COMMERCIAL_AMENITIES = {"fuel", "restaurant", "marketplace"}
INDIA_CHARGER_AMENITY = "charging_station"
INDIA_OSM_SOURCE = "OSM"
INDIA_PBF_MAX_BLOB_BYTES = 64 * 1024 * 1024
INDIA_PBF_PROGRESS_BLOCKS = 500
INDIA_PBF_COORDINATE_SCALE = 1e-9
INDIA_PBF_DEFAULT_GRANULARITY = 100
INDIA_READER_VERSION = 1
INDIA_MAP_SIMPLIFY_M = 250
INDIA_MAP_NOTE = "India OSM snapshot; OSM contributors (ODbL). Supplied geoBoundaries district polygons; verify release year/licence. Missing EV/population data are never estimated. Charger presence does not prove public access, uptime or capacity."
INDIA_GEOCENTRIC_CRS = "EPSG:4978"  # Global Earth-centred metres, for neighbour candidates.
INDIA_DISTRICT_PROGRESS = 50
INDIA_PBF_SUPPORTED_FEATURES = {"OsmSchema-V0.6", "DenseNodes"}
INDIA_BOUNDARY_METADATA_URL = "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/"
INDIA_OSM_SOURCE_URL = "https://download.geofabrik.de/asia/india.html"
INDIA_LATEST_PBF_URL = "https://download.geofabrik.de/asia/india-latest.osm.pbf"
INDIA_LATEST_PBF_CACHE = "india-latest.osm.pbf"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
INDIA_LIVE_MIN_BYTES = 1024 * 1024  # Reject HTML/error responses posing as a national extract.
GOOGLE_MAPS_LINKS_ENABLED = True
GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/"
GOOGLE_MAPS_DIRECTIONS_URL = "https://www.google.com/maps/dir/"
GOOGLE_MAPS_URL_VERSION = "1"
GOOGLE_MAPS_TRAVEL_MODE = "driving"
OFFICIAL_CENSUS_DISTRICT_URL = "https://censusindia.gov.in/nada/index.php/catalog/42557/download/46183/2011-IndiaStateDist-0000.xlsx"

# Population proposals attach only after the crosswalk rules pass.
POPULATION_CANDIDATE_FILE = "population_official_estimates_candidate.csv"
POPULATION_CROSSWALK_FILE = "district_crosswalk.csv"
POPULATION_USE_CANDIDATE_CROSSWALK = True
POPULATION_INDICATOR_LABEL = "annual new EV registrations per 100,000 people (2022 population estimate)"
PUBLIC_EV_PDF_FILE = "AU4552_original.pdf"

# Use the first available complete source for each optional OSM indicator.
INDICATOR_SOURCE_ORDER = ["state_cache", "national_cache", "live_overpass"]
NATIONAL_EXTRACT_CACHE_PATTERN = "india_pbf_*_v{version}.json.gz"
INDICATOR_MISSING_SOURCE = "missing"
INDICATOR_UNKNOWN_DATE = "unknown"

# Library caching is opt-in. Tiles are not downloaded by this setting.
MAP_OFFLINE_MODE = False
MAP_ASSET_CACHE_DIR = "map_assets"
MAP_ASSET_FALLBACK_EXTENSION = ".asset"

# Keep the state provider unchanged until the user selects the alternative.
BOUNDARY_PROVIDER = "pinned_repo"  # or "geoboundaries"; used by both runners
GEOBOUNDARIES_METADATA_URLS = {
    "ADM2": INDIA_BOUNDARY_METADATA_URL,
    "ADM1": "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/",
}
GEOBOUNDARIES_NAME_COLUMN = "shapeName"
GEOBOUNDARIES_ID_COLUMN = "shapeID"
GEOBOUNDARIES_CACHE_PREFIX = "geoboundaries_IND"
BOUNDARY_REPO_TREE_URL = f"https://api.github.com/repos/{BOUNDARY_REPO}/git/trees/{BOUNDARY_COMMIT}?recursive=1"
BOUNDARY_REPO_RAW_BASE = f"https://raw.githubusercontent.com/{BOUNDARY_REPO}/{BOUNDARY_COMMIT}/"
BOUNDARY_REPO_STATE_PREFIX = "geojson/states/"
BOUNDARY_REPO_README_URL = BOUNDARY_REPO_RAW_BASE + "README.md"
BOUNDARY_RIGHTS_NOTE = 'Pinned repository README describes collection "for personal usage" and names no data licence. Redistribution permission is unresolved.'

# Acceptance inputs are kept together so the report can be reused elsewhere.
ACCEPTANCE_OUTPUT_FILE = "acceptance_report.json"
ACCEPTANCE_INPUT_FILES = {
    "scores": ("outputs", "district_gap_scores.csv"),
    "selected": ("outputs", "district_gap_scores_deduplicated.csv"),
    "index": ("outputs", "district_gap_index.csv"),
    "raw": ("data/processed", "chargers_raw.csv"),
    "deduplicated": ("data/processed", "chargers_deduplicated.csv"),
    "population": ("data/processed", "district_population.csv"),
    "osm": ("data/processed", "district_osm_indicators.csv"),
    "crosswalk": ("data/samples", POPULATION_CROSSWALK_FILE),
}
ACCEPTANCE_HOTSPOT_FILE = "hotspot_statistics.json"
ACCEPTANCE_BOUNDARY_MANIFEST = "boundary_manifest.json"
BOUNDARY_COMPARISON_FILE = "boundary_provider_comparison.json"

GEOBOUNDARIES_COUNTRY_ISO = "IND"
POPULATION_GENERIC_INDICATOR_LABEL = "EV registrations per 100,000 people (verify registration period and population year)"

NATIONAL_EXTRACT_MANIFEST_FILE = "outputs/india/run_manifest.json"

# Native Google Maps view of the same national outputs; credentials stay in .env.
GOOGLE_MAPS_ENABLED = True
GOOGLE_MAPS_API_KEY_ENV = "GOOGLE_MAPS_API_KEY"
GOOGLE_MAPS_API_URL = "https://maps.googleapis.com/maps/api/js"
GOOGLE_MAPS_API_VERSION = "weekly"
GOOGLE_MAPS_INITIAL_ZOOM = 5
GOOGLE_MAPS_MAP_TYPE = "roadmap"
GOOGLE_MAPS_LOAD_TIMEOUT_MS = 20000
GOOGLE_MAPS_INDIA_FILENAME = "india_google_map.html"
GOOGLE_MAPS_TEMPLATE_FILE = "google_map_template.html"
GOOGLE_MAPS_INCLUDE_UNASSIGNED_CHARGERS = False
GOOGLE_MAPS_BOUNDARY_INPUT = "districts_scored.geojson"
GOOGLE_MAPS_CHARGER_INPUT = "chargers_deduplicated_assigned.csv"
GOOGLE_MAPS_INDEX_INPUT = "district_gap_index.csv"
GOOGLE_MAPS_COVERAGE_INPUT = "district_gap_scores_deduplicated.csv"
GOOGLE_MAPS_MANIFEST_INPUT = "run_manifest.json"
GOOGLE_MAPS_LAYERS = {
    "charger_count": "Mapped charger stations (supply)",
    "composite_score": "Composite gap index",
    "ev_pressure": "EV registrations per charging unit",
    "evs_per_100k": "EV registrations per 100,000 people (verify population year)",
    "road_km_per_km2": "Trunk/primary road km per square km",
    "commercial_per_km2": "Commercial nodes per square km",
}
GOOGLE_MAPS_DEFAULT_LAYER = "charger_count"
GOOGLE_MAPS_POPUP_FIELDS = ["district", "district_key", "charger_count", "port_count", "ev_total", "population", "ev_measure", "period_start", "period_end", "data_flag", "composite_score", "rank", "index_status", "missing_indicators"]
GOOGLE_MAPS_CHARGER_FIELDS = ["name", "operator", "district", "ports", "ports_known", "sources", "confidence"]
GOOGLE_MAPS_NOTE = "OSM snapshot observations; OSM contributors (ODbL). Charger presence does not prove public access, uptime or capacity. Missing EV/population values remain unranked. Boundary attribution and coverage are recorded in the national run manifest. Google basemap requires internet, enabled billing and an authorised browser key."

# Original-PDF recovery uses table geometry and refuses ambiguous numeric cells.
PUBLIC_EV_PDF_FIRST_TABLE_PAGE = 5  # One-based page containing the annexure header.
PUBLIC_EV_PDF_TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
PUBLIC_EV_PDF_WORD_SETTINGS = {"x_tolerance": 1, "y_tolerance": 2}
PUBLIC_EV_PDF_CELL_INSET_PT = 0.5
PUBLIC_EV_PDF_AUDIT_FILE = "public_ev_pdf_cells.json"
PUBLIC_EV_PDF_CHECKS_FILE = "public_ev_pdf_checks.json"
PUBLIC_EV_PDF_LAYOUT_FILE = "AU4552_layout.txt"
PUBLIC_EV_PDF_READER_CANDIDATES = ["pdftotext", "C:/Program Files/Git/mingw64/bin/pdftotext.exe"]
PUBLIC_EV_DISTRICT_TOTAL_LABELS = {"total", "districttotal"}
PUBLIC_EV_STATE_TOTAL_LABELS = {"grandtotal", "statetotal"}
PUBLIC_EV_MEASURE_LABEL = "annual new EV registrations, not cumulative fleet"

PUBLIC_EV_PDF_TOTAL_TEXT = ["Grand Total", "State Total", "District Total", "Total"]
INDIA_ACCEPTANCE_OUTPUT_FILE = "acceptance_report.json"
INDIA_SOURCE_CANDIDATES_FILE = "national_source_candidates.json"
INDIA_VAHAN_REPORT_URL = "https://analytics.parivahan.gov.in/analytics/vahanpublicreport"
INDIA_EV_CANDIDATE_LAYER_URL = "https://livingatlas.esri.in/server/rest/services/India/District_wise_RTO_Vehicle_Registration/MapServer/0"

# Generic accent folding preserves letters in provider transliterations.
NAME_UNICODE_NORMALIZATION = "NFKD"
MAP_SERVER_HOST = "127.0.0.1"
MAP_SERVER_PORT = 8000
MAP_SERVER_OPEN_BROWSER = True
GOOGLE_MAPS_FALLBACK_ENABLED = True
GOOGLE_MAPS_FALLBACK_WIDTH = 1000
GOOGLE_MAPS_FALLBACK_HEIGHT = 900
SUPPLIED_USER_FOLDER = "supplied_user_files"
SUPPLIED_CENSUS_FILE = "2011-IndiaStateDist-0000.xlsx"
SUPPLIED_STATE_FILE = "All_Stateof_India_2026-10-27_12-05-51.xlsx"
SUPPLIED_EV_FILE = "table_data.csv"
SUPPLIED_CENSUS_COLUMNS = {"state_code": "State", "district_code": "District", "level": "Level", "district": "Name", "area_type": "TRU", "population": "TOT_P"}
SUPPLIED_CENSUS_DISTRICT_LEVEL = "DISTRICT"
SUPPLIED_CENSUS_TOTAL_LABEL = "Total"
SUPPLIED_CENSUS_YEAR = 2011
SUPPLIED_POPULATION_CANDIDATE = "population_india_2011_candidate.csv"
SUPPLIED_POPULATION_CROSSWALK = "population_india_2011_crosswalk_candidate.csv"
SUPPLIED_AUDIT_REPORT = "supplied_data_audit.json"
SUPPLIED_CENSUS_COUNTRY_LEVEL = "India"
SUPPLIED_EV_TOTAL_LABEL = "Total"
