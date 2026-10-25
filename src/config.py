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

# ---- Scoring --------------------------------------------------------------
# "first"    : districts with 0 chargers rank as most underserved (biggest EV count first)
# "smoothed" : score = EVs / max(chargers, 1), so tiny-EV districts do not jump to rank 1
NO_CHARGER_POLICY = "smoothed"

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
