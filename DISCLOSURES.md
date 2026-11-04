# Disclosures & Academic Integrity Statement

**Project**: ChargeGap India — EV Infrastructure Gap Map & Optimizer  
**Competition**: Techfest 2026–27, IIT Bombay (Challenge 1: EV Infrastructure Map India)  
**Date**: 4 November 2026  
**Document**: `DISCLOSURES.md`  

---

## 1. AI Code Assistance & Engineering Methodology

In strict compliance with transparency, reproducibility, and academic integrity guidelines, the team discloses the use of AI assistance during project development:

1. **AI Assistants Used**:
   - Advanced agentic AI pair programming tools (Google Antigravity, Anthropic Claude 3.5 Sonnet, and Google Gemini models) were utilized for code structuring, test generation, algorithmic boilerplate, and mathematical refactoring.
2. **Human Oversight & Verification Protocol**:
   - Every algorithmic model (Bass/Logistic diffusion fitting, M/M/c Erlang C queueing equations, PuLP MILP MCLP/FRLM formulations, and pgmpy Bayesian Variable Elimination) was reviewed, verified, and cross-checked by the engineering team against published literature and regulatory standards.
   - All code is subject to an automated, non-negotiable commit gate (`python check.py check`), requiring clean bytecode compilation (`python -m compileall -q src api`) and 100% passing automated tests (`pytest -q` — **202 tests passing**).
3. **Data Integrity & Zero Invention Policy**:
   - AI tools were strictly barred from generating synthetic baseline datasets, inventing EV vehicle registration numbers, or guessing charging station counts.
   - Real empirical counts are derived solely from audited MoRTH/VAHAN releases, Census of India benchmarks, and OpenStreetMap/OpenChargeMap APIs.
   - Any synthetic test fixtures exist exclusively in test directories or isolated sandbox files (`*_SYNTHETIC_TEST*`) bearing explicit `data_flag = "synthetic"` metadata that are completely excluded from official rankings.

---

## 2. Planner Assistant Architecture & Tool Use

The ChargeGap India interactive **Planner Assistant** (`src/assistant/`) provides automated natural language explanation of infrastructure deficits, ranking drivers, and siting recommendations.

1. **Dual-Mode Architecture**:
   - **Offline Deterministic Mode** (`src/assistant/offline_backend.py`): Operates 100% locally with zero internet access using rule-based intent parsing and verified template engines. Guarantees complete operational availability at the competition venue.
   - **LLM Tool-Calling Mode** (`src/assistant/llm_backend.py`): Supports Anthropic Claude (`claude-3-5-sonnet-20241022`) tool calling when `ANTHROPIC_API_KEY` is provided in the local environment.
2. **Automatic Offline Fallback**:
   - If an API key is missing, network access is severed, or the Anthropic API times out, the assistant immediately and invisibly falls back to the deterministic offline engine. No user error or empty output is ever returned.
3. **Strict Grounding & Zero Memory Hallucinations**:
   - The assistant is forbidden from answering infrastructure, regulatory, or geographic questions from model internal memory.
   - All figures, ranks, deficits, and site coordinates are retrieved at query time via read-only tools executing over pipeline outputs (`outputs/*.csv`, `outputs/*.geojson`).
   - Every answer terminates with an `### Evidence` block disclosing the underlying data files, district keys, and data flags.
4. **Transparency on Missing Telemetry**:
   - Districts lacking official VAHAN EV counts (e.g. Ariyalur) are explicitly identified as unranked (`status = "no_ev_data"`). The assistant refuses to invent numbers and clearly communicates the data gap.
5. **Indicative Guideline Disclosures (`UNVERIFIED`)**:
   - Ministry of Power (MoP) September 2024 indicative inter-station corridor spacing targets (25 km for light EVs, 100 km for heavy-duty commercial EVs) are explicitly labeled with `[UNVERIFIED: MoP 2024 indicative guideline]` in every assistant response to distinguish policy targets from physical constraints.

---

## 3. Bayesian Network Expert Priors & Provenance

The Phase 2 **Bayesian Uncertainty Layer** (`src/bayes_layer.py`) models spatial uncertainty across 10 discrete domain nodes using `pgmpy`:

1. **Expert Priors vs. Learned Parameters**:
   - Where empirical telemetry (e.g. smart-meter grid feeder loads, real-time charger occupancy) is absent in public datasets, Conditional Probability Distributions (CPDs) are modeled as transparent **expert prior assumptions** in `config/bn_priors.yaml`.
   - Priors are **never** claimed to be learned from data. Each table includes mandatory `rationale` and `source` metadata citing regulatory sources (Central Electricity Authority National Electricity Plan, NITI Aayog Handbook 2021, Bureau of Energy Efficiency, MoP 2024) or explicitly labeled as `"analyst judgement"`.
2. **Exact Marginalization Over Missing Nodes**:
   - When district telemetry is unavailable, the Variable Elimination engine marginalizes over unobserved latent nodes rather than imputing fabricated values. This honestly widens the 80% credible interval ($[P_{10}, P_{90}]$) to represent true epistemic uncertainty.
3. **Dirichlet Sensitivity & Robustness**:
   - Dirichlet distribution perturbations ($\alpha = 15.0$) demonstrate that district deficit classifications remain stable across prior variations, and districts sensitive to prior assumptions are flagged as `prior_dominated = True`.
