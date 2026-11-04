# ChargeGap India — 5-Minute Jury Presentation & Demo Script

**Event**: Techfest 2026–27, IIT Bombay  
**Challenge**: Challenge 1 — EV Infrastructure Map India (Slice 0 + 1)  
**Corridor Focus**: Chennai – Vellore – Bengaluru (NH-48) & Tamil Nadu Statewide  
**Duration**: 5–7 Minutes (Timed walkthrough with live commands, map interactions, Bayesian uncertainty, and grounded assistant)  

---

## Quick Reference Commands for Demo

```bash
# 1. Verify all 144 offline tests pass in < 15 seconds
python check.py check

# 2. Run the end-to-end analytical pipeline (Slices 0 + 1)
python run_all.py

# 3. Launch the interactive Leaflet dashboard and API
python run_dashboard.py
# Open browser at: http://127.0.0.1:8000
```

---

## 5-Minute Timed Presentation Script

### Minute 0:00 – 1:00: The Problem & Data Honesty Bar
**Presenter Dialogue**:
> "Good morning, esteemed jury. Today, public EV infrastructure planning in India suffers from two critical flaws: raw charger counts that ignore vehicle adoption reality, and dashboards that invent numbers to fill gaps.
>
> In ChargeGap India, we enforce a strict **zero-invented-data** standard. If a district lacks official VAHAN EV counts, we do not hallucinate a figure — we flag it as `insufficient data` and exclude it from ranking. Every data point on our map carries an auditable provenance flag (`real`, `synthetic`, or `projected`), a confidence score, and a plain-language explanation of its sizing drivers."

**Action**:
- Run `python check.py check` in terminal: show **144 tests passing** with zero failures.
- Show `district_gap_scores.csv`: point to `rank`, `data_flag = real`, and `confidence = 0.85`.

---

### Minute 1:00 – 2:00: Highway Corridor Analysis (NH-48)
**Presenter Dialogue**:
> "Let’s zoom into the high-traffic freight and passenger corridor: **NH-48 (Chennai to Bengaluru via Vellore)**.
>
> In 2024, the Ministry of Power mandated a maximum inter-station distance of **25 km** for light EVs, and **100 km** for heavy-duty commercial EVs. Naive maps plot chargers as isolated points; ChargeGap snaps chargers to actual highway geometry in a metric CRS (UTM 44N) and evaluates consecutive site spacing.
>
> Even with all public chargers mapped, we identify a **34.6 km unserved stretch** between Ranipet and Vellore bypass. When filtering for high-confidence chargers ($\ge 0.80$), that gap widens to **48.2 km**, violating MoP guidelines."

**Action**:
- Switch to dashboard map: toggle **Corridors** layer on.
- Point to the dashed red highway stretch between Ranipet and Vellore.
- Click the corridor segment popup: show *Consecutive Gap: 34.6 km (Limit: 25 km) — MoP 2024 Non-Compliant*.

---

### Minute 2:00 – 3:00: Queueing Delay & Sizing Intervals (Erlang C)
**Presenter Dialogue**:
> "How many chargers are actually needed? Rather than relying on arbitrary rules of thumb, ChargeGap provides two validated sizing engines:
> 1. A transparent **EVs-per-port ratio** (CEA benchmark: 20 EVs/port) weighted by existing charger confidence.
> 2. An **M/M/c Erlang C queueing model** that sizes ports to ensure average driver waiting time remains strictly under 10 minutes ($W_q < 10\text{ min}$) during peak charging hours.
>
> Because real EV adoption and charger reporting are uncertain, we run a seeded Monte Carlo simulation over adoption growth and undercount rates, producing calibrated **P10, P50, and P90 port deficit ranges** for every district."

**Action**:
- In the dashboard, click **Chennai** in the District Ranks table.
- Open the **Drill-Down** panel:
  - Show EV Registrations: 34,710
  - Show Existing Public Ports: 60
  - Show Port Deficit: **P50 = 1,675 ports [P10: 1,420 – P90: 2,110]**
  - Show spatial hotspot status: *Gi\* High-Deficit Cluster (z = 4.12, p < 0.001)*.

---

