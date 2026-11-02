# ChargeGap India - Pending Manual Actions (TODO_MANUAL.md)

This file tracks all data items, configuration keys, guideline verifications, and approvals that must be supplied or verified by human researchers. The codebase **never invents data** and will degrade gracefully or flag outputs when these are missing.

---

## 1. National District EV Counts
- **Status**: Blocked on official data supply.
- **Required**: Official district-level registered EV counts across all states and union territories in India.
- **Current State**: The available national export (`official_ev_2025_collected.csv`) provides national aggregated totals by vehicle category and fuel type, but contains zero district-level breakdown. National maps degrade gracefully and display "insufficient data" where district counts are absent.

## 2. Approve 5 Population Mapping Rows (Tamil Nadu)
- **Status**: Pending human review.
- **Required**: Review and approval of the 5 crosswalk candidate mappings connecting 2011 Census district boundaries to modern reorganised districts in Tamil Nadu (e.g., Chengalpattu, Kallakurichi, Ranipet, Tenkasi, Tirupathur).
- **Current State**: Explicitly printed during pipeline runs; population-derived indicators are excluded or marked unapproved until signed off.

## 3. External API Keys (`.env`)
- **Status**: Optional / Environment dependent.
- **Keys**:
  - `OCM_API_KEY`: OpenChargeMap API key to fetch additional crowd-sourced and operator charging locations.
  - `GOOGLE_MAPS_API_KEY`: Google Maps JavaScript API key for live browser visualization.
- **Current State**: The pipeline operates fully offline with OpenStreetMap Overpass caches and local offline Leaflet visualization when keys are omitted.

## 4. Highway Corridor Guideline Figures
- **Status**: VERIFIED against official notification; kept configurable in code.
- **Reference**: Ministry of Power (MoP) *Guidelines for Installation and Operation of Electric Vehicle Charging Infrastructure-2024* (Notification dated 17 September 2024):
  - Regular EV highways guideline: At least 1 charging station every **20 km** on both sides of highways and expressways.
  - Heavy-duty / fast charging guideline: At least 1 fast charging station every **100 km** on each side for long-range and heavy-duty commercial EVs.
- **Implementation**: Configurable in `src/config.py` as `CORRIDOR_MAX_GAP_KM = 20.0` and `CORRIDOR_MAX_GAP_HEAVY_KM = 100.0`. Labelled in code, documentation, and outputs with their regulatory status.

## 5. Operator Spot-Check
- **Status**: Pending physical or operator portal verification.
- **Required**: Spot-check validation of 30 deduplicated charging sites (`data/samples/spot_check_TEMPLATE.csv`) against operator networks (e.g., Tata Power, Zeon, Jio-bp, ChargeZone) to audit coordinate accuracy and operational status.
