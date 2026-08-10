# Paper 6 — Section Outline (Sections 3–6)

**Status:** structural planning, not draft prose. Drafting happens in
subsequent sessions.

**Constraints.** Venue-neutral, Times New Roman 12pt, single column.
25–30 body pages for §§3–6; 6–11 pages of tables/figures/references.
Audience: SE / RCA researchers and practitioners. Write
economically.

**Evidence sources (locations).**

* `paper/notes/findings.md` (3,075 lines) — primary empirical source.
  Section anchors used below abbreviate findings.md top-level headers.
* `DEVIATIONS.md` (1,795 lines) — method-adapter and metric-design
  choices feeding Threats to Validity.
* `paper/artifacts/scatter_ac1_vs_*.png` — four 6"×6" scatter PNGs
  (AC@1 vs SG / SC / EC / ECE_proxy).
* `paper/artifacts/{dejavu_attention,yrca_explanation,foda_fcp_explanation}_samples.json`
  — per-method canonical-explanation samples for Figure 7.
* `results/phase2_integration_headline_re1-{ob,ss,tt}.csv` — headline tables.
* `results/phase2_correlation_matrices.csv` — Spearman matrices.
* `results/phase2_cross_system_comparison.csv` — cross-system delta.

---

## Section 3 — The Framework (~6 pages)

### 3.1 Canonical Diagnostic Explanation Form (~1 page)

* **Headline claim.** Every RCA method's output, regardless of
  method family, can be projected onto a common substrate of
  ontology-typed atoms and weighted causal links. The four
  semantic-quality metrics operate on this substrate, not on
  per-method outputs directly.
* **Content.**
  * Define `CanonicalExplanation` as a DAG of `ExplanationAtom`
    (text + optional ontology URI + optional fuzzy membership)
    and `CausalLink` (source/target atom IDs + weight + relation
    type). Cite the dataclass at
    `evaluation/extraction/canonical_explanation.py:14-126`.
  * Argue method-agnosticism: every Phase 1 method's adapter
    emits this form. List the seven adapters with one-line
    summary of what each contributes.
  * Worked example: one canonical form for an FCP diagnosis,
    showing cause atom + service atom + recommendation atom + 2
    causal links.
* **Evidence.** findings.md §§ "MonitorRank baseline" through
  "FODA-FCP entry" (lines 11–894) — per-method explanation
  shapes documented during Phase 1.
* **Tables/figures.** Figure 1 (framework conceptual diagram)
  and Figure 2 (canonical form example) appear in this
  subsection.

### 3.2 SemanticGroundedness (~1.5 pages)

* **Headline claim.** SG measures whether explanation atoms speak
  the ontology's vocabulary. Token-aligned fuzzy matching at
  coverage ≥ 0.7 gives a method that grounds zero atoms an
  honest 0 score; the threshold and matcher are reproducible.
* **Content.**
  * Formal definition: SG = |grounded atoms| / |all atoms|, with
    grounding via `OntologyAdapter.find_class_by_label` at
    coverage ≥ 0.7.
  * Token-alignment algorithm (`rapidfuzz.utils.default_process`
    + min-length-3 content tokens). Why fuzzy is better than
    exact match for cross-method comparison.
  * Configurable knobs (threshold, min token length) and why
    they were chosen.
  * Worked example: FCP atom `"adservice CPU saturation"`
    grounds at coverage 1.0; MR atom `"frontend"` doesn't
    ground (no fault prototype label matches).
* **Evidence.** findings.md "Phase 2 Week 1: SemanticGroundedness"
  (lines 1050–1315); DEVIATIONS.md "Schema normalization layer"
  for tokenisation rationale.
* **Tables/figures.** No new figures; cites worked example inline.

### 3.3 SemanticCoherence (~1.5 pages)

* **Headline claim.** SC measures whether causal-link directions
  in the explanation chain match the ontology's propagation
  table at the fault-class level. Mitigation links are excluded
  to prevent the metric collapsing to "FCP wins by emitting
  Recommendation atoms."
* **Content.**
  * Formal definition (variant 4): per-link typicality lookup
    from `DiagnosticKB.has_propagation_to`, link weight scaled
    by propagation strength.
  * `excluded_mitigation_links` denominator adjustment.
  * Why variant 4 was chosen over v1/v2/v3 (cite the v3
    investigation in findings.md).
  * Worked example: an FCP link `(latency anomaly) → (CPU
    saturation)` scores coherent; a hypothetical link
    `(disk loss) → (CPU saturation)` scores incoherent.