### Minute 3:00 – 4:00: Site Optimization (MILP MCLP + FRLM)
**Presenter Dialogue**:
> "Knowing the deficit is only half the battle. Where should a public agency invest its budget first?
>
> We formulated a Mixed-Integer Linear Program (MILP) combining **Maximal Covering Location (MCLP)** and **Flow-Refueling Location (FRLM)** solved via PuLP and CBC. The model evaluates candidate locations generated along flagged highway gaps and urban deficit centroids under a budget of $K = 15$ sites.
>
> The optimizer prioritizes candidates near major highway junctions and high-demand clusters with road classification bonuses (National Highways receive higher flow weights)."

**Action**:
- In dashboard, switch to **Sites** tab and toggle **Recommended Sites** on the map.
- Click on **#1 Recommended Site: Kanchipuram Highway Junction (NH-48 Bypass)**:
  - Show Type: *Highway Corridor*
  - Show Recommended Ports: *4 Fast-Charging Ports (CCS2 / 60 kW)*
  - Show Drivers: *Resolves 34.6 km corridor spacing breach; high highway transit score*.

---

### Minute 4:00 – 5:00: Live What-If Simulation & Jury Q&A
**Presenter Dialogue**:
> "Finally, policymakers require scenario planning tools. What if EV adoption surges faster than expected? What if existing chargers are undercounted by 50%?"

**Action**:
- Click **What-If** tab in the dashboard.
- Drag **EV Fleet Growth** slider from `+20%` to `+50%`.
- Drag **Target EVs per Port** slider from `20` to `15` (higher service quality).
- Click **Run Simulation**:
  - Show immediate update via `POST /api/whatif`.
  - Highlight the updated state P50 deficit expanding from 3,412 to 5,680 ports.
  - Show that relative priority ranking remains rock-solid.

---

### Minute 5:00 – 7:00: Phase 2 — Bayesian Uncertainty & Grounded Planner Assistant
**Presenter Dialogue**:
> "In Phase 2, we tackle two major challenges raised in Round 1:
> First, real-world planning data is often incomplete or noisy. Instead of fabricating missing telemetry, our **Bayesian Uncertainty Layer** (pgmpy) uses exact Variable Elimination to marginalize over unobserved nodes. Notice how an unranked district like Kanyakumari automatically receives an honest, widened 80% credible interval rather than a fake point estimate.
>
> Second, busy policymakers cannot parse dozens of CSVs. We built an interactive **Planner Assistant** with dual backends: 100% deterministic offline execution for zero-connectivity competition venues, and Anthropic Claude tool use when online. The assistant enforces strict institutional guardrails: zero memory hallucinations, mandatory evidence citations, and transparent disclosures on unverified guidelines."

**Action 1 (Bayesian Credible Interval & Unranked Honesty)**:
- In the dashboard, select **Kanyakumari** (unranked district with no chargers in Slice 0/1):
  - Point to the **Bayesian Uncertainty Card** in the drill-down panel.
  - Highlight the widened 80% credible interval ($[P_{10}, P_{90}]$) expanding to 115+ ports.
  - Explain: *"Notice how our Bayesian layer does not guess a single number. It marginalizes over unobserved telemetry, signaling to planners that this district requires field verification before capital commitment."*

**Action 2 (One-Click Ranking Explanation — Zero Typing)**:
- In the District Rankings table or drill-down card, click the **⚡ Explain** button on **Chennai**:
  - Show the Planner Assistant panel immediately populating with a structured response:
    - Current Rank: #1
    - Total EVs: 34,710
    - Existing Public Ports: 60
    - Sized Deficit: ~1,675 ports
    - Key Drivers: Massive fleet size and low port density.
  - Click the **Evidence** dropdown: show full provenance citing `outputs/district_gap_scores.csv` and `outputs/charger_requirements.csv` with `data_flag = real`.

**Action 3 (Interactive Assistant Query — Krishnagiri Ranking & Confidence)**:
- In the Assistant chat input, click the suggested chip or submit:  
  `"Why is Krishnagiri ranked 3rd and how sure are we?"`
- Present the assistant's answer:
  - Details high EV adoption relative to existing public supply (EV-to-port ratio).
  - Cross-references the Monte Carlo sizing range with the Bayesian 80% credible interval ($[P_{10}: 180, P_{90}: 245]$ ports).
  - Notes that Dirichlet prior sensitivity confirms the classification is robust.

