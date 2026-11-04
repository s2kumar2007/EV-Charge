# Bayesian Uncertainty Layer Design Specification

**Module**: `src/bayes_layer.py`  
**Configuration**: `config/bn_priors.yaml`  
**Outputs**: `outputs/bayes_district_posteriors.csv`  
**Author**: Lead Engineer, ChargeGap India (Techfest 2026–27, IIT Bombay)  
**Date**: 3 November 2026  

---

## 1. Executive Summary & Design Philosophy

In Phase 1 of ChargeGap India, charger requirements and port deficits were sized using deterministic ratio benchmarks (CEA standard: 20 EVs/port) and Monte Carlo undercount simulations. While effective, Monte Carlo treats missing variables either as zeros or requires point imputations.

The **Phase 2 Bayesian Uncertainty Layer** replaces heuristic handling of missing and noisy inputs with rigorous probabilistic reasoning:
1. **Marginalization over Missing Evidence**: If a district lacks VAHAN EV counts or grid measurements, we **never impute fake numbers**. The Bayesian Network (BN) simply marginalizes over unobserved nodes, producing a wider posterior distribution (e.g. credible interval expands from `[40, 60]` to `[20, 110]`), signaling genuine institutional uncertainty.
2. **Explicit Expert Prior Provenance**: We strictly reject pseudo-empirical "trained" networks where probability tables are learned from tiny, unrepresentative datasets and passed off as "empirical truths". All Conditional Probability Distributions (CPDs) are **explicitly cataloged expert assumptions** stored in human-readable YAML (`config/bn_priors.yaml`), each with a documented regulatory source (CEA, NITI Aayog, MoP, BEE) or tagged as `"analyst judgement"`.
3. **Driver Attribution & Prior Sensitivity**: For every district, the layer computes:
   - The **80% Credible Interval** over required ports.
   - **Driver Attribution**: Which observed evidence (or missing information) moved the posterior the most?
   - **Prior-Sensitivity Index**: Whether the conclusion is data-dominated or prior-dominated.

---

## 2. Directed Acyclic Graph (DAG) Structure

The network models the causal structure of EV infrastructure demand, crowdsourced supply distortions, and grid constraints across Indian administrative districts.

```
       [Urbanisation]        [EV_growth]       [Traffic_exposure]
          /     \                 |                  /
         /       v                v                 v
        /   [Charging_behaviour]  [Demand_ports] <---
       /              \               /
      v                v             v
[True_charger_supply] <--- [Requirement_class]
         ^                        |
         |                        v
 [OSM_completeness]          [Gap_class] <--- [Grid_headroom]
```

### 2.1 Nodes and Discrete State Bins

| Node Name | States | Meaning & Value Bins | Derivation from Phase 1 Outputs |
| :--- | :--- | :--- | :--- |
| **`Urbanisation`** | `low`, `med`, `high` | Commercial node density per $\text{km}^2$ and population density | Phase 1 OSM POI density & 2022 population estimate (quantiles: $<33\%$, $33-66\%$, $>66\%$) |
| **`EV_growth`** | `low`, `med`, `high` | Projected compound annual growth rate of EV registrations | Phase 1 Bass/Logistic diffusion slope or annual registration tier ($<15\%$, $15-35\%$, $>35\%$) |
| **`Traffic_exposure`** | `low`, `med`, `high` | Exposure to national/state highway corridor transit flows | Phase 1 Road density ($\text{km}/\text{km}^2$) & intersection with NH/SH corridor buffers |
| **`OSM_completeness`** | `poor`, `fair`, `good` | Reliability of crowdsourced public charging data | Phase 1 charger confidence scores ($<0.50$ = poor, $0.50-0.75$ = fair, $\ge 0.75$ = good) |
| **`Grid_headroom`** | `low`, `med`, `high`, `unknown` | Substation transformer spare capacity | District discom feeder logs; set to **`unknown`** when no real grid telemetry exists |
| **`Charging_behaviour`** | `home_dominant`, `mixed`, `public_dominant` | Dominant charging regime of local EV owners | Latent node conditioned on `Urbanisation` (high-density multistory housing lacks home charging) |
| **`True_charger_supply`**| `low`, `med`, `high` | Actual physical operational charging supply | Inferred from observed charger counts adjusted for `OSM_completeness` undercount |
| **`Demand_ports`** | `low`, `med`, `high` | Aggregate port demand from registered and transit EVs | Inferred from `EV_growth`, `Urbanisation`, `Traffic_exposure`, `Charging_behaviour` |
| **`Requirement_class`** | `tier_1_low`, `tier_2_med`, `tier_3_high`, `tier_4_severe` | Net new public charging ports required | Bins: `<50` ports, `50–200` ports, `200–500` ports, `>500` ports |
| **`Gap_class`** | `adequate`, `moderate`, `critical` | Urgency of public infrastructure deficit | Synthesis of `Requirement_class` tempered by `Grid_headroom` bottlenecks |

---

## 3. Causal Edges & Justifications

1. **`Urbanisation -> Charging_behaviour`**:
   - *Rationale*: In rural/peri-urban districts (`low`), EV owners predominantly possess independent single-family homes with dedicated 15A plugs (`home_dominant`). In high-density urban metros like Chennai or Coimbatore (`high`), 60–75% of vehicle owners reside in multi-unit dwellings lacking dedicated chargers, necessitating public/workplace reliance (`public_dominant`).
   - *Source*: NITI Aayog "Handbook for EV Charging Infrastructure Implementation", Section 2.1.