* **Evidence.** findings.md "Phase 2 Week 2: SemanticCoherence"
  (lines 1316–1567) and "v3: SC alarm investigation"
  (1568–1820) for the variant-4 justification.
* **Tables/figures.** No new figures; cite the v3-to-v4
  redesign as a paragraph.

### 3.4 ExplanationCompleteness (~1 page)

* **Headline claim.** EC asks the operator-actionable three:
  *what kind of fault*, *which service*, *what mitigation*.
  Aggregate is fraction-present, taking one of four values
  `{0, 1/3, 2/3, 1}`.
* **Content.**
  * Three binary category detectors (root cause, affected
    component, mitigation).
  * Strict DiagnosticKB-vocabulary threshold for cause; service-
    name whole-token text rule for component; Recommendation
    URI / label match for mitigation.
  * Why the strict reading is preferred over a permissive one
    (auditability, vocabulary conformance).
  * Worked example: FCP scores 3/3 on a cpu case; DejaVu scores
    1/3 (component only, because its `"cpu"` text doesn't
    cover `"CPU Saturation"` at 70 %).
* **Evidence.** findings.md "Phase 2 Week 3: ExplanationCompleteness"
  (1821–2198); DEVIATIONS.md "ExplanationCompleteness metric"
  for the strict-threshold rationale.

### 3.5 ConfidenceCalibration (~1 page)

* **Headline claim.** CC is ECE — aggregate, not per-case, and
  the only metric where lower is better. The aggregate-only
  contract is a deliberate departure from SG / SC / EC.
* **Content.**
  * Standard ECE definition over `n_bins=10` equal-width
    buckets. Why aggregate is mathematically necessary.
  * Reliability diagram structure for diagnostic visualisation.
  * Per-case proxy `|confidence − target|` for Spearman
    correlation work — explicitly *not* equivalent to ECE.
  * BARO `peak_confidence` routing rule (cross-method scale
    normalisation), citing DEVIATIONS.md.
* **Evidence.** findings.md "Phase 2 Week 4: ConfidenceCalibration"
  (2199–2706); DEVIATIONS.md "ConfidenceCalibration metric"
  for the routing rule.
* **Tables/figures.** Inline reliability-diagram sketch (not a
  full figure — a small table of 5 example bins).

### 3.6 Properties of the Framework (~0.5 pages)

* **Headline claim.** The four metrics are polynomial-time
  computable, no LLM judge, no per-case manual rating,
  reproducible from public code + ontology + benchmark.
  Method-family agnostic.
* **Content.**
  * Brief property list (computability, reproducibility,
    open-source).
  * Threats summary (one-paragraph forward-reference to §5.3):
    ontology coverage as bottleneck, threshold-tuning surface,
    aggregate-vs-per-case asymmetry of ECE.
* **Evidence.** Implicit (references prior subsections); no new
  empirical content here.

---

## Section 4 — Empirical Study (~9 pages)

### 4.1 Experimental Setup (~1 page)

* **Headline claim.** Three RCAEval RE1 systems (OB, SS, TT)
  cover 12 / 15 / 64 services and 2,625 (case, method) pairs.
  Evaluation runs under the inject-time-clean contract
  (no method reads `ground_truth.inject_time`).
* **Content.**
  * System table: services, GT vocabulary, fault distribution,
    sampling rate.
  * Inject-time-clean protocol (one paragraph, cite
    `evaluation/methods/_protocol.py`).
  * Schema normalizer pipeline: `simple_data.csv` priority,
    `_latency-50` aliasing, per-service `latency_source` tag.
    Justify as benchmark adaptation, not method modification.
* **Evidence.** DEVIATIONS.md "Schema normalization layer" and
  "RE1-SS / RE1-TT latency alias"; findings.md "multi-system
  extension" §1 per-system tables.
* **Tables/figures.** Table 4 (small): system characteristics
  (services / faults / sample-rate / latency-source).

### 4.2 Per-System Headline Results (~2 pages)

* **Headline claim.** No method dominates all four semantic
  metrics + AC@1. DejaVu wins AC@1 + ECE on every system;
  FCP wins SG / SC / EC on every system; the six others
  cluster at the semantic-metric floor.
