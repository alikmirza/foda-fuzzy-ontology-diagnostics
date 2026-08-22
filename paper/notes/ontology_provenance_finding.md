# STOP-condition finding: ontology provenance vs RCAEval work (step 4)

**Status: the §3.6 claim is REFUTED by git history. Work halted per ruling.**

The drafted §3.6 states that "§5's benchmark faults were not used to extend the
ontology," carrying my note that "the repo history suggests the propagation set
predates the RCAEval work." The history shows the opposite.

## Verified timeline

| date | commit | event |
|---|---|---|
| 2026-03-08 | `fe58e61` | project foundation; DiagnosticKB created |
| 2026-05-04 | `32358e8` | ontology-grounded explanations for the LNNS chapter. **Ontology contains 0 `Prop_*` individuals at this point.** |
| 2026-05-08 | `a470f9a`, `ffbc05e`, `af7aedc` | RCAEval evaluation module, RCAEval loader, Online Boutique loader |
| 2026-05-12 20:37 | `ceebb25`, `f6bf9d3` | SemanticGroundedness metric + **SG run over 7 methods × 125 cases** — benchmark results in hand |
| **2026-05-12 23:01** | **`85cbb8d`** | **all 22 `Prop_*` individuals added to the ontology (+276 lines), in the same commit as `semantic_coherence.py` (+436) and a 68-line change to `foda_fcp.py`** |
| after | — | no further ontology edits |

## What this means precisely

1. **The propagation table postdates the start of RCAEval evaluation by four
   days**, and postdates the first full 7-method × 125-case metric run by about
   two and a half hours.
2. **The propagation table, the metric that scores against it, and a change to
   the method that emits the links being scored were all authored in a single
   commit** while benchmark data was available.
3. The eight fault prototypes are *not* affected — they predate the RCAEval work
   (present at `32358e8`, 2026-05-04, for the LNNS chapter). Only the
   propagation layer is implicated.
4. The ontology contains **no RCAEval-specific content**: zero occurrences of any
   benchmark service name. The propagations relate fault prototypes to fault
   prototypes, not services to services.

## Assessment — what is and is not compromised

**Not compromised:** SG, EC, AC@1, calibration, the §5.6 mechanism analysis, the
§5.7 refinement, the §5.9 dose–response. None of these consume the propagation
table. The grounding claim (every atom carries an IRI) rests on the fault
prototypes, which predate the benchmark work.

**Compromised as stated:** the independence claim in §3.6, and the framing in
§3.4 and §5.8 that presents the propagation table as prior curated domain
knowledge against which the method's links are independently checked. That
framing cannot stand as written.

**Mitigating, and worth stating rather than hiding:**
- The measured SC values are *low* — 0.266 / 0.158 / 0.086 — and the §5.8
  analysis is about the method disagreeing with its own table. A table authored
  to flatter the method would have produced high coherence. The direction of the
  result is evidence against tuning-to-flatter, and is the strongest available
  defence.
- No benchmark-specific vocabulary entered the ontology.
- The propagations are inter-prototype domain claims (e.g. CpuSaturation →
  LatencySpike), a form of knowledge that does not depend on which benchmark is
  in view.

## Options (author's ruling required before any further step)

**Option A — disclose and reframe.** Correct §3.6, and rewrite §3.4/§5.8 to say
the propagation layer was authored during the evaluation period, for the purpose
of the coherence metric, and therefore does not constitute independent prior
knowledge. Add the low-SC direction-of-result argument. Costs nothing empirically
and pre-empts a reviewer who reads the public history; §5.8's finding survives,
with a weaker independence claim.

**Option B — external validation.** Have the propagation set reviewed or
re-derived by someone outside the evaluation (Kosov is the natural candidate,
given the CRediT ontology-engineering role), and report the agreement rate. This
converts an unverifiable provenance claim into a measured one, at the cost of
coordination time.

**Option C — drop SC from the paper's contribution claims** and report it as a
descriptive statistic only, with §5.8 recast as an internal-consistency
observation rather than an audit. Safest, and loses the R6 answer.

**Recommendation: A now, B if time permits before submission.** A is required
regardless — the history is public in the artifact release, so any claim of
independence is falsifiable by any reviewer who runs `git log`. B strengthens it
materially and is the only route back to an independence claim.

## Related exposure

Paper 6 relies on the same propagation table for its SC results. If this paper
discloses the sequence, Paper 6's Q2 revision must carry the same disclosure —
add to `paper6_q2_corrections.md` as correction #5 once the ruling lands.
