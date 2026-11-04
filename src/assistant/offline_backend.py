"""
Deterministic offline intent router and template engine for the Planner Assistant.

Processes natural language planner queries locally without external LLM dependencies,
strictly invoking read-only tools and enforcing data honesty, unverified guideline propagation,
and prompt-injection protection.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from assistant.tools import AssistantTools


class OfflinePlannerAssistant:
    """Offline deterministic backend for the ChargeGap Planner Assistant."""

    def __init__(
        self,
        outputs_dir: Optional[Union[str, Path]] = None,
        log_file: Optional[Union[str, Path]] = None,
    ):
        self.tools = AssistantTools(outputs_dir=outputs_dir)
        self.outputs_dir = self.tools.outputs_dir
        if log_file is None:
            self.log_file = self.outputs_dir / "assistant_log.jsonl"
        else:
            self.log_file = Path(log_file)

    def _log_query(self, question: str, intent: str, status: str) -> None:
        """Log questions locally for auditing (no API keys, capped log size)."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backend": "offline",
                "question": question[:300],
                "intent": intent,
                "status": status,
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _find_district_in_query(self, query: str, context: Optional[str] = None) -> Optional[str]:
        """Extract a mentioned district from query text or context."""
        if context:
            res = self.tools.resolver.resolve(context)
            if res["status"] == "resolved":
                return res["district_key"]

        q_lower = query.lower()
        # Check known aliases and registered districts
        for alias, canon in self.tools.resolver.known_districts.items():
            pattern = r"\b" + re.escape(alias.lower()) + r"\b"
            if re.search(pattern, q_lower):
                return canon

        # Check raw words against resolver
        words = re.findall(r"[a-zA-Z]{3,}", query)
        for w in words:
            res = self.tools.resolver.resolve(w)
            if res["status"] == "resolved":
                return res["district_key"]

        return None

    def answer(self, question: str, district_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze planner question, route to appropriate tool, and generate grounded answer.
        """
        q_raw = str(question).strip()
        q_lower = q_raw.lower()

        # 1. Prompt-injection and safety guardrail
        injection_patterns = [
            r"ignore.*(previous|all).*instruction",
            r"system\s*prompt",
            r"reveal.*(key|secret|password)",
            r"jailbreak",
            r"<script",
        ]
        if any(re.search(pat, q_lower) for pat in injection_patterns):
            self._log_query(q_raw, "injection_attempt", "refused")
            return {
                "status": "refused",
                "backend": "offline",
                "intent": "injection_attempt",
                "answer": "Security Alert: This query contains instruction-override or jailbreak patterns and cannot be processed.",
                "evidence": [],
                "warnings": ["Prompt-injection attempt refused."],
            }

        # 2. Out-of-scope filter
        ev_keywords = [
            "ev", "charger", "station", "port", "district", "corridor", "gap", "rank",
            "highway", "nh-48", "nh48", "uncertainty", "prior", "bayes", "what-if", "what if",
            "traffic", "grid", "power", "vahan", "chennai", "krishnagiri", "ariyalur", "ranipet",
            "deficit", "quota", "recommend", "site", "tamil nadu", "infrastructure", "fleet"
        ]
        out_of_scope_patterns = [
            r"\b(weather|recipe|cake|movie|football|cricket score|capital of|stock price|poem|song)\b"
        ]
        if any(re.search(pat, q_lower) for pat in out_of_scope_patterns) and not any(kw in q_lower for kw in ev_keywords):
            self._log_query(q_raw, "out_of_scope", "refused")
            return {
                "status": "refused",
                "backend": "offline",
                "intent": "out_of_scope",
                "answer": "This query is out of scope. I am the ChargeGap India Planner Assistant, designed specifically to answer queries regarding EV charging infrastructure deficits, corridor spacing, siting recommendations, and Bayesian uncertainty across Indian districts.",
                "evidence": [],
                "warnings": ["Out-of-scope query refused."],
            }

        # 3. Intent classification and tool routing
        district_key = self._find_district_in_query(q_raw, district_context)

        # Intent: Limitations & disclosures
        if re.search(r"(what can'?t you tell|limitations?|caveats?|disclosures?|shortcomings)", q_lower):
            lims = self.tools.list_limitations()
            bullets = "\n".join(f"- {item}" for item in lims["limitations"])
            answer = (
                f"### ChargeGap India — Verified Methodology & Data Limitations\n\n"
                f"{bullets}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `list_limitations`\n"
                f"- **Source**: `docs/bayes_design.md` and `README.md`\n"
                f"- **Data Flag**: `disclosure`"
            )
            self._log_query(q_raw, "limitations", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "limitations",
                "answer": answer,
                "evidence": [lims["evidence"]],
                "warnings": ["All reported findings must be interpreted alongside official project disclosures."],
            }

        # Intent: Highway Corridor gaps
        if re.search(r"(corridor|highway|nh-?48|stretch|spacing|gap.*highway|highway.*gap)", q_lower):
            corridor_res = self.tools.get_corridor_gaps()
            gaps = corridor_res["gaps"]
            if not gaps:
                ans_body = "No non-compliant corridor stretches currently flagged in project outputs."
            else:
                lines = []
                for g in gaps:
                    lines.append(
                        f"- **{g['corridor_id']} ({g['corridor_name']})**: Segment `{g['segment_id']}` has a gap of **{g['gap_km']:.1f} km** "
                        f"(maximum allowed: {g['max_allowed_km']:.0f} km) — **{g['status']}**."
                    )
                ans_body = "\n".join(lines)

            answer = (
                f"### Highway Corridor Gap Analysis\n\n"
                f"{ans_body}\n\n"
                f"### Warnings\n"
                f"- **UNVERIFIED**: Ministry of Power (MoP) 2024 guideline threshold of 25 km between charging stations is an indicative planning benchmark.\n\n"
                f"### Evidence\n"
                f"- **Tool**: `get_corridor_gaps`\n"
                f"- **Source File**: `corridor_gaps.csv`\n"
                f"- **Data Flag**: `real`"
            )
            self._log_query(q_raw, "corridor_gaps", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "corridor_gaps",
                "answer": answer,
                "evidence": [corridor_res["evidence"]],
                "warnings": corridor_res["warnings"],
            }

        # Intent: Site recommendations
        if re.search(r"(where.*(build|put|place)|recommend.*site|priority site|new site|optimal location)", q_lower):
            sites_res = self.tools.get_recommended_sites(top_n=5)
            sites = sites_res["sites"]
            if not sites:
                ans_body = "No candidate charging sites generated in current outputs."
            else:
                lines = []
                for s in sites:
                    lines.append(
                        f"1. **#{s['rank']} {s['name']}** ({s['district']}): Recommended **{s['ports_recommended']} ports** ({s['site_type']}). Drivers: {s['drivers']}."
                    )
                ans_body = "\n".join(lines)

            answer = (
                f"### Priority Charging Site Recommendations (MCLP & FRLM Optimization)\n\n"
                f"{ans_body}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `get_recommended_sites`\n"
                f"- **Source File**: `recommended_sites.csv`\n"
                f"- **Data Flag**: `recommended`"
            )
            self._log_query(q_raw, "site_recommendations", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "site_recommendations",
                "answer": answer,
                "evidence": [sites_res["evidence"]],
                "warnings": [],
            }

        # Intent: Uncertainty / Credible Interval
        if re.search(r"(how sure|credible interval|uncertainty|confidence in|bayesian|sensitivity)", q_lower) and district_key:
            unc = self.tools.get_uncertainty(district_key)
            if unc["status"] != "ok":
                return unc

            p_dom_str = (
                "**WARNING**: This district is **prior-dominated** (Dirichlet sensitivity shifts P50 > 25%). Conclusion is sensitive to assumed prior beliefs."
                if unc["prior_dominated"]
                else "Conclusion is **data-dominated** and robust against prior perturbations."
            )
            answer = (
                f"### Bayesian Uncertainty Analysis: {unc['district']}\n\n"
                f"- **80% Credible Interval**: **{unc['req_p10']} to {unc['req_p90']} public ports** (Median P50: **{unc['req_p50']} ports**).\n"
                f"- **Uncertainty Width**: {unc['req_ci_80_width']} ports.\n"
                f"- **Deficit Severity**: **{unc['most_likely_gap'].title()}** (P(Severe) = {unc['prob_severe']:.1%}, P(Moderate) = {unc['prob_moderate']:.1%}, P(Adequate) = {unc['prob_adequate']:.1%}).\n"
                f"- **Top Drivers**: {unc['drivers']}.\n"
                f"- **Model Agreement**: {unc['model_agreement']} — {unc['agreement_note']}.\n"
                f"- **Prior Sensitivity**: {p_dom_str}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `get_uncertainty`\n"
                f"- **Source File**: `bayes_district_posteriors.csv`\n"
                f"- **District Key**: `{unc['district_key']}`\n"
                f"- **Data Flag**: `{unc['data_flag']}`\n"
                f"- **Note**: {unc['provenance_notice']}"
            )
            self._log_query(q_raw, "uncertainty", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "uncertainty",
                "answer": answer,
                "evidence": [unc["evidence"]],
                "warnings": [unc["provenance_notice"]],
            }

        # Intent: What-if simulation
        if re.search(r"(what happens if|what if|faster|slower|adoption growth|scenario|simulate)", q_lower):
            # Parse growth percentage if present
            growth_match = re.search(r"(\d+)\s*%", q_lower)
            growth = float(growth_match.group(1)) if growth_match else 20.0
            whatif_res = self.tools.run_whatif(adoption_growth_pct=growth)
            if whatif_res.get("status") != "ok":
                return whatif_res

            answer = (
                f"### What-If Scenario Analysis ({growth:+g}% EV Fleet Growth)\n\n"
                f"- **Simulated Total EVs**: {whatif_res['summary']['total_simulated_evs']:,}\n"
                f"- **Statewide Port Deficit (P50)**: **{whatif_res['summary']['total_p50_port_deficit']:,} ports**\n"
                f"- **Drivers**: {whatif_res['drivers']}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `run_whatif`\n"
                f"- **Source File**: `district_gap_scores.csv`\n"
                f"- **Data Flag**: `simulated`"
            )
            self._log_query(q_raw, "what_if", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "what_if",
                "answer": answer,
                "evidence": [whatif_res["evidence"]],
                "warnings": ["Simulations assume stochastic normal fleet expansion and 1.2x crowdsourced charger undercount."],
            }

        # Intent: Data quality & confidence
        if re.search(r"(data quality|data confidence|how many chargers are verified|provenance|audit)", q_lower) and district_key:
            qual = self.tools.get_data_quality(district_key)
            if qual["status"] != "ok":
                return qual

            answer = (
                f"### Data Quality & Provenance Audit: {qual['district']}\n\n"
                f"- **Data Flag**: `{qual['data_flag']}`\n"
                f"- **Charger Confidence Score**: **{qual['confidence']:.0%}** (OpenStreetMap & OpenChargeMap verified).\n"
                f"- **Public Infrastructure Count**: {qual['port_count']} ports across {qual['charger_count']} stations.\n"
                f"- **Source Provenance**:\n"
                f"  - EV Registrations: {qual['provenance']['ev_counts']}\n"
                f"  - Charging Stations: {qual['provenance']['chargers']}\n"
                f"  - Boundaries: {qual['provenance']['boundaries']}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `get_data_quality`\n"
                f"- **Source File**: `charger_requirements.csv`\n"
                f"- **District Key**: `{qual['district_key']}`\n"
                f"- **Data Flag**: `{qual['data_flag']}`"
            )
            self._log_query(q_raw, "data_quality", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "data_quality",
                "answer": answer,
                "evidence": [qual["evidence"]],
                "warnings": [],
            }

        # Intent: Explain rank (specific district)
        if re.search(r"(why.*rank|explain.*rank|why is.*ranked)", q_lower) and district_key:
            exp = self.tools.explain_rank(district_key)
            if exp["status"] != "ok":
                return exp

            if exp["rank"] is None:
                answer = (
                    f"### District Ranking: {exp['district']}\n\n"
                    f"**{exp['explanation']}**\n\n"
                    f"### Evidence\n"
                    f"- **Tool**: `explain_rank`\n"
                    f"- **Source File**: `district_gap_index.csv`\n"
                    f"- **Data Flag**: `insufficient_data`"
                )
                self._log_query(q_raw, "explain_rank", "ok")
                return {
                    "status": "ok",
                    "backend": "offline",
                    "intent": "explain_rank",
                    "answer": answer,
                    "evidence": [exp["evidence"]],
                    "warnings": ["Insufficient EV data: district is left unranked in accordance with competition rules."],
                }

            answer = (
                f"### Ranking Explanation: {exp['district']} (#{exp['rank']})\n\n"
                f"- **Current Rank**: **#{exp['rank']}** (Gap Score: **{exp['gap_score']:.1f}**)\n"
                f"- **Multi-Criteria Robustness**: Rank spans between **#{exp['min_rank']}** and **#{exp['max_rank']}** across AHP, equal, and PCA weighting schemes.\n"
                f"- **Key Drivers**: {exp['drivers']}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `explain_rank`\n"
                f"- **Source File**: `district_gap_index.csv`\n"
                f"- **District Key**: `{exp['district_key']}`\n"
                f"- **Data Flag**: `{exp['data_flag']}`"
            )
            self._log_query(q_raw, "explain_rank", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "explain_rank",
                "answer": answer,
                "evidence": [exp["evidence"]],
                "warnings": [],
            }

        # Intent: Top underserved districts
        if re.search(r"(which district.*need|top.*district|worst gap|highest gap|underserved)", q_lower):
            n_match = re.search(r"top\s*(\d+)", q_lower)
            top_n = int(n_match.group(1)) if n_match else 5
            top_res = self.tools.rank_districts(top_n=top_n)

            lines = []
            for d in top_res["districts"]:
                ev_str = f"{d['ev_total']:,} EVs" if d["ev_total"] is not None else "No EV data"
                lines.append(
                    f"1. **#{d['rank']} {d['district']}**: Gap Score **{d['gap_score']:.1f}** ({ev_str}, {d['port_count']} public ports)."
                )
            ans_body = "\n".join(lines)

            answer = (
                f"### Top {top_n} Most Underserved Districts (Official Rankings)\n\n"
                f"{ans_body}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `rank_districts`\n"
                f"- **Source File**: `district_gap_index.csv`\n"
                f"- **Data Flag**: `real`"
            )
            self._log_query(q_raw, "top_districts", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "top_districts",
                "answer": answer,
                "evidence": [top_res["evidence"]],
                "warnings": ["Synthetic test districts are strictly excluded from official rankings."],
            }

        # Intent: District lookup fallback
        if district_key:
            d = self.tools.get_district(district_key)
            if d["status"] != "ok":
                return d

            if d["rank"] is None:
                answer = (
                    f"### District Status: {d['district']}\n\n"
                    f"**{d['note']}**\n\n"
                    f"- **Public Ports**: {d['port_count']}\n"
                    f"- **Data Flag**: `{d['data_flag']}`\n\n"
                    f"### Evidence\n"
                    f"- **Tool**: `get_district`\n"
                    f"- **Source File**: `district_gap_index.csv`\n"
                    f"- **Data Flag**: `{d['data_flag']}`"
                )
                self._log_query(q_raw, "district_lookup", "ok")
                return {
                    "status": "ok",
                    "backend": "offline",
                    "intent": "district_lookup",
                    "answer": answer,
                    "evidence": [d["evidence"]],
                    "warnings": ["District has no EV registration records in the official VAHAN dataset."],
                }

            answer = (
                f"### District Status: {d['district']} (#{d['rank']})\n\n"
                f"- **Rank**: #{d['rank']} (Gap Score: {d['gap_score']:.1f})\n"
                f"- **Registered EVs**: {d['ev_total']:,}\n"
                f"- **Public Ports**: {d['port_count']} ports ({d['charger_count']} stations)\n"
                f"- **Drivers**: {d['drivers']}\n\n"
                f"### Evidence\n"
                f"- **Tool**: `get_district`\n"
                f"- **Source File**: `district_gap_index.csv`\n"
                f"- **Data Flag**: `{d['data_flag']}`"
            )
            self._log_query(q_raw, "district_lookup", "ok")
            return {
                "status": "ok",
                "backend": "offline",
                "intent": "district_lookup",
                "answer": answer,
                "evidence": [d["evidence"]],
                "warnings": [],
            }

        # General help / unrouted
        answer = (
            "### ChargeGap India — Planner Assistant\n\n"
            "I can assist you with:\n"
            "- **Rank Explanations**: e.g., *'Why is Krishnagiri ranked 3rd?'*\n"
            "- **Top Deficits**: e.g., *'Which districts need chargers most?'*\n"
            "- **Highway Corridors**: e.g., *'Which highway stretch should we fix first?'*\n"
            "- **Site Siting**: e.g., *'Where should we build chargers next?'*\n"
            "- **Bayesian Uncertainty**: e.g., *'How sure are we about Krishnagiri?'*\n"
            "- **What-If Simulations**: e.g., *'What happens if EV growth is 30% faster?'*\n"
            "- **Limitations**: e.g., *'What are the project limitations?'*\n\n"
            "Please ask a specific infrastructure question or select a district."
        )
        self._log_query(q_raw, "general_help", "ok")
        return {
            "status": "ok",
            "backend": "offline",
            "intent": "general_help",
            "answer": answer,
            "evidence": [],
            "warnings": [],
        }
