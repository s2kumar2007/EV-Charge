"""
District name resolution and fuzzy matching for the Planner Assistant.

Maps user queries, spoken aliases, and typo-ridden inputs to canonical district keys
and official boundary names, returning ambiguity warnings when multiple candidates match.
"""
import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Predefined common district aliases in Tamil Nadu and India
KNOWN_ALIASES: Dict[str, str] = {
    "trichy": "tiruchirappalli",
    "tiruchi": "tiruchirappalli",
    "coimbatur": "coimbatore",
    "covai": "coimbatore",
    "chenai": "chennai",
    "madura": "madurai",
    "vellur": "vellore",
    "ooty": "the_nilgiris",
    "nilgiris": "the_nilgiris",
    "nilgiri": "the_nilgiris",
    "kanyakumari": "kanniyakumari",
    "tanjore": "thanjavur",
    "tuticorin": "thoothukkudi",
    "thoothukudi": "thoothukkudi",
    "tirunelvely": "tirunelveli",
    "nellai": "tirunelveli",
}


def normalize_query(query: str) -> str:
    """Normalize input query string for matching."""
    q = str(query).lower().strip()
    q = re.sub(r"\b(district|dist|dt|state|city)\b", "", q)
    q = re.sub(r"[^a-z0-9]", "", q)
    return q.strip()


class DistrictResolver:
    """Resolves arbitrary user district names to canonical district keys."""

    def __init__(self, known_districts: Optional[Dict[str, str]] = None):
        """
        Args:
            known_districts: Mapping of canonical district_key -> official district display name.
        """
        self.known_districts = known_districts or {}
        # Precompute normalized key lookups
        self._norm_map: Dict[str, str] = {}
        for k, name in self.known_districts.items():
            self._norm_map[normalize_query(k)] = k
            self._norm_map[normalize_query(name)] = k

    def register_districts(self, districts_map: Dict[str, str]) -> None:
        """Update or register known districts mapping."""
        self.known_districts.update(districts_map)
        for k, name in districts_map.items():
            self._norm_map[normalize_query(k)] = k
            self._norm_map[normalize_query(name)] = k

    def resolve(self, query: str) -> Dict[str, Any]:
        """
        Resolve a district query to a canonical key.
        
        Returns:
          Dict with keys:
            - status: 'resolved', 'ambiguous', or 'not_found'
            - district_key: canonical key (if resolved)
            - district: display name (if resolved)
            - candidates: list of candidate display names (if ambiguous)
            - message: explanatory notice or clarification request
        """
        if not query or not str(query).strip():
            return {
                "status": "not_found",
                "message": "Empty district query provided.",
            }

        raw = str(query).strip().lower()
        norm = normalize_query(raw)

        # 1. Exact registered normalized lookup (priority to official boundaries)
        if norm in self._norm_map:
            canon = self._norm_map[norm]
            disp = self.known_districts.get(canon, canon.replace("_", " ").title())
            return {
                "status": "resolved",
                "district_key": canon,
                "district": disp,
            }

        # 2. Regional alias lookup
        if raw in KNOWN_ALIASES:
            alias_target = KNOWN_ALIASES[raw]
            alias_norm = normalize_query(alias_target)
            canon = self._norm_map.get(alias_norm, alias_target)
            disp = self.known_districts.get(canon, canon.replace("_", " ").title())
            return {
                "status": "resolved",
                "district_key": canon,
                "district": disp,
            }

        # 3. Fuzzy match against all known names and keys
        candidates_pool = list(self._norm_map.keys())
        matches = difflib.get_close_matches(norm, candidates_pool, n=3, cutoff=0.60)

        if not matches:
            return {
                "status": "not_found",
                "message": f"District '{query}' not found in project boundary records.",
            }

        # If top match is strong (> 0.75 similarity) and distinctly better than runner-up
        top_ratio = difflib.SequenceMatcher(None, norm, matches[0]).ratio()
        if len(matches) == 1 or top_ratio >= 0.75:
            canon = self._norm_map[matches[0]]
            disp = self.known_districts.get(canon, canon.replace("_", " ").title())
            return {
                "status": "resolved",
                "district_key": canon,
                "district": disp,
            }

        # Ambiguous matches: request clarification
        candidate_names = [
            self.known_districts.get(self._norm_map[m], self._norm_map[m].title())
            for m in matches
        ]
        return {
            "status": "ambiguous",
            "candidates": candidate_names,
            "message": f"Query '{query}' is ambiguous. Did you mean: {', '.join(candidate_names)}?",
        }
