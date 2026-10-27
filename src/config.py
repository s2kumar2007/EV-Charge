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
    "evs_per_100k": "VAHAN EV total / compatible district population * 100000",
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
CACHE_MAP_ASSETS = True
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