**Action 4 (Corridor Gap Prioritization & UNVERIFIED Disclosure)**:
- Ask the assistant:  
  `"Which highway corridor stretch should we fix first?"`
- Present the assistant's grounded answer:
  - Identifies NH-48 between Ranipet and Vellore bypass as the top priority (34.6 km gap).
  - Point out the prominent disclosure badge in the response:  
    `[UNVERIFIED: Ministry of Power 2024 indicative 25 km guideline]`.
  - Explain to the jury: *"Our assistant never presents policy guidance as hard ground truth without flagging its verification status."*

---

## Anticipated Jury Questions & Authoritative Answers

### Q1: "What if VAHAN data misses unregistered commercial or retrofitted vehicles?"
> **Answer**:  
> "That is precisely why we integrated the **Charger Undercount Multiplier** and Monte Carlo uncertainty intervals. Our baseline applies an undercount distribution $N(1.0, 0.08)$ over fleet size and $U(0.9, 1.1)$ over charger counts. When policymakers anticipate higher informal fleet penetration, they simply adjust the undercount factor in the What-If engine or configure `VAHAN_UNDERCOUNT_FACTOR` in `src/config.py`. The resulting P10–P90 interval shields infrastructure budgets from under-sizing."

### Q2: "Why use both Erlang C queueing and ratio sizing?"
> **Answer**:  
> "Ratio sizing (e.g. 20 EVs per port) is the standard metric used by CEA, NITI Aayog, and state nodal agencies for macro budgetary allocations. However, ratio sizing assumes uniform arrival. In high-demand urban corridors, charging demands cluster at peak hours. Erlang C calculates the physical probability of queuing $P_C$ and waiting time $W_q$. By cross-validating both, we ensure that a district sized at 20 EVs/port also satisfies the service-level guarantee of $W_q < 10\text{ minutes}$."

### Q3: "Why did the optimizer place a candidate at Kanchipuram bypass instead of inside Kanchipuram town?"
> **Answer**:  
> "The MILP objective maximizes dual coverage: serving urban deficit demand while resolving highway corridor spacing breaches. Placing the charging plaza at the NH-48 Kanchipuram bypass intersection captures both long-distance inter-city transit traffic along the Chennai–Bengaluru corridor and peri-urban local traffic, achieving a 2.4× higher flow-coverage score than a purely intra-city location."

### Q4: "How does the model handle districts with no EV data?"
> **Answer**:  
> "In strict compliance with competition rules, we never invent data. Districts without verified VAHAN records receive a `status = 'no_ev_data'` and an empty `rank`. On our dashboard and map, they appear with dashed neutral boundaries and an explicit 'Insufficient Data' banner. They are automatically logged in `TODO_MANUAL.md` for ground verification."

### Q5: "Where did the probability distributions in your Bayesian network come from? Were they learned from data?"
> **Answer**:  
> "We are 100% transparent: our Conditional Probability Distributions in `config/bn_priors.yaml` are expert assumptions derived from regulatory benchmarks (CEA National Electricity Plan, NITI Aayog Handbook 2021, BEE, MoP 2024 Guidelines) or labeled as analyst judgement. We never fabricate data or pretend priors are learned from data where telemetry is absent. Furthermore, our Dirichlet sensitivity analysis ($\\alpha=15.0$) proves that district classifications remain stable across prior perturbations."

### Q6: "Can your Planner Assistant hallucinate numbers or cite outdated policy?"
> **Answer**:  
> "No. The assistant architecture strictly forbids answering from internal model memory. Every metric, ranking, deficit, and coordinate is fetched at runtime by deterministic tools executing over pipeline artifacts. Every answer terminates with an explicit evidence block and propagates `UNVERIFIED` tags for indicative benchmarks."

### Q7: "What happens if there is no internet connection at the competition venue?"
> **Answer**:  
> "Everything runs 100% offline. The analytical pipeline, the FastAPI service, the Leaflet maps with cached assets, and the Planner Assistant all function completely disconnected. If `ANTHROPIC_API_KEY` is absent or the venue has no internet, the assistant's deterministic rule-based router seamlessly handles all questions with zero downtime."

---

*ChargeGap India — Techfest 2026–27, IIT Bombay*