* **Content.**
  * Three per-system headline tables (Tables 1a, 1b, 1c).
  * 6–8 sentences of cross-system commentary on the
    FCP-vs-rest pattern.
  * Note FCP's AC@1 trajectory 0.400 / 0.160 / 0.008 and
    forward-reference §4.5 (the FCP case study).
* **Evidence.** findings.md "Phase 2 multi-system extension" §1
  (lines 2810–2904); `results/phase2_integration_headline_*.csv`.
* **Tables/figures.** Tables 1a, 1b, 1c (per-system headlines)
  here.

### 4.3 Cross-Metric Correlation Analysis (~1.5 pages)

* **Headline claim.** AC@1 is weakly correlated with each
  semantic metric overall (|ρ| ≤ 0.19). SG / SC / EC form a
  "structural-quality triple" (pairwise ρ 0.47–0.72). ECE is
  essentially uncorrelated with everything (|ρ| ≤ 0.04 with
  SG / SC / EC).
* **Content.**
  * Spearman correlation matrix (Table 2) over all 875 OB
    pairs (the original Week 5 matrix; mention that multi-
    system extension's 2,625-pair matrix moves these by
    < 0.05).
  * The four scatter plots (Figures 3–6) interpreted together.
  * Ranking-vs-explanation two-group division (DejaVu /
    MR / CR / Micro / BARO cluster on AC@1 ∈ [0.54, 0.70]
    with semantic-floor scores; FCP / yRCA on lower AC@1 with
    non-zero semantic scores).
* **Evidence.** findings.md "Phase 2 Week 5: Integration" §3
  (lines 2768–2799); `results/phase2_correlation_matrices.csv`.
* **Tables/figures.** Table 2 (correlation matrix), Figures 3–6
  (scatter plots).

### 4.4 Method Family Profiles (~2 pages)

* **Headline claim.** Each method's behaviour on the four-axis
  evaluation is consistent with its design philosophy. Five
  ranking-optimized methods (supervised, probabilistic, causal,
  graph-walk × 2) cluster on semantic-floor; two
  explanation-optimized methods (rule-based × 2) trade
  ranking for explanation grounding.
* **Content.**
  * One-paragraph narrative per method (7 paragraphs ≈ 1.4
    pages). For each: design philosophy → AC@1 across systems
    → SG / SC / EC profile → ECE / calibration behaviour →
    Phase-1 robustness axes (random-onset, edge-shift) →
    distinguishing finding.
  * Universal edge fragility paragraph (a Phase-1 finding that
    holds across all 7 methods on all 3 systems): no method's
    AC@1 survives an onset shift to the window edge.
  * DejaVu binary-regime calibration (cpu/disk/mem ≈ 0,
    delay/loss ≈ 0.27) — cross-system stable.
  * BARO BOCPD flatness — cross-system stable across all 3
    systems.
* **Evidence.** findings.md per-method baselines (lines 11–894)
  for Phase 1 axes; "Phase 2 Week 4 §6" for DejaVu binary
  regime and BARO flatness; "multi-system extension §4–5" for
  cross-system stability.
* **Tables/figures.** Table 3 (per-method characterisation
  summary: design philosophy / AC@1-OB-SS-TT / SG-SC-EC /
  ECE / edge-shift survival / distinguishing finding).

### 4.5 Case Study: FODA-FCP on RE1-TT (~1.5 pages)

* **Headline claim.** FCP on TT achieves SG = 1.000 / EC = 0.789
  / ECE = 0.219 with AC@1 = 0.008 (below chance 1/64 ≈ 0.016).
  This is the single strongest empirical evidence for Paper 6's
  thesis: a method can be ontology-grounded, structurally
  complete, and reasonably calibrated while having essentially
  zero ranking accuracy.
* **Content.**
  * Open with the four-tuple (SG, SC, EC, ECE) + AC@1 + chance
    baseline.
  * Trace the Noisy-OR saturation mechanism (Diagnostic C):
    64 services × ~10–20 neighbors with H ≥ 0.5 → 30–64 services
    tied at C = 1.0 / 0.0; alphabetical tiebreaker dominates.
  * Cite the math: ``C(s) = 1 − ∏ (1 − H(n) × edge_weight(n, s))``.
  * Hypotheses ruled out (Diagnostic A: 43 distinct top-1s, not
    a fixed bias; Diagnostic B: TT z's 10× OB, opposite of
    threshold-mismatch hypothesis).
  * Frame as evidence that the four dimensions are independent
    in the extreme. Explicitly state: this is an FCP
    algorithmic limitation, NOT a framework failure.
  * Figure 7: side-by-side canonical explanation chains for
    FCP (impeccable structure, wrong service) and yRCA
    (sparser, also wrong) on the same TT case.