2. **`EV_growth -> Demand_ports`**:
   - *Rationale*: Direct causal link. Faster fleet adoption expands daily kWh replenishment requirements.
   - *Source*: CEA National Electricity Plan (Vol. II) EV charging projections.
3. **`Urbanisation -> Demand_ports`**:
   - *Rationale*: Urban agglomerations feature higher daily vehicle kilometers travelled (VKT) and commercial fleet densities (e-rickshaws, e-taxis, delivery 2Ws).
4. **`Traffic_exposure -> Demand_ports`**:
   - *Rationale*: Major national highway corridors (e.g. NH-48 Chennai–Bengaluru) bring non-local transit traffic that cannot charge at home, inducing en-route fast-charging demand.
5. **`Charging_behaviour -> Demand_ports`**:
   - *Rationale*: A public-dominant charging regime requires 1 public port per 15–20 EVs, whereas a home-dominant regime requires only 1 public port per 50–100 EVs.
6. **`OSM_completeness -> True_charger_supply`**:
   - *Rationale*: Crowdsourced data sources (OSM, OCM) consistently suffer from volunteer coverage bias. Poor completeness indicates that actual on-ground chargers exceed observed counts.
7. **`Demand_ports + True_charger_supply -> Requirement_class`**:
   - *Rationale*: Net requirement is the structural difference between total demand and existing supply.
8. **`Requirement_class + Grid_headroom -> Gap_class`**:
   - *Rationale*: A district needing $>500$ ports with high grid headroom can deploy chargers rapidly; however, if grid headroom is low or constrained, the infrastructure gap is severely critical because transformer upgrades require 18–24 months lead time.

---

## 4. What is Data vs. What is Assumption

To satisfy the competition's strict **honesty and provenance mandate**:

### Observed Data (from Phase 1 Pipelines)
- District EV registration totals and growth metrics (VAHAN official Lok Sabha annexure).
- OpenStreetMap and OpenChargeMap verified charger observations with confidence scores.
- Spatial indicators: OSM primary/trunk road densities ($\text{km}/\text{km}^2$), commercial node densities ($\text{nodes}/\text{km}^2$).
- Geographic boundary polygons (geoBoundaries / pinned official shapefiles).

### Expert Assumptions (cataloged in `config/bn_priors.yaml`)
- Prior probabilities for root nodes (`EV_growth`, `Urbanisation`, `Traffic_exposure`, `Grid_headroom`).
- Conditional probability tables for latent nodes (`Charging_behaviour`).
- Likelihood matrices mapping demand and supply combinations to requirement tiers.
- *Every probability value in the YAML includes a mandatory citation or the label `"analyst judgement"`.*

---

## 5. Handling Missing Inputs by Marginalisation

A core architectural advantage of Bayesian networks is that inference operates over arbitrary evidence subsets:
$$P(\text{Requirement\_class} \mid \mathbf{e}) = \frac{\sum_{\mathbf{X} \setminus (\{\text{Requirement\_class}\} \cup \mathbf{e})} P(\mathbf{X})}{\sum_{\mathbf{X} \setminus \mathbf{e}} P(\mathbf{X})}$$

- **Case 1: Fully Observed District (e.g. Chennai)**:
  Evidence $\mathbf{e} = \{\text{Urbanisation: high}, \text{EV\_growth: high}, \text{Traffic: high}, \text{OSM: good}, \text{Grid: unknown}\}$.
  Posterior yields sharp distribution: $P(\text{tier\_4\_severe}) = 0.88$, credible interval `[1420, 1950]` ports.
- **Case 2: Missing EV Data District (e.g. unranked rural district)**:
  Evidence $\mathbf{e} = \{\text{Urbanisation: low}, \text{Traffic: med}, \text{OSM: poor}\}$. `EV_growth` is **unobserved**.
  The inference engine marginalizes over `EV_growth`, yielding a wide, diffuse posterior: $P(\text{tier\_1}) = 0.45, P(\text{tier\_2}) = 0.35, P(\text{tier\_3}) = 0.20$.
  The credible interval spans `[10, 180]` ports, and the output row is flagged with `data_flag = "insufficient_data"` and `drivers = "Wide uncertainty due to unobserved EV fleet"`.

---

## 6. Output Schema & Reconciled Metrics

Each row in `outputs/bayes_district_posteriors.csv` carries:
- `district_key`, `district`: Identifier.
- `req_p10`, `req_p50`, `req_p90`: Credible interval bounds over required ports.
- `req_ci_80_width`: Absolute uncertainty width ($P_{90} - P_{10}$).
- `prob_adequate`, `prob_moderate`, `prob_critical`: Discrete Gap Class probability distribution.
- `top_driver_1`, `top_driver_2`: Primary observed or unobserved factors shifting the posterior.
- `prior_dominated`: Boolean flag (`True` if Dirichlet sensitivity shifts $P_{50} > 25\%$).
- `monte_carlo_p50`: Corresponding Phase 1 Monte Carlo requirement estimate for cross-validation.
- `model_agreement`: Categorical (`high_agreement`, `moderate_agreement`, `divergent`).
- `data_flag`: `real`, `insufficient_data`, or `synthetic`.
