# Extended δ sweep — accuracy–explanation trade-off (the gating measurement)

Single-run provenance: `scratchpad/delta_ext/delta_extended_{re1-ob,re1-ss,re1-tt}.csv`,
11 δ values × 3 systems × 125 cases, FODA-FCP, pessimistic convention, atoms
under the corrected dual-channel semantics. δ = 0.001 is the δ → 0 limit
(local-Mamdani-only ranking); `ac1_refined` is the (−C, −H) lexicographic variant.

## The headline: there is NO trade-off

Damping's ranking gain does **not** cost explanation quality. Across all three
systems, as δ decreases: AC@1 improves, SC improves, EC improves or holds, and
SG is invariant at 1.000. The propagation step degrades every measured axis.

### RE1-TT (64 services)

| δ | AC@1 shipped | AC@1 refined | SG | SC | EC |
|---|---|---|---|---|---|
| **0.001 (local-H only)** | **0.464** | 0.464 | 1.0 | **0.372** | **0.835** |
| 0.100 | 0.376 | 0.376 | 1.0 | 0.282 | 0.835 |
| 0.200 | 0.216 | 0.216 | 1.0 | 0.212 | 0.824 |
| 0.300 | 0.112 | 0.112 | 1.0 | 0.154 | 0.805 |
| 0.400 | 0.072 | 0.072 | 1.0 | 0.106 | 0.800 |
| 0.500 | 0.064 | 0.064 | 1.0 | 0.084 | 0.784 |
| 0.650 | 0.024 | 0.032 | 1.0 | 0.086 | 0.763 |
| 0.750 | 0.024 | 0.056 | 1.0 | 0.074 | 0.768 |
| **0.850 (as-shipped)** | **0.008** | 0.144 | 1.0 | 0.086 | 0.789 |
| 0.950 | 0.008 | 0.192 | 1.0 | 0.132 | 0.816 |
| 1.000 | 0.000 | 0.208 | 1.0 | 0.172 | 0.827 |

**AC@1 rises 58× from the shipped setting to the δ → 0 limit (0.008 → 0.464).**
At 0.464 the method sits within the unsupervised baseline band — above BARO
(0.392) and just below MicroRCA (0.456), MonitorRank (0.480) and CausalRCA
(0.472) — instead of below the 1/64 chance baseline. SC simultaneously rises
from 0.086 to 0.372 (4.3×) and EC from 0.789 to 0.835.

### RE1-SS (15 services)

| δ | AC@1 | SC | EC |
|---|---|---|---|
| 0.001 / 0.100 / 0.200 | **0.408** | 0.302 / 0.294 / 0.296 | 0.755 |
| 0.500 | 0.256 | 0.210 | 0.755 |
| **0.850 (as-shipped)** | **0.160** | 0.158 | 0.749 |
| 1.000 | 0.064 | 0.144 | 0.739 |

Monotone; a flat optimum plateau across δ ≤ 0.2 at 0.408 (2.55× the shipped value).

### RE1-OB (12 services)

| δ | AC@1 | SC | EC |
|---|---|---|---|
| 0.001 | 0.552 | 0.398 | 0.835 |
| **0.100 (interior optimum)** | **0.560** | **0.400** | 0.835 |
| 0.200 | 0.544 | 0.396 | 0.835 |
| 0.500 | 0.480 | 0.304 | 0.835 |
| **0.850 (as-shipped)** | **0.400** | 0.266 | 0.824 |
| 1.000 | 0.344 | 0.234 | 0.819 |

The only system with a genuine interior optimum, and it is shallow: 0.560 at
δ = 0.1 against 0.552 at the δ → 0 limit. A small amount of propagation helps
on a 12-service graph; the benefit vanishes by 15 services.

## What this means

1. **The default δ = 0.85 is far from optimal on every system and every axis.**
   Shipped AC@1 0.400 / 0.160 / 0.008 versus best-δ 0.560 / 0.408 / 0.464.
2. **The propagation step, the algorithmic core carried from the conference
   version, is net-harmful on RCAEval** at every setting above δ ≈ 0.2, and its
   harm grows with graph size — exactly the saturation mechanism of §5.6.1, now
   measured as a continuous dose-response rather than inferred at one point.
   This is consistent with, and much stronger than, the conference version's own
   ablation in which the "−Propagation" variant beat the full method on MRR
   (0.875 vs 0.833) on the synthetic suite.
3. **No accuracy–explanation trade-off exists to manage.** The framing that
   damping buys ranking accuracy at the cost of explanation quality is refuted:
   SC and EC move in the same direction as AC@1. Only SG is indifferent
   (invariant at 1.000), because grounding is structural.
4. **The refinement of §5.7 is a high-δ phenomenon.** `ac1_refined` differs from
   `ac1_shipped` only for δ ≥ 0.65, where saturation ties exist; at low δ the
   two coincide exactly. The refinement is a repair for a regime that the δ
   sweep suggests should be avoided altogether.

## Consequences requiring author decisions

- **δ selection is now a first-order paper question, not an ablation footnote.**
  Reporting δ = 0.85 as the headline while the sweep shows δ ≤ 0.2 dominating on
  every axis needs an explicit, defensible rationale — and post-hoc re-tuning
  after seeing results carries the same forking-paths concern that closed the
  fuzzy-metric search.
- **§5.9's binding framing (δ = 0.85 headline, sweep as characterisation) still
  holds mechanically, but its rationale must now absorb a 58× effect.** The
  honest options: keep δ = 0.85 as-shipped and report the sweep as the
  method's principal limitation; or re-baseline to a defensible low-δ setting
  and disclose the re-tuning explicitly with the sweep as its justification.
- **§4.4–4.5's framing of damped propagation as the contribution** cannot stand
  unqualified alongside this table.