* **Evidence.** findings.md "multi-system extension §3" (lines
  2903–3008); `paper/artifacts/foda_fcp_explanation_samples.json`
  + `yrca_explanation_samples.json` for Figure 7.
* **Tables/figures.** Figure 7 (FCP vs yRCA explanation
  side-by-side).

### 4.6 Methodological Findings Beyond Ranking (~1 page)

* **Headline claim.** Aggregate AC@1 alone cannot characterize
  RCA method value. Three cross-cutting findings: (a)
  ranking-vs-explanation independence, (b) universal edge
  fragility, (c) cross-system stability differs across methods
  in informative ways.
* **Content.**
  * Synthesis: ranking accuracy and explanation quality are
    weakly correlated overall — the structural-quality triple
    (SG, SC, EC) is independent of AC@1 at |ρ| ≤ 0.19.
  * Universal edge fragility: across 7 methods × 3 systems,
    AC@1 drops 30–80 pp under onset-shift to the window edge
    (the band-edge diagnostic from Phase 1 generalises).
  * Cross-system stability: methods with consistent
    cross-system AC@1 range (DejaVu 0.152, Micro 0.192) vs.
    those with system-dependent collapse (FCP 0.392, yRCA
    0.224).
* **Evidence.** findings.md "Cross-method finding (FINAL, all
  7 methods)" (lines 895–1049); "Phase 2 Week 5: Integration"
  §3 four-bullet pattern (2778–2798); "multi-system extension"
  §2 stability table (2873–2904) and §5 universal patterns
  (2931–3008).
* **Tables/figures.** Optional Figure 8 (cross-system AC@1
  heatmap, 7×3 grid). Not required if Tables 1a/b/c carry it.

---

## Section 5 — Discussion (~3 pages)

### 5.1 Implications for RCA Method Design (~1 page)

* **Headline claim.** The four-axis evaluation surfaces two
  legitimate design philosophies — ranking-optimised
  (DejaVu, BARO, CR, MR, Micro) vs explanation-optimised
  (FCP, yRCA) — that single-axis evaluation conflates as
  "good vs bad."
