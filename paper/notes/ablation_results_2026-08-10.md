# §5.9 Sensitivity Ablation Results — 2026-08-10

Source: `scratchpad/ablations/ablation_{tau,bins,delta}_{re1-ob,re1-ss,re1-tt}.csv`,
computed at commit `d485957` under the pessimistic convention. Three sweeps:
τ (text-match threshold) × SG/EC, B (calibration bins) × ECE, δ (damping) × FCP.

## 1. τ ∈ {0.5 … 0.9} — the two-group division is contingent on τ ≥ 0.6

SG by τ, RE1-OB (all seven methods):

| method | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|
| FODA-FCP | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Micro | **0.400** | 0.000 | 0.000 | 0.000 | 0.000 |
| MR | **0.387** | 0.000 | 0.000 | 0.000 | 0.000 |
| CR | **0.334** | 0.000 | 0.000 | 0.000 | 0.000 |
| yRCA | 0.267 | 0.267 | 0.267 | 0.267 | 0.267 |
| BARO | **0.206** | 0.000 | 0.000 | 0.000 | 0.000 |
| DejaVu | **0.054** | 0.000 | 0.000 | 0.000 | 0.000 |

EC by τ shows the same cliff (RE1-OB): at τ = 0.5 the five floor methods rise to
0.451–0.664; at τ ≥ 0.6 all sit at exactly 0.333.

**Reading.** For τ ∈ [0.6, 0.9] the results are *perfectly* stable — identical to
three decimals, no ordering change. At τ = 0.5 the floor collapses: half-coverage
token matches (e.g. the token "cpu" against the label "CPU Saturation", coverage
1/2) begin to count as grounding, and the two-group division disappears —
MicroRCA (0.400) and MonitorRank (0.387) overtake yRCA (0.267), so the ordering
genuinely inverts.

**Honest statement for §5.9.** The qualitative finding (a sharp two-group split
with an empty middle) holds throughout τ ∈ [0.6, 0.9] and fails at τ = 0.5. The
default τ = 0.7 sits in the middle of the stable region. This both confirms and
bounds Paper 6's untested claim of "robustness in τ ∈ [0.6, 0.8]": the claim is
exactly right, and the boundary is immediately below it. §5.9 must report the
τ = 0.5 breakdown rather than only the stable band — it is the honest form of
the sensitivity analysis reviewers asked for (criticism R8).

## 2. B ∈ {5, 10, 15, 20} — calibration conclusions are robust

RE1-OB: FCP 0.119 / 0.119 / 0.119 / 0.125; DejaVu 0.099 / 0.099 / 0.106 / 0.118;
BARO 0.534 at every B. RE1-TT: FCP 0.243 at every B; BARO 0.390 at every B.

No method ordering changes at any B. The calibration findings do not depend on
the bin count; B = 10 is reported as convention, not necessity.

## 3. δ ∈ {0.5 … 1.0} — **the propagation step monotonically harms ranking accuracy**

FCP AC@1 by damping factor (note: the update is C ← (1−δ)·C + δ·NoisyOR, so
*lower* δ means *heavier* damping, i.e. less propagation influence):

| δ | RE1-OB | RE1-SS | RE1-TT |
|---|---|---|---|
| 0.50 | **0.480** | **0.256** | **0.064** |
| 0.65 | 0.472 | 0.224 | 0.024 |
| 0.75 | 0.440 | 0.200 | 0.024 |
| **0.85 (default)** | 0.400 | 0.160 | 0.008 |
| 0.95 | 0.360 | 0.112 | 0.008 |
| 1.00 (no damping) | 0.344 | 0.064 | 0.000 |

SG is 1.000 at every δ on every system (grounding is independent of propagation,
as designed). SC and EC move mildly and non-monotonically.

**Three findings, in increasing order of discomfort.**

(i) The relationship is monotone on all three systems: heavier damping is better
for ranking, at every step, without exception. This is direct empirical
confirmation of the saturation mechanism of §5.6.1 — reducing propagation's
contribution is exactly what relieves the Noisy-OR product collapse.

(ii) **At δ = 0.5 the RE1-TT result rises to 0.064, which is above the 1/64 ≈
0.0156 chance baseline** — four times the default configuration's 0.008 and
comfortably out of the below-chance regime.

(iii) The uncomfortable corollary: since δ → 0 degenerates toward ranking by
local Mamdani confidence alone, the sweep says FCP's *propagation step — the
algorithmic core of the method — costs ranking accuracy on RCAEval at every
setting tested*. This is consistent with the preliminary conference version's
own ablation, where the "−Propagation" variant beat the full method on MRR
(0.875 vs 0.833) on the synthetic suite; the RCAEval sweep shows the effect is
systematic rather than an artifact of that benchmark.

## 4. Consequences that need author decisions

1. **δ vs the §5.7 refinement.** A one-parameter change (δ = 0.5) yields TT
   AC@1 = 0.064 from 0.008, whereas the local-H score refinement has a *ceiling*
   of 0.152 with the measured value still pending. The two are independent and
   composable. §5.7 currently presents the refinement as the mitigation; the δ
   result may be the stronger and simpler one, and it is a *parameter* choice
   rather than a method variant, so it does not carry the post-hoc-design
   caveat in the same way (though re-tuning δ after seeing results is itself a
   post-hoc choice that must be disclosed).
2. **Boundary not yet found.** δ = 0.5 is the lowest value tested and is still
   improving. A follow-up sweep over δ ∈ {0.1, 0.2, 0.3, 0.4} plus an explicit
   local-H-only baseline (δ → 0) would establish whether the optimum is interior
   or whether propagation is simply harmful throughout. **Recommended before
   §5.9 is drafted** — without it the paper cannot say whether the method's core
   mechanism has any ranking-positive regime at all.
3. **Narrative impact.** The paper's honest characterisation becomes sharper and
   less comfortable: the ontology grounding and explanation structure are robust
   and valuable (SG = 1.000 at every δ and τ), while the propagation mechanism —
   the part inherited from the conference version — degrades ranking on this
   benchmark family. §6′ and §7 need to absorb this rather than bury it.