* **Content.**
  * Ranking-optimised methods: report AC@1 + S(M) + ECE.
    They give an operator a candidate to act on but not
    a justification.
  * Explanation-optimised methods: report SG + SC + EC +
    AC@1. They give an operator a justification that may
    or may not be deployable depending on AC@1.
  * Four-axis characterisation gives designers explicit
    targets to push on (e.g. "improve AC@1 without sacrificing
    SG"), and gives operators an honest characterisation of
    the trade-off.
* **Evidence.** findings.md "Phase 2 Week 5" structural-
  division paragraph (2796–2799); "multi-system extension §5"
  universal patterns.

### 5.2 Implications for Benchmark Design (~0.5 pages)

* **Headline claim.** RCAEval RE1 (and similar benchmarks)
  reward ranking-optimised methods exclusively. Offset
  robustness and explanation-quality dimensions should be
  evaluation-protocol standards, not extensions.
* **Content.**
  * Current benchmarks: GT is a service name; methods score
    by exact match. No reward for ontology grounding, link
    coherence, mitigation suggestions, or confidence
    calibration.
  * Phase-1 finding: methods that rank well under the central
    inject offset collapse on edge offsets. Inject-time
    randomisation should be standard.
  * Phase-2 finding: SG / SC / EC / ECE add 4 axes of
    information at < 30 min compute per (method, system).
* **Evidence.** findings.md "universal edge fragility" cross-
  method finding (lines 405–608); per-method robustness axes.

### 5.3 Threats to Validity (~1 page)

* **Headline claim.** Three threat categories: internal
  (schema / ontology / threshold choices), external (single
  benchmark family + author-method), construct (the four
  metrics don't exhaust operator-grade quality).
* **Content.**
  * Internal threats:
    - Schema choice (`simple_data.csv` priority on SS/TT;
      `_latency-50` aliasing) — cite DEVIATIONS.md.
    - Ontology coverage (DiagnosticKB has 12 fault
      prototypes + Mitigation hierarchy; methods producing
      out-of-vocabulary content score SG = 0 by design).
    - Threshold tuning knobs (SG coverage = 0.7; SC variant
      4 design; EC strict cause-detection; ECE `n_bins` = 10;
      BARO peak_confidence routing). Each documented in
      DEVIATIONS.md.
  * External threats:
    - Single benchmark family (all RCAEval RE1; no real-world
      production traces).
    - FCP is our own method (Paper 6 reports its strengths
      and limitations transparently; the case study in §4.5
      is the cleanest evidence of honesty).
    - No human-operator study — operator-grade quality is
      proxied by SG / SC / EC, not directly measured.
  * Construct threats:
    - SG / SC / EC measure structural properties; an
      explanation that grounds in DiagnosticKB but is
      operator-unhelpful is unmeasured.
    - ECE measures self-assessment alignment but not whether
      the absolute confidence value is actionable.
* **Evidence.** DEVIATIONS.md (full document); findings.md
  Phase-1 cross-method findings.

### 5.4 Limitations and Future Work (~0.5 pages)

* **Headline claim.** Three concrete limitations + a Paper 7
  pointer.
* **Content.**
  * RCAEval scope (one benchmark family, three systems);
    extension to LEMMA-RCA, real production traces is future
    work.
  * No human-operator validation of SG / SC / EC.
  * FCP's Noisy-OR saturation on dense graphs is an
    algorithmic limitation; Paper 7 (FODA system paper) will
    address it via (a) damping-aware propagation,
    (b) H-based tie-breaking, (c) confidence-conserving
    aggregators.
* **Evidence.** findings.md "multi-system extension §3"
  Implication-for-future-work paragraph (3000–3008).

---

## Section 6 — Conclusion (~1 page)

### 6.1 Summary of Contributions (~0.5 pages)

* **Headline claim.** Three contributions: (a) the four-axis
  semantic-quality evaluation framework, (b) the 7-method
  × 3-system × 2,625-pair empirical study, (c) the
  ranking-vs-explanation independence finding (concretely
  evidenced by FCP-on-TT).
* **Content.** One paragraph per contribution.

### 6.2 Future Work (~0.5 pages)

* **Headline claim.** Three directions: (a) benchmark
  expansion, (b) operator study, (c) Paper 7 FCP redesign.
* **Content.** One paragraph per direction. End with a
  one-sentence thesis restatement.

---

## Figure / Table inventory

| # | Type | Title (working) | Subsection | Source / status |
|---|---|---|---|---|
| 1 | Figure | Framework conceptual diagram (atoms / links / metrics layered) | 3.1 | **NEW** — needs drawing. Source: dataclass shapes in `evaluation/extraction/canonical_explanation.py`. |
| 2 | Figure | Canonical explanation form — worked FCP example | 3.1 | **NEW** — needs drawing. Source data: `paper/artifacts/foda_fcp_explanation_samples.json`. |
| 3 | Figure | AC@1 vs SG scatter | 4.3 | **Exists** at `paper/artifacts/scatter_ac1_vs_sg.png`. |
| 4 | Figure | AC@1 vs SC scatter | 4.3 | **Exists** at `paper/artifacts/scatter_ac1_vs_sc.png`. |
| 5 | Figure | AC@1 vs EC scatter | 4.3 | **Exists** at `paper/artifacts/scatter_ac1_vs_ec.png`. |
| 6 | Figure | AC@1 vs ECE proxy scatter | 4.3 | **Exists** at `paper/artifacts/scatter_ac1_vs_ece_proxy.png`. |
| 7 | Figure | FCP vs yRCA canonical chain side-by-side on a TT case | 4.5 | **NEW** — needs drawing. Source: `paper/artifacts/foda_fcp_explanation_samples.json` + `yrca_explanation_samples.json`. |
| 8 | Figure (optional) | Cross-system AC@1 heatmap (7 methods × 3 systems) | 4.6 | **NEW** — needs drawing. Source: `results/phase2_cross_system_comparison.csv`. |
| 1a | Table | Per-system headline RE1-OB (7 methods × AC@1+SG+SC+EC+ECE) | 4.2 | **Exists** at `results/phase2_integration_headline_re1-ob.csv`. |
| 1b | Table | Per-system headline RE1-SS | 4.2 | **Exists** at `results/phase2_integration_headline_re1-ss.csv`. |
| 1c | Table | Per-system headline RE1-TT | 4.2 | **Exists** at `results/phase2_integration_headline_re1-tt.csv`. |
| 2 | Table | 5×5 Spearman correlation matrix (AC@1 / SG / SC / EC / ECE_proxy) | 4.3 | **Exists** at `results/phase2_correlation_matrices.csv` (overall row, n=875 OB). |
| 3 | Table | Per-method characterisation summary (design / AC@1 / SG / SC / EC / ECE / edge-shift / finding) | 4.4 | **NEW** — needs assembly. Source: findings.md per-method baselines + Phase-2 results. |
| 4 | Table | System characteristics (services / faults / sample rate / latency-source mix) | 4.1 | **NEW** — small. Source: findings.md multi-system §1 + DEVIATIONS.md latency alias. |

---

## Dependency map

```
3.1 ─┬─→ 3.2 ─→ 3.3 ─→ 3.4 ─→ 3.5 ─→ 3.6
     │                                  │
     └──────────────→ 4.1 ───────────────┘
                       │
                       ▼
                      4.2 ─→ 4.3 ─→ 4.4 ─→ 4.5
                                     │
                                     ▼
                                    4.6
                                     │
       ┌─────────────────────────────┘
       ▼
      5.1 ─→ 5.2 ─→ 5.3 ─→ 5.4
                                │
                                ▼
                               6.1 ─→ 6.2
```

* **3.1 must precede 3.2–3.5** — they all reference the
  CanonicalExplanation substrate.
* **3.6 depends on 3.2–3.5** — summarises shared properties.
* **4.1 depends on §3** — references the framework definitions.
* **4.2 must precede 4.3–4.6** — establishes the per-system
  numbers everything else interprets.
* **4.5 depends on 4.4** — the FCP case study expands on the
  per-method profile.
* **4.6 depends on 4.3 + 4.4** — synthesises cross-metric and
  cross-method findings.
* **5.x can be drafted in parallel after §4** but 5.3 (Threats)
  needs §4.1 (setup details) anchored first.
* **§6 last** — summarises everything.

---

## Recommended drafting order

Group by cognitive coherence, not by section number.

1. **Setup pair** — 4.1 (Setup) + 3.1 (Substrate). 4.1 grounds
   what's being evaluated; 3.1 grounds the framework on the
   same evidence. Drafting them together keeps the
   benchmark-vs-framework boundary clear. **~2 sessions.**
2. **Metric quartet** — 3.2 / 3.3 / 3.4 / 3.5. Best drafted
   in one or two sessions consecutively; the four metrics
   share a contract structure and the prose echoes itself.
   **~3 sessions.** (1.5 metrics per session.)
3. **Framework closer** — 3.6. Short, depends on the quartet.
   **~0.5 session.**
4. **Results spine** — 4.2 (Per-system) + 4.3 (Correlations).
   The empirical core. **~2 sessions.**
5. **Profiles + edge fragility** — 4.4. Longest empirical
   subsection; one paragraph per method × 7. **~2 sessions.**
6. **FCP case study** — 4.5. The single most important
   subsection in the paper. Needs careful framing per the
   diagnostic-grounded findings.md §3. **~2 sessions.**
7. **Synthesis** — 4.6. **~1 session.**
8. **Discussion** — 5.1 + 5.2 + 5.4. **~2 sessions.**
9. **Threats** — 5.3. Distinct cognitive task; do as one focused
   session. **~1 session.**
10. **Conclusion** — 6.1 + 6.2. **~0.5 session.**

**Total estimated drafting sessions: 16.**

(Above counts assume 1 page of polished prose per 1–1.5
sessions, with a session ≈ 1–2 hours of focused writing. Heavy
sections like 4.5 may stretch.)

---

## Figure-creation work (separate track from drafting)

* Figures 1, 2, 7 need to be drawn — recommend a single
  illustration session before drafting 3.1 / 4.5 starts in
  earnest. Tool: TikZ / matplotlib hand-drawn / draw.io
  exported to PDF.
* Figure 8 is optional; revisit after 4.6 first draft to see
  whether the section needs it.
* Figures 3–6 (scatters) exist but may need venue-specific
  re-styling (font sizes, axis labels).

---

## Notes for review

* Each subsection includes: headline, content bullets,
  evidence sources with findings.md line ranges, and any
  table/figure placement.
* Total body-prose budget allocation: §3 = 6 pages, §4 = 9
  pages, §5 = 3 pages, §6 = 1 page = 19 pages of body prose.
  Tables / figures occupy the remaining 6–11 pages.
* All evidence cited above exists in `findings.md` or
  `DEVIATIONS.md`; no subsection is unsupported.
