# Cold-Read Bundle v1 — FODA-FCP method paper (§3–§5)

Assembled 2026-08-11. Read as a reviewer would: sections in
order, all open markers left visible. Numbers trace to `results/` at commit
`d485957` (+ the uncommitted δ-sweep and fuzzy-variant runs) via
`RESULTS_PROVENANCE.md`. Pessimistic AC@1 convention throughout; δ = 0.85
as-shipped is the reported configuration everywhere.

**Not included by design:** §1, §2, §6′, §7 (undrafted); §6 operator study
(NO-GO for v1). REUSE/NEW provenance lives in `section5_reuse_new_summary.md`
and `content_map.md` — linked, not inlined, so the cold read sees the paper
rather than its construction log.

## Marker index (23 open; 12 triaged blocking)

Triage is the drafter's guess, offered for the cold read to overrule.
*Blocking* = the claim cannot go to a reviewer unresolved (unverified
mathematics, unfilled tables, uncited parameter provenance). *Cosmetic* =
wording or typesetting that does not affect a claim's validity.

| # | Section | Line | Type | Triage | Marker |
|---|---|---|---|---|---|
| 1 | §3 | 3 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY] |
| 2 | §3 | 29 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY: CQ list drafted from the ontology's actual query surface — confirm these were the design-time  |
| 3 | §3 | 35 | AUTHOR-VERIFY | **BLOCKING** | [AUTHOR-VERIFY: confirm the surrogate remains in the evaluated configuration and that the §5 results are repor |
| 4 | §3 | 73 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY: confirm no RCAEval-driven ontology edits occurred; the repo history suggests the propagation s |
| 5 | §4 | 3 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY] |
| 6 | §4 | 3 | NEW-MATH | **BLOCKING** | [NEW-MATH] |
| 7 | §4 | 15 | AUTHOR-VERIFY | **BLOCKING** | [AUTHOR-VERIFY: confirm the correlation-graph parameters to be quoted here — lag window, threshold — from the  |
| 8 | §4 | 39 | AUTHOR-VERIFY | **BLOCKING** | [AUTHOR-VERIFY: add the SLO sources/justification you used at calibration time] |
| 9 | §4 | 51 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY: this footnote is how the 16 (harness) / 20 (AICT) / "18" (stale javadoc) discrepancy is resolv |
| 10 | §4 | 71 | TODO | **cosmetic** | [TODO: typeset Algorithm 1 from the reference implementation's control flow at LaTeX conversion time.] |
| 11 | §4 | 81 | NEW-MATH | **BLOCKING** | [NEW-MATH: the W = 1 boundary case — the practical default — needs the careful statement: for W = 1, ρ = 1 − δ |
| 12 | §4 | 85 | NEW-MATH | **BLOCKING** | [NEW-MATH — the bound deferred as future work in the conference paper] |
| 13 | §4 | 91 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY: numbers recomputed from the AICT worked example; re-derive independently before submission.] |
| 14 | §4 | 97 | AUTHOR-VERIFY | **BLOCKING** | [AUTHOR-VERIFY: confirm the exact confidence formula to quote from the reference implementation — the adapter  |
| 15 | §4 | 105 | TODO | **cosmetic** | [TODO at drafting §5: insert the canonical explanation for RCAEval case re1-ob_adservice_cpu_3 — four atoms (F |
| 16 | §4 | 109 | TODO | **cosmetic** | [TODO at §5 drafting: add measured wall-clock per case on RE1-TT (64 services) from the harness logs, giving t |
| 17 | §5 | 5 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY] |
| 18 | §5 | 41 | TABLE | **BLOCKING** | [TABLE — one row per method: MonitorRank, MicroRCA, CausalRCA, BARO, DejaVu, yRCA, FODA-FCP × columns: native  |
| 19 | §5 | 49 | COMPRESSED DEFINITIONS | **BLOCKING** | [COMPRESSED DEFINITIONS — ~1 p, carried from the framework specification.] |
| 20 | §5 | 85 | TABLE | **BLOCKING** | [TABLE 1a — RE1-OB] |
| 21 | §5 | 87 | TABLE | **BLOCKING** | [TABLE 1b — RE1-SS] |
| 22 | §5 | 89 | TABLE | **BLOCKING** | [TABLE 1c — RE1-TT] |
| 23 | §5 | 204 | AUTHOR-VERIFY | **cosmetic** | [AUTHOR-VERIFY: confirm the 165 Fault→Fault links / 84 endorsed figures from the deviation log against the cur |

## Known structural gaps (not markers)

1. §5.3's adapter table is specified but unfilled — content exists in the
   repository deviation log.
2. §5.4's crisp metric definitions are compressed to a placeholder; the full
   formal definitions belong in the framework companion paper.
3. §5.5's Tables 1a–c are described in prose; typesetting from the committed
   CSVs with bootstrap CIs is pending.
4. Figures: architecture (§3.1), canonical-explanation example (§4.7),
   Algorithm 1 pseudocode (§4.4) — all pending redraw/typesetting.


---

# §3

# §3 The FODA Architecture and the DiagnosticKB Ontology

> DRAFT v0.1 — 2026-08-07 (header updated 2026-08-10). Citation placeholders `[REF:*]` map to the master bibliography at integration time. Per D6-revised (Option C): the AICT conference version is not cited — prose says "the preliminary conference version"; §1 carries the disclosure sentence. `[AUTHOR-VERIFY]` marks claims the author must confirm. Target length: ~4 pp.

The knowledge layer described in this section is a first-class component of the method. FODA-FCP's explanations are grounded in a curated diagnostic ontology, and the method's semantic-quality scores are consequences of that design decision. We therefore disclose the ontology's full structure, engineering method, and provenance here, before the algorithm (§4) and its evaluation (§5): a reader assessing the evaluation must know exactly what the method's knowledge base contains and how it came to contain it. Grounding-by-construction is a property of the method, and we state it as such; what the evaluation then measures is whether that property survives contact with a benchmark the ontology was not tuned to — and where it does not (§5.6), we say so.

## 3.1 Architecture overview

FODA (Fuzzy-Ontology-based Diagnostic Architecture) organizes microservice diagnosis into four cooperating layers (Fig. 2 — **redrawn from scratch for this paper; no reuse of prior artwork** [D8]):

1. **Telemetry and anomaly layer.** Per-service metrics (CPU, memory, latency, error rate, throughput) are consumed by an anomaly-detection ensemble (Isolation Forest + One-Class SVM) exposed as a service; its per-service anomaly signals feed the fuzzy engine. In the benchmark evaluation of §5 this layer is replaced by the RCAEval telemetry contract (§5.2), so that all compared methods read identical inputs.
2. **Fuzzy inference layer.** The FCP engine (§4) fuzzifies metric evidence, fires a Mamdani rule base to produce per-service local fault hypotheses with graded confidence H(s), and propagates confidence over the service dependency graph.
3. **Knowledge layer.** The DiagnosticKB ontology (this section) supplies the diagnostic vocabulary — fault prototypes, contributing factors, recommendations, and typed fault-propagation knowledge — via SPARQL SELECT queries executed once at startup and cached; the diagnostic path never blocks on the triple store [REF:Tbilisi].
4. **Explanation layer.** The explanation builder assembles the fired rules, the propagation path, and the ontology enrichments into an operator-facing explanation in which every diagnostic claim carries an ontology IRI (§4.7).

The architecture was introduced in preliminary form in our LNNS chapter [REF:Tbilisi], which treated the fuzzy engine as a black box and evaluated only the explanation-text layer on a 12-scenario synthetic benchmark. This paper opens the box: §4 specifies the engine; §5 evaluates the complete method on RCAEval.

## 3.2 DiagnosticKB: structure and engineering method

DiagnosticKB is an OWL 2 ontology (IRI `http://foda.com/ontology/diagnostic`, prefix `diag:`, version 1.0.0, pinned by commit hash in the artifact release — Appendix F). It contains:

- **12 classes:** `Anomaly`, `ContributingFactor`, `DiagnosticResult`, `Fault`, `MLModel`, `Metric`, `MicroService`, `Propagation`, `Recommendation`, `RootCause`, `Severity`, `Symptom`.
- **13 object properties:** `affectsService`, `causedBy`, `detectedBy`, `diagnosedAs`, `hasContributingFactor`, `hasDiagnosis`, `hasMetric`, `hasRecommendation`, `hasSeverity`, `hasSymptom`, `indicatesAnomaly`, `propagationSource`, `propagationTarget`.
- **13 data properties:** `anomalyScore`, `confidence`, `description`, `diagnosticId`, `fci` (fuzzy confidence index — §3.5), `importance`, `metricName`, `metricValue`, `modelName`, `predictionId`, `propagationStrength`, `serviceId`, `timestamp`.
- **58 named individuals:** 8 fault prototypes (§3.3), 16 ContributingFactor individuals, 8 Recommendation individuals, 22 Propagation individuals (§3.4), and 4 Severity levels (`Low`, `Medium`, `High`, `Critical`).

Two structural decisions deserve explicit statement. First, **DiagnosticKB contains no SWRL rules and is used without a DL reasoner in the diagnostic path**: the ontology is accessed by SPARQL SELECT retrieval only. Inference lives in the Mamdani engine (§4.3), not in the ontology; the ontology's job is authoritative vocabulary and curated relational knowledge. Second, the ontology is **crisp OWL 2**: fuzziness enters through the data property `fci` and through the fuzzy memberships the engine attaches to ontology-anchored claims (§3.5), not through a fuzzy-DL formalism. We discuss the trade-off in §3.5 and list fuzzy-OWL formalization as future work (§7).

**Engineering method.** The ontology was developed following the iterative competency-question methodology of Noy and McGuinness [REF:NoyMcGuinness]. The competency questions the current version answers include: *(CQ1)* what fault prototype does a given engine fault category denote? *(CQ2)* which contributing factors, with what importance, explain a given fault prototype? *(CQ3)* what remediation is recommended for a given fault prototype? *(CQ4)* does fault type A typically propagate to fault type B, and with what typicality? *(CQ5)* which metric evidences a given contributing factor? **[AUTHOR-VERIFY: CQ list drafted from the ontology's actual query surface — confirm these were the design-time questions, and add any that were considered and dropped.]** Curation drew on operational knowledge of common microservice failure modes and on the failure-pattern literature [REF:failure-pattern-surveys]; provenance and revision history are recorded in the public repository.

## 3.3 Fault prototypes, contributing factors, recommendations

The diagnostic core is a set of eight fault prototypes: `CpuSaturation`, `MemoryLeak`, `LatencySpike`, `NetworkCongestion`, `HighErrorRate`, `ResourceContention`, `ThroughputDegradation`, `DiskIoBottleneck`. Each prototype carries exactly two ContributingFactor individuals (e.g., for `ResourceContention`: `concurrent_request_count`, importance 0.85; `lock_wait_time`, importance 0.70), each with `metricName`, `importance` ∈ [0, 1], and a prose `description`; and exactly one Recommendation individual (`Rec_CpuSaturation`, …) holding the remediation text an operator receives.

The Mamdani engine emits six fault-category strings (§4.3). Five map one-to-one onto prototypes via the explanation builder's category map: CPU_SATURATION → `CpuSaturation`, LATENCY_ANOMALY → `LatencySpike`, MEMORY_PRESSURE → `MemoryLeak`, SERVICE_ERROR → `HighErrorRate`, RESOURCE_CONTENTION → `ResourceContention`. The sixth, CASCADING_FAILURE, is currently mapped to `ResourceContention` as a documented **semantic weakening**: a propagation-level phenomenon is surrogated by a node-local prototype, which can misread a propagated symptom as a local cause. We inherit this limitation from the architecture's current release, flag it in the explanation text, and list a dedicated `CascadingFailure` prototype as required future work [REF:Tbilisi]. **[AUTHOR-VERIFY: confirm the surrogate remains in the evaluated configuration and that the §5 results are reported with it in place.]**

Ontology enrichment is retrieved by one SPARQL SELECT per fault category at engine startup and cached immutably. The query template (rewritten here; variable names differ from the chapter listing [D8]):

```sparql
SELECT ?faultLabel ?adviceText ?evidenceMetric ?evidenceWeight ?evidenceNote
WHERE {
  ?fault    rdfs:label                 ?faultLabel ;
            diag:hasRecommendation     ?advice ;
            diag:hasContributingFactor ?evidence .
  ?advice   diag:description           ?adviceText .
  ?evidence diag:metricName            ?evidenceMetric ;
            diag:importance            ?evidenceWeight ;
            diag:description           ?evidenceNote .
}
ORDER BY DESC(?evidenceWeight)
```

## 3.4 The propagation model

To let the method (and, downstream, any explanation-quality metric) reason about *which fault types plausibly cause which*, DiagnosticKB reifies fault-to-fault propagation as 22 `Propagation` individuals, each a triple ⟨`propagationSource`, `propagationTarget`, `propagationStrength`⟩ over the 8 prototypes. Strengths take the deliberately coarse vocabulary {1.0, 0.5}: 12 individuals at 1.0 encode patterns that almost always co-occur with the source fault (dominated by resource faults propagating to performance-visible faults, e.g. CpuSaturation → LatencySpike), and 10 at 0.5 encode conditional patterns (e.g. MemoryLeak → CpuSaturation via swap thrashing). The remaining 42 of 64 ordered prototype pairs carry no individual — implicit strength 0.0. The coarse scale matches the distinctions operators actually make ("usually," "sometimes," "almost never") without overcommitting to false precision; transitive closure is deliberately not applied. The full table, with curation rationale and known omissions, is Appendix A.

## 3.5 Where the fuzziness lives

Because "fuzzy" in a title can decay into decoration, we state precisely which parts of FODA carry fuzzy semantics and which are crisp:

| Layer | Semantics |
|---|---|
| Metric evidence | **Fuzzy.** Trapezoidal/triangular membership functions map each metric onto linguistic terms (e.g. cpu_HIGH = trap(65, 85, 100, 100)); full parameter tables in §4.2/Appendix E. |
| Fault inference | **Fuzzy.** Mamdani rules fire with strength CF × min(antecedent memberships); per-service fault hypotheses carry graded confidence H(s) ∈ [0, 1] (§4.3). |
| Propagation | **Graded.** Damped Noisy-OR composes [0, 1] confidences over weighted edges (§4.4); ontology `propagationStrength` supplies graded typicality {0, 0.5, 1.0}. |
| Ontology vocabulary | **Crisp.** Classes, properties, and individuals are standard OWL 2; an atom either carries a `diag:` IRI or does not. |
| Diagnosis record | **Fuzzy-annotated.** `DiagnosticResult` carries `fci` (fuzzy confidence index), persisting the engine's graded confidence into the knowledge layer. |

The design principle: *fuzziness where the uncertainty is (evidence, inference, propagation), crispness where the shared vocabulary must be unambiguous (the ontology)*. A fuzzy-DL encoding of the whole KB is possible and listed as future work; the present split keeps the ontology editable by non-specialists and the reasoning auditable — every graded number in an explanation traces to a membership function, a rule certainty factor, or a curated propagation strength, never to an opaque score. This division of labor is exercised end-to-end in §5.4, where explanation-quality metrics consume the fuzzy memberships attached to ontology-anchored atoms.

## 3.6 What the knowledge layer commits the method to

Three consequences of this design frame the evaluation. (i) Every FCP explanation atom carries a resolvable `diag:` IRI, so ontology-groundedness is 1.0 *by construction* — reported in §5 as a design property, not a discovered result. (ii) The ontology's coverage (8 prototypes, 22 propagations) bounds what the method can express: failure modes outside the prototype set surface only via the closest prototype, and §5's benchmark faults were not used to extend the ontology **[AUTHOR-VERIFY: confirm no RCAEval-driven ontology edits occurred; the repo history suggests the propagation set predates the RCAEval work]**. (iii) The propagation table is the method's own account of plausible fault causality — so the evaluation can, and does (§5.8), check the method's emitted causal links against its own knowledge base, an internal-consistency audit few RCA methods can even undergo.


---

# §4

# §4 FCP: Fuzzy Confidence Propagation — Algorithm and Formal Analysis

> DRAFT v0.1 — 2026-08-07. `[REF:*]` = bibliography placeholders; Per D6-revised (Option C, 2026-08-10): the paper is self-contained — the AICT conference version is referenced in prose as "the preliminary conference version" with a §1 disclosure sentence, NOT cited; upgrade to a proceedings citation only if AICT is accepted before submission. `[AUTHOR-VERIFY]` = must be confirmed by the author; `[NEW-MATH]` = formal material newly derived for this paper and requiring author check before submission. Target length: ~5 pp.

**Framing note (2026-08-11).** This section presents two things with deliberately different status. The **fuzzy-ontology core** — the DiagnosticKB knowledge layer of §3, the Mamdani inference of §4.3, and the explanation generation of §4.7 — is the paper's contribution: it is what produces ontology-grounded, checkable explanations, and it is invariant under every parameter setting we test. The **propagation step** of §4.4 is presented as a *design hypothesis*: that composing local evidence over the dependency graph should improve attribution. §5.9 tests that hypothesis with a dose–response sweep and **falsifies it on this benchmark family** — the propagation as formulated costs both ranking accuracy and coherence, with the penalty growing with graph size. We keep the full mechanism description here, because a hypothesis worth falsifying is worth stating precisely, and because the sweep's interpretation depends on it.

*Reconciliation with the preliminary conference version.* That version reported the propagation as beneficial on a 12-scenario synthetic suite whose graphs carry at most a handful of services. Our sweep reproduces that regime and its residue: RE1-OB, the smallest system here at 12 services, is the only one with an interior optimum (δ = 0.1, AC@1 0.560 against 0.552 at the δ → 0 limit), i.e. a small amount of propagation still helps at that scale. The benefit is already gone by 15 services and inverts sharply by 64. The two results are consistent; the earlier one was measured where the effect is positive and small.

FCP (Fuzzy Confidence Propagation) is a deterministic, training-free RCA algorithm operating on per-service metric evidence and a weighted service dependency graph, with no acyclicity assumption. It runs in five phases: fuzzification (§4.2), Mamdani fault inference (§4.3), cycle-safe damped Noisy-OR propagation (§4.4), ranking (§4.6), and ontology-grounded explanation generation (§4.7). A preliminary 6-page version of the propagation algorithm is under review at IEEE AICT 2026 (disclosed in §1); this section is self-contained and extends that preliminary treatment with full membership-function specifications, a formal convergence analysis including a spectral local-rate bound (deferred as future work in the conference version), the calibrated-confidence design, and the explanation phase as a first-class component. Throughout, the configuration described is exactly the one evaluated in §5 (the reference implementation's default rule base); divergences between released configurations are footnoted.

## 4.1 Notation and problem setting

Let G = (V, E) be a weighted directed graph over services V, where an edge (s, t) ∈ E means s calls t, with weight w(s, t) ∈ [0, 1] interpreted as a conditional fault-propagation probability. We assume Σ_t w(s, t) ≤ W with W = 1 in practice. Cycles are permitted and expected: replicated services querying each other, worker–controller pipelines through schedulers, and service meshes with bidirectional health checks all defeat the DAG assumption most hierarchical RCA methods make. Each service s carries a vector of metric evidence; the algorithm produces a confidence C(s) ∈ [0, 1] per service, a ranked candidate list, and an explanation.

When no topology metadata ships with the telemetry (the RCAEval setting, §5.2), the dependency graph is inferred from lagged Pearson correlation between services' dominant anomaly features, following the same convention as MicroRCA and yRCA; the construction and its parameters are part of the adapter contract (§5.3) **[AUTHOR-VERIFY: confirm the correlation-graph parameters to be quoted here — lag window, threshold — from the adapter source]**.

## 4.2 Fuzzification

Each metric is mapped onto linguistic terms by trapezoidal trap(a, b, c, d) and triangular tri(a, b, c) membership functions. The reference implementation's calibration, stated here in full for the first time (the conference paper named only the MF families):

| Metric | Term | Membership function |
|---|---|---|
| CPU (%) | LOW | trap(0, 0, 30, 50) |
| | MEDIUM | tri(30, 55, 80) |
| | HIGH | trap(65, 85, 100, 100) |
| Latency (ms) | NORMAL | trap(0, 0, 80, 150) |
| | ELEVATED | tri(80, 250, 500) |
| | CRITICAL | trap(400, 600, ∞, ∞) |
| Memory (%) | LOW | trap(0, 0, 40, 60) |
| | MEDIUM | tri(40, 65, 85) |
| | HIGH | trap(75, 90, 100, 100) |
| Error rate | NONE | trap(0, 0, 0.005, 0.01) |
| | LOW | tri(0.005, 0.02, 0.05) |
| | ELEVATED | tri(0.04, 0.07, 0.12) |
| | HIGH | trap(0.10, 0.15, 1.0, 1.0) |
| Throughput (req/s) | LOW | trap(0, 0, 0.3·β, 0.6·β) |
| | NORMAL | trap(0.6·β, β, ∞, ∞) |

where β is the service's nominal throughput baseline. Thresholds are SLO-calibrated: the CRITICAL latency knee at 400–600 ms and the HIGH error-rate onset at 10–15% reflect common service-level objectives **[AUTHOR-VERIFY: add the SLO sources/justification you used at calibration time]**. Adjacent terms deliberately overlap (e.g., cpu MEDIUM and HIGH overlap on [65, 80]) so that borderline evidence fires multiple rules with graded strength rather than flipping between rules at a threshold.

**Benchmark adaptation.** Under the RCAEval contract the raw units above are unavailable in comparable form across systems; the evaluated port maps post-onset-vs-baseline z-scores onto the same linguistic terms, preserving the MF shapes and the meaning of LOW/MEDIUM/HIGH while replacing absolute thresholds with z-magnitudes. This is an adapter-level substitution, documented as such (§5.3), because the original thresholds were calibrated for a different telemetry pipeline.

## 4.3 Mamdani fault inference

Local fault hypotheses are produced by a Mamdani-style rule base [REF:Mamdani] of **16 expert rules (R01–R16) over six fault categories**: CPU_SATURATION (R01–R03), MEMORY_PRESSURE (R04–R06), SERVICE_ERROR (R07–R09), LATENCY_ANOMALY (R10–R11), CASCADING_FAILURE (R12–R14), RESOURCE_CONTENTION (R15–R16). Each rule r = (id, antecedents A_r, consequent category, CF_r) fires with strength

α_r(s) = CF_r · min_{a ∈ A_r} μ_a(s),          (1)

the certainty factor CF_r ∈ [0.65, 0.95] scaling the minimum antecedent membership. Per category, firing strengths aggregate by max; the dominant category's strength is the service's local confidence H(s) ∈ [0, 1], and the dominant category itself is the service's local fault hypothesis. Example rules: R01: IF cpu_HIGH ∧ latency_ELEVATED THEN CPU_SATURATION (CF 0.85); R14: IF cpu_HIGH ∧ memory_HIGH ∧ latency_CRITICAL THEN CASCADING_FAILURE (CF 0.95). The full base is Appendix B.

The rule base is externalized (YAML) and versioned. *Footnote:* the released engine additionally ships an extended 20-rule/8-category configuration (adding MEMORY_LEAK_TENDENCY and DOWNSTREAM_DEPENDENCY_SLOWDOWN rules R17–R20), loadable from the same file format; the preliminary conference version's FODA-12 experiments used that extended base. All results in §5 use the 16-rule default base, which is the configuration the reference implementation constructs when no external rule file is supplied. **[AUTHOR-VERIFY: this footnote is how the 16 (harness) / 20 (AICT) / "18" (stale javadoc) discrepancy is resolved on the record; the javadoc will be corrected in the artifact release.]**

## 4.4 Cycle-safe damped Noisy-OR propagation

A fault in service t propagates evidence to its callers. FCP aggregates upstream evidence by the Noisy-OR combinator [REF:Pearl1988], chosen because it is monotone, bounded in [0, 1], and order-independent:

P(s) = 1 − ∏_{t ∈ callees(s)} (1 − w(s, t) · C(t)).          (2)

Local and propagated evidence combine in the same Noisy-OR fashion, with damping factor δ ∈ (0, 1]:

**DAG pass (exact, reverse topological order):**
C_{k+1}(s) = (1 − δ) · C_k(s) + δ · [1 − ∏_u (1 − w(s, u) · C_k(u))].          (3)

**Jacobi iteration (cyclic graphs):**
C^{(k)}(s) = (1 − δ) · C^{(k−1)}(s) + δ · [1 − (1 − H(s)) · (1 − P^{(k)}(s))],          (4)

with P^{(k)} computed from C^{(k−1)} by (2), initialization C^{(0)}(v) = H(v), and termination when the sup-norm residual Δ_k = ‖C^{(k)} − C^{(k−1)}‖_∞ ≤ ε or a hard cap MAX_ITER is reached. Defaults: δ = 0.85, ε = 10⁻⁶, MAX_ITER = 100.

Routing is adaptive: the engine attempts a topological sort in O(|V| + |E|); on success it runs the exact damped pass, on failure (a cycle exists) it falls back to Jacobi iteration. Both formulations converge to the same fixed point on DAGs. The unified Noisy-OR semantics across two adaptively selected strategies is the algorithmic core.

**Pseudocode (Algorithm 1).** *(The conference paper gives the algorithm only as equations + a pipeline figure; the full pseudocode block — fuzzify → infer → route → propagate → rank — is written out here.)* **[TODO: typeset Algorithm 1 from the reference implementation's control flow at LaTeX conversion time.]**

## 4.5 Convergence analysis

The conference paper argued convergence informally; here the argument is made precise, and a local rate bound is added that explains the empirically observed fast convergence. Define the update operator T by the right-hand side of (4).

**Theorem 1 (Global contraction).** *For δ ∈ (0, 1] and Σ_t w(s, t) ≤ W for all s: for any confidence vectors C, C′,*
‖T(C) − T(C′)‖_∞ ≤ ρ · ‖C − C′‖_∞,  ρ = 1 − δ(1 − W).
*If W < 1 or δ < 1 with W ≤ 1 strictly feasible, T is a contraction on [0, 1]^V and, by the Banach fixed-point theorem, has a unique fixed point C\* to which the Jacobi iteration converges from any initialization.*

*Proof sketch.* |∂P(s)/∂C(t)| ≤ w(s, t) by differentiating (2) and bounding the product factor by 1; the mean-value theorem gives |P(s) − P′(s)| ≤ W · ‖C − C′‖_∞; substituting into (4) yields the stated Lipschitz constant. **[NEW-MATH: the W = 1 boundary case — the practical default — needs the careful statement: for W = 1, ρ = 1 − δ(1 − W) = 1 and T is only non-expansive; convergence then follows from the strict-contraction factor (1 − δ) + δ·L(s) with L(s) = (1 − H(s))·W_s < 1 whenever H(s) > 0 or W_s < 1 — i.e., Theorem 2's local argument, promoted to a global statement under the mild condition that every service has either nonzero local evidence or caller-weight sum < 1. AUTHOR-VERIFY this condition against the implementation: services with H(s) = 0 and full weight budget would need the damping-only argument of the conference paper.]**

**Corollary (Iteration bound).** N(ε) ≈ log ε / log ρ; with δ = 0.85 and worst-case effective ρ = 0.15 + 0.85·W_eff, ε = 10⁻⁶ is reached in ≈ 30 iterations for W_eff = 1 treated via the non-expansive argument. Empirically, cyclic benchmark scenarios converge in 12–22 iterations (preliminary conference version, FODA-12 suite; re-confirmed in the released implementation's tests).

**Theorem 2 (Local spectral rate) [NEW-MATH — the bound deferred as future work in the conference paper].** *Let J be the Jacobian of T at the fixed point C\*. Then*
J_{st} = (1 − δ)·𝟙[s = t] + δ·(1 − H(s)) · ∂P(s)/∂C(t)|_{C\*},  |∂P(s)/∂C(t)| ≤ w(s, t),
*so the asymptotic convergence rate is bounded by the spectral radius*
ρ_loc ≤ (1 − δ) + δ · max_s (1 − H(s)) · ρ(W̃),
*where W̃ is the |V|×|V| matrix of edge weights. Because ρ(W̃) ≤ W = 1 and the factor (1 − H(s)) shrinks wherever local evidence is strong, ρ_loc is strictly smaller than the global Lipschitz bound whenever any service carries evidence.*

*Worked example (from the conference paper, re-analyzed).* On the 3-cycle A→B→C→A with all w = 0.7, H = (0.6, 0.3, 0.2), δ = 0.85: the iteration converges in 14 steps to C\* = (0.7255, 0.5271, 0.5453) (asserted to 10 decimals by the reference implementation's unit test). The conference paper could only compare the empirical rate ≈ 0.43 against the global bound 0.745. Theorem 2 gives ρ_loc ≤ 0.15 + 0.85 · (1 − 0.2) · 0.7 = 0.626 — consistent with, and much closer to, the observed rate; the residual gap is the difference between max_s(1 − H(s)) and the evidence profile along the dominant eigenvector. **[AUTHOR-VERIFY: numbers recomputed from the AICT worked example; re-derive independently before submission.]**

## 4.6 Ranking and calibrated confidence

Services are ranked by C(s) descending; ties are broken by H(s) descending, then by service name ascending for determinism. Candidates below threshold 0.10 are dropped; the top-k (default k = 3) are reported. *(The tiebreak order matters at scale and is analyzed in §5; its interaction with Noisy-OR saturation on dense graphs is the subject of §5.6–5.7.)* **[NOTE-TO-AUTHOR: Paper 6 §4.5 described the tiebreak as alphabetical; the implementation breaks ties by H(s) first and has done so since the adapter's first commit — this section states the implemented behavior, and the Paper-6 text should be corrected at its Q2 revision.]**

The reported confidence is not the raw C(s): FCP reports a fuzzy-classification confidence derived from the dominant hypothesis's firing strength and the margin over runner-up candidates, mapped to [0, 1] **[AUTHOR-VERIFY: confirm the exact confidence formula to quote from the reference implementation — the adapter documentation describes a margin-based normalization ("clear winner ⇒ near 1; near-tie ⇒ lower")]**. This value is what §5.10's calibration analysis measures against empirical correctness: the design intent is that a well-formed fuzzy pipeline should produce *meaningfully graded* confidence — an intent the ECE results test, not assume.

## 4.7 Explanation generation: the reasoning is the explanation

The explanation phase emits no post-hoc rationalization; it serializes the diagnostic computation itself. For the top-ranked candidate the builder assembles: the fired rules with their firing strengths (from §4.3); the propagation path by backtracking the highest-confidence chain from the candidate through the dependency graph (from §4.4); and the ontology enrichment — fault prototype IRI, contributing factors with importance, recommendation — retrieved per §3.3.

In canonical form (atoms and links, the structure §5.4's metrics consume): one atom per implicated service, tagged with its fault-prototype IRI (e.g. `diag:CpuSaturation`) and carrying **two distinct graded channels**. The *membership* channel holds the Mamdani local confidence H(s) — the degree to which the rule base backs that atom's claim, in the Zadeh sense of §3.5, and independent of where the atom ranks. The *confidence-share* channel holds the atom's share of the reported head's propagated-confidence mass, which is ranking-derived. Keeping them separate matters because they diverge sharply in exactly the regime §5.6 analyses: under Noisy-OR saturation several services carry near-identical shares while their rule-base support ranges from 0.008 to 0.95. Only the membership channel is consumed by the membership-weighted metric variant of §5.4; link weights use the share. one Recommendation atom (e.g. `diag:Rec_CpuSaturation`) for the predicted root cause; `contributes_to` links from contributing-factor atoms to the fault atom, and a `suggests_mitigation` link from fault to recommendation. Every atom carries a resolvable IRI — the groundedness-by-construction property stated in §3.6. The operator-facing rendering presents six paragraphs — summary, contributing factors, recommended action (ontology-derived); symptoms, fired rules, causal path (engine-derived) — at O(1) per explanation after startup caching [REF:Tbilisi].

*Worked example.* **[TODO at drafting §5: insert the canonical explanation for RCAEval case re1-ob_adservice_cpu_3 — four atoms (Fault, two ContributingFactors, Recommendation), five typed links — as Figure 4, redrawn.]**

## 4.8 Complexity and runtime

Per case: fuzzification and rule firing are O(|V| · |R|); propagation is O(|V| + |E|) on DAGs and O(MAX_ITER · (|V| + |E|)) on cyclic graphs; explanation assembly is O(1) per candidate after startup enrichment caching (one SPARQL query per fault category at initialization). Measured overhead of ontology grounding: ≈ 9.5 ms one-time construction, +0.73 µs and +7.7 kB per explanation versus a template baseline (single-JVM microbenchmark; caveats in [REF:Tbilisi]). **[TODO at §5 drafting: add measured wall-clock per case on RE1-TT (64 services) from the harness logs, giving the journal-grade scalability number the conference paper lacked.]**


---

# §5

# §5 Benchmark Evaluation on RCAEval

> DRAFT v0.1 — 2026-08-10. Drafted subsections: **5.1, 5.2, 5.3, 5.5, 5.6, 5.8**.
> Pending inputs: **5.4** (crisp-vs-fuzzy run queued), **5.7** (ceiling recompute landed; awaiting ratification of the ε formulation), **5.9** (τ/B/δ ablations running), **5.10** (correlation re-treatment).
> All numbers trace to `results/` at commit `d485957` via `RESULTS_PROVENANCE.md`. Pessimistic tie convention throughout. `[REF:*]` = bibliography placeholders; `[AUTHOR-VERIFY]` = author must confirm.

## 5.1 Research questions

The evaluation asks six questions, each targeting a property the method claims or a limitation it must characterize honestly.

**RQ1 (ranking accuracy).** How does FODA-FCP's top-1 accuracy compare with six representative baselines spanning the ranking, causal, probabilistic, supervised-neural, and rule-based families, across service graphs spanning an order of magnitude in size?

**RQ2 (explanation quality).** Do the four semantic-quality dimensions — groundedness, coherence, completeness, calibration — separate methods that reason over a diagnostic ontology from those that do not, and where does FODA-FCP sit on each?

**RQ3 (scale behaviour and failure mechanism).** How does the method's ranking accuracy vary with service-graph size, and what mechanism accounts for the variation?

**RQ4 (mitigation headroom).** How much of the observed ranking failure is addressable by a ranking-side intervention that uses only quantities the method already computes?

**RQ5 (parameter sensitivity).** Are the reported findings stable under the framework's and the method's tuning knobs — the text-match threshold τ, the calibration bin count B, and the propagation damping factor δ?

**RQ6 (calibration).** Does the method's reported confidence track its empirical correctness, and how does its calibration profile compare with supervised and probabilistic baselines?

RQ1 and RQ2 are answered in §5.5, RQ3 in §5.6, RQ4 in §5.7, RQ5 in §5.9, and RQ6 in §5.10; §5.8 examines a question the framework makes available and that few RCA methods can even be asked — whether the method's own causal claims agree with its own knowledge base.

## 5.2 Experimental setup

**Benchmark systems.** We evaluate on three systems from RCAEval [REF:RCAEval], the current de facto standard benchmark for microservice RCA: Online Boutique (RE1-OB, 12 services), Sock Shop (RE1-SS, 15 services), and Train Ticket (RE1-TT, 64 services). The three span an order of magnitude in service-graph size, which is what makes the scale analysis of §5.6 possible at all. Each system supplies 125 fault-injection cases distributed evenly across five fault types (CPU, memory, disk, latency, packet loss), giving 375 cases per method and 2,625 method-case evaluations in total. Chance baselines for top-1 prediction are 1/12 ≈ 0.083, 1/15 ≈ 0.067, and 1/64 ≈ 0.016 respectively.

**Evaluation contract.** To isolate root-cause attribution from anomaly-onset detection, each case is presented as a fixed-length canonical-feature window and methods rank services for attribution. The injection timestamp is withheld from every method: the normalization layer positions the window using a per-case hash of the case identifier, placing the injection at a deterministic but method-opaque offset within the middle half of the window, and raises on any attempt to read the injection time. A static validator asserts, per method, that no code path reads ground-truth fields [REF:repo]. The contract is shift-invariant: perturbing the nominal injection time by ±300 s leaves every method's top-1 output unchanged.

**Schema normalization.** RCAEval's systems expose telemetry at differing granularities; we normalize to a canonical per-service feature set (CPU, memory, latency, error rate, traffic, disk, network) at 1 Hz. One adaptation is material and disclosed: RE1-SS and RE1-TT expose median and 90th-percentile latency but not mean, so we alias median latency to the canonical latency channel and record the substitution in case metadata. Median latency is a defensible qualitative proxy for response-time anomaly, though statistically distinct from the mean.

**Scoring convention.** Top-1 accuracy (AC@1) uses pessimistic tie handling: when several services share the top score, the ground truth is assigned the worst rank within that tied block. This matters because FODA-FCP produces fully tied rankings under two distinct conditions analysed in §5.6, and the alternative — crediting whichever tied service happens to sort first — would inflate its AC@1 by 0.048, 0.072, and 0.024 on RE1-OB, RE1-SS, and RE1-TT respectively, purely by alphabetical accident. The same convention supplies the correctness label for the calibration analysis, so that a single definition of "correct" runs through every number reported here.

## 5.3 Fair-extraction adapter contracts

Every method is scored on the same canonical explanation structure (§4.7), which requires translating each method's native output into atoms and causal links. This translation is where an evaluation of explanation quality can silently become unfair, and the criticism is well taken: scoring a ranking method at zero on ontology groundedness after extracting from it an explanation it never claimed to produce would measure a design choice rather than a quality. We therefore state the adapter contract explicitly and release every adapter.

**The contract.** An adapter may populate a canonical field if and only if the method's own output or its published description supplies the corresponding content. Adapters may reshape and rename; they may not invent. Concretely: an adapter may emit one atom per ranked service with the method's own score as the atom's membership, because every method produces exactly that; an adapter may not attach an ontology class to an atom unless the method itself consulted a knowledge base, because that class would be the adapter's inference and not the method's claim.

**What each adapter populates.** [TABLE — one row per method: MonitorRank, MicroRCA, CausalRCA, BARO, DejaVu, yRCA, FODA-FCP × columns: native output, atoms emitted, links emitted, ontology class source, confidence channel.] The pattern the table shows is that atom text is always populated; links are populated by the four methods whose native output is relational (BARO's change-point-to-service attributions, MicroRCA's lagged-correlation subgraph, yRCA's rule derivations, FCP's typed propagations); and ontology classes are populated only by the two methods that consult a knowledge base during diagnosis — FCP with DiagnosticKB IRIs and yRCA with its rule-derivation namespace. The five remaining methods leave the field null.

**Why null is the correct outcome, not a penalty.** A null ontology class records that the method's output contains no term drawn from any shared diagnostic vocabulary — a property of the method, reproducible by anyone who reads its output. The framework does not claim such methods are bad; it claims they are silent on a dimension that operators need. §5.5 reports ranking accuracy separately precisely so that this silence is not confused with poor performance.

**Documented deviations.** Every adapter's departures from its source publication are recorded per method in the repository's deviation log, including the two that affect comparability: DejaVu is supervised and retrained per system under a stratified five-fold split keyed by case identifier, and yRCA is natively log-based but is run here on the metrics-normalized contract shared by all methods. Both are flagged wherever their numbers appear.

## 5.4 Metrics, and what happens when fuzziness enters the measurement

The four semantic dimensions are computed as defined in the framework: SemanticGroundedness as the mean per-atom grounding score, SemanticCoherence as the mean per-link agreement with the ontology's propagation table, ExplanationCompleteness as the fraction of three operator-relevant categories covered, and calibration as expected calibration error over the method's reported confidences. [COMPRESSED DEFINITIONS — ~1 p, carried from the framework specification.] These are the *crisp* forms, and they remain this paper's canonical metrics: every number in §5.5 and beyond is crisp unless explicitly labelled otherwise.

This subsection asks a narrower question. A standing criticism of ontology-grounded fuzzy methods is that the fuzzy apparatus does no measurable work — that memberships are computed, reported, and then consumed by nothing. We test that directly by defining membership-weighted variants of two metrics and measuring how much they move.

**Definitions.** SG_fuzzy weights each atom's grounding score by the degree to which the method holds that atom: SG_fuzzy = Σ g(a)·μ(a) / Σ μ(a), reducing to crisp SG when all memberships are 1. SC_fuzzy weights each scored link by the product of its endpoints' memberships. Both are reported alongside, never instead of, their crisp forms.

**What μ must be, and a correction.** For FODA-FCP the membership channel carries the Mamdani local confidence H(s) — the degree to which the rule base backs an atom's claim (§4.7). This required a correction to the implementation: until it was audited for this paper, the atom's membership field carried a different quantity, the atom's share of the reported head's propagated-confidence mass, which is ranking-derived rather than inferential. The two decouple sharply under saturation — atoms with near-identical shares of 0.333 carry rule-base support anywhere from 0.008 to 0.95 — so the channels are now separate and only the Mamdani channel feeds the variants below. The correction is semantic: ranking, AC@1, SG, SC and EC are numerically unchanged, verified by regression.

**Measured effect (RE1-OB).** With genuine Mamdani memberships: FODA-FCP SG 1.000 → **0.744**, SC 0.266 → **0.236**; yRCA SG 0.267 → **0.253**. The five methods that produce no ontology-grounded content score 0.000 under both forms, because a grounding score of zero is annihilated by any weight.

**A pre-registered prediction, and its failure.** Before running the corrected variant we recorded the expectation that H-weighting would differ substantially from the earlier share-weighting, because propagation-inflated atoms — high confidence share, near-zero rule support — would be heavily discounted. We also recorded the failure condition: if the H-weighted value landed at or above the share-weighted one, the two quantities would be more correlated in aggregate than the individual traces suggested, and the conclusion would need rethinking rather than restating. **The prediction failed.** Share-weighting gave 0.752 and membership-weighting gives 0.744 — a difference of 0.008. The decoupled atoms are real but too rare to move the mean.

**The decomposition, and why the result is forced.** The measured values are not merely dominated by a case-level effect — for this method they can be nothing else. Every FODA-FCP atom carries a resolvable ontology IRI, so every per-atom grounding score is g(a) = 1. Substituting into the definition, SG_fuzzy = Σ 1·μ(a) / Σ μ(a) = 1 whenever any membership is positive, and 0 when all are zero. **The membership-weighted variant is therefore algebraically identical to an indicator of whether the rule base fired at all**, and its mean is exactly the firing rate. The prediction failed because it could not have succeeded: no assignment of memberships, however graded, can move this metric for a method with uniform grounding.

The data confirm the identity to three decimals on all three systems, with silence counts of 32, 46 and 33 of 125:

| system | silence cases | (125 − silence)/125 | measured SG_fuzzy |
|---|---|---|---|
| RE1-OB | 32 | 0.744 | 0.744 |
| RE1-SS | 46 | 0.632 | 0.632 |
| RE1-TT | 33 | 0.736 | 0.736 |

RE1-SS's larger drop is not a stronger within-case effect but simply a higher silence rate — its rule base is quiet on 37 % of cases. The pattern is uniform, not system-dependent.

**What the variant can and cannot discriminate.** The identity holds only under uniform grounding. For a method whose atoms are *mixed* — some grounded, some not — membership weighting does real work, because it asks whether the grounded atoms are the ones the method actually believes. yRCA is that case, and its values move accordingly (0.267 → 0.253 on RE1-OB, 0.149 → 0.112 on RE1-SS). So the honest statement is a property of the *pairing*, not of fuzziness in general: **membership weighting discriminates only where grounding is partial, and FODA-FCP's grounding is total.** For FCP the fuzzy channel's imprint on this metric is a gate — whether the method had grounds to speak — rather than a gradient of how strongly, and the gate is what the number reports.

The atoms the variant was meant to penalise do exist: 36 of 465 on RE1-OB, spread over 26 cases and concentrated in memory (16) and CPU (12) faults, carry positive confidence share with zero rule support — propagation asserts them, the rule base disowns them. They are invisible to SG_fuzzy for the algebraic reason above, and they are the same population that the coherence variant, which weights *pairs* of endpoints and therefore escapes the identity, does register: SC 0.266 → 0.236 on RE1-OB and 0.158 → 0.172 on RE1-SS, moving in different directions on different systems because it is sensitive to which links survive the weighting.

**One phenomenon, three instruments — with one of them dependent by construction.** The silence class is the same population identified by the failure analysis of §5.6.2 and by the zero-signal cases in the damping sweep of §5.9, and the three readings must not be presented as mutually corroborating. The dependence is of two different kinds, and precision matters here. Between §5.6 and §5.9 it is empirical: both count the same cases, and their agreement reflects a shared population rather than independent confirmation. Between those and §5.4 it is **analytic**: for a total-grounding method SG_fuzzy is identically the firing indicator, so for FODA-FCP the membership-weighted score adds *no* evidence beyond the silence count — it is a re-expression of it, and would agree even if every membership value were replaced by any other positive number. For partial-grounding methods the situation differs: yRCA's atoms are a mix of grounded and ungrounded, the identity does not apply, and its membership-weighted score is a genuinely independent measurement of whether the atoms it grounds are the ones it believes.

**What this settles about the fuzzy claim.** Fuzziness is constitutive of the method rather than decorative: the Mamdani inference produces H, H gates whether the method speaks at all, and H breaks the saturation ties in the refinement of §5.7. What the measurement adds is that this contribution is now *measured* rather than asserted — and the measurement says the fuzzy structure's output-level imprint is a gate, not a grade. We report that as it stands. Searching for a different fuzzy metric that would show a larger effect would be a forking-paths exercise on the same data, and we did not conduct one.

## 5.5 Headline results

Tables 1a–c report all seven methods on all five metrics for the three systems; each AC@1 value carries a 95 % bootstrap percentile confidence interval (10,000 resamples, seed 42) over the 125 cases.

[TABLE 1a — RE1-OB] DejaVu 0.696, MonitorRank 0.632, CausalRCA 0.624, MicroRCA 0.624, BARO 0.536, FODA-FCP 0.400, yRCA 0.328 on AC@1; SG 1.000 (FCP), 0.267 (yRCA), 0.000 for the other five; SC 0.266 (FCP), 0.000 elsewhere; EC 0.824 (FCP), 0.333 for all others; ECE 0.051–0.534 with FCP at 0.119.

[TABLE 1b — RE1-SS] DejaVu 0.848, CausalRCA 0.656, MonitorRank 0.656, MicroRCA 0.648, BARO 0.584, yRCA 0.256, FODA-FCP 0.160; FCP SG 1.000, SC 0.158, EC 0.749, ECE 0.051.

[TABLE 1c — RE1-TT] DejaVu 0.744, MonitorRank 0.480, CausalRCA 0.472, MicroRCA 0.456, BARO 0.392, yRCA 0.104, FODA-FCP 0.008; FCP SG 1.000, SC 0.086, EC 0.789, ECE 0.243.

**Supervised and unsupervised methods are reported separately.** DejaVu is trained on labelled failures from the same system it is evaluated on; the remaining six methods, including ours, are training-free. DejaVu's lead is therefore reported as a distinct comparison class rather than as a ranking within one leaderboard, and its insensitivity to system size — 0.696, 0.848, 0.744 — is itself informative: a per-system-retrained classifier does not experience the scaling pressure that propagation-based methods do.

**Ranking accuracy.** Among the six unsupervised methods, FODA-FCP is mid-field on the smallest system (0.400, above yRCA and below the four metric-based methods) and falls with system size: 0.400 → 0.160 → 0.008. On RE1-TT the point estimate is **0.008, below the 1/64 ≈ 0.016 chance baseline (95 % CI [0.000, 0.024])**; we display the interval because it straddles chance, and rest the claim on the point estimate. The mechanism is analysed in §5.6. yRCA declines monotonically as well (0.328 → 0.256 → 0.104), while the four metric-based methods degrade only mildly.

**Explanation quality.** The semantic dimensions divide the field sharply. Five methods score exactly zero on groundedness and coherence and exactly 1/3 on completeness — the component-only floor, earned by naming a service and nothing else. Two methods score above the floor: yRCA, whose rule-derivation URIs partially match ontology labels (0.267 → 0.149 → 0.109 as its vocabulary grows harder to align on larger systems), and FODA-FCP, which achieves **SG = 1.000 on every case of every system**. That result is a design property, not a discovery: FCP annotates every atom with a DiagnosticKB IRI by construction (§3.6). What the evaluation does establish is that the property is *stable* — it survives a tenfold increase in graph size and a collapse in ranking accuracy, which is the empirical content of the claim that the two axes are independent.

**Completeness and calibration.** FCP's completeness (0.824 / 0.749 / 0.789) is high but not perfect: on the cases where its rule engine fires no recommendation, the mitigation category is unmet and the score drops to the component-only floor. Its calibration is competitive with the supervised baseline on the two smaller systems (0.119 and 0.051 against DejaVu's 0.099 and 0.111) and degrades on RE1-TT (0.243) — a degradation §5.6 shows is not incidental.

**The empty middle.** No method occupies an intermediate position: methods either commit to ontology grounding fully or do not engage with a diagnostic vocabulary at all. We return to what this implies for method design in §6′.1.

## 5.6 Failure-mechanism decomposition at scale

FODA-FCP's ranking accuracy on RE1-TT is 0.008: one correct attribution in 125 cases, below the chance baseline, while the same runs produce perfectly grounded and near-complete explanations. This section explains how both facts hold simultaneously. We instrumented all 125 RE1-TT cases, capturing every service's local Mamdani confidence H(s), its propagated confidence C(s), and the composition of the top-scoring block. The 124 failures separate into two mechanisms with sharply different signatures, plus a small residual.

### 5.6.1 Saturation — 87 failures (70 %)

In 87 cases the top score is exactly 1.000 and is shared by a block of between 2 and 30 services. The cause is the Noisy-OR combinator meeting a dense graph. Confidence at a service is one minus the product of complements over its active neighbours; on RE1-OB's 12-service graph a service has roughly three active neighbours and the product stays well away from zero, so C discriminates. On RE1-TT's 64-service graph a service has ten to twenty active neighbours with substantial memberships, the product collapses toward zero, and C saturates at 1.000 for many services at once. Under the pessimistic convention the ground truth then takes the worst rank in its block, and AC@1 records a failure.

The diagnostics rule out the two obvious alternative explanations. Systematic bias toward particular services would concentrate the failures on a few top-1 predictions; instead **43 distinct services appear as top-1 across the failures, the most frequent accounting for 25.8 %**. A mismatch between the Mamdani thresholds and the injected faults would show up as weak local evidence at the ground truth; instead **the ground truth's local confidence has median 0.950** across these cases. Local inference succeeds; propagation destroys the discrimination it produced.

Calibration supplies independent corroboration. Because saturated blocks carry the maximal confidence value, these are cases where the method is not merely wrong but *confidently* wrong — and the honest correctness label makes that visible: FCP's RE1-TT calibration error rises from 0.219 under naive scoring to **0.243** under the pessimistic convention, moving in the opposite direction from the two smaller systems, where it improves (0.167 → 0.119 and 0.123 → 0.051). Calibration and ranking degrade together at scale, and for the same reason.

### 5.6.2 Silence — 31 failures (25 %)

In 31 cases every one of the 64 services has C = 0.000, because **no Mamdani rule fires anywhere in the system**: the ground truth's own local confidence is 0.000 in all 31. These are not ranking failures at all. The method has no hypothesis to rank, and the fully tied output is the honest representation of that state. The pessimistic convention scores them as failures, which is correct — a method that says nothing has not identified the root cause.

The affected cases concentrate in fault types whose canonical-feature signature does not match any antecedent in the 16-rule base under the z-score fuzzification (§4.2), and they are spread across all five fault types rather than concentrated in one (memory 8, delay 7, disk 7, CPU 5, packet loss 4) — the coverage gap is general, not fault-type-specific. The remedy is rule-base coverage, not ranking machinery: no post-hoc reordering can legitimately manufacture a correct answer from a state in which the method has produced no evidence. We return to this in §7 as the most concrete item of future work.

### 5.6.3 Residual — 6 failures (5 %)

Six cases produce a unique top-1 at C = 1.000 with the ground truth outside the top block. These are genuine attribution errors: local inference fires, propagation discriminates, and the discrimination points at the wrong service — a correlation-induced topology whose edges do not match the true fault path.

### 5.6.4 What the decomposition establishes

Three conclusions follow. First, the below-chance result is not one phenomenon but three, and only the largest (70 %) is a propagation pathology; a quarter of it is the method correctly reporting that it has nothing to say. Second, any mitigation must be matched to a mechanism: §5.7 addresses saturation and can, by construction, do nothing for silence. Third, high semantic quality and low ranking accuracy are not in tension but are produced by the same run — the explanation of a saturated case is fully grounded and structurally complete, and it is grounded in a fault hypothesis that is locally correct; what fails is the attribution of that hypothesis to a service.

## 5.7 A mechanism-matched mitigation: local-H score refinement

**What ranking-side intervention cannot do.** Under the pessimistic convention of §5.2, top-1 accuracy is provably invariant to how a tied block is ordered: if k services share the top score, the ground truth is assigned rank k regardless of the ordering rule, so AC@1 = 0 whenever k > 1 and no within-block ordering — alphabetical, evidence-based, or otherwise — can change it. Any mitigation that hopes to move the metric must therefore act on the *score*, not on the order. This is not a peculiarity of our scoring choice; it is the reason the choice is the honest one, since a metric sensitive to within-block order would be rewarding an arbitrary convention.

**The refinement.** We define a variant of the ranking step that consults local evidence at the score level. Services are ordered lexicographically by the pair (C(s), H(s)) — propagated confidence first, local Mamdani confidence as the second key — and pessimistic scoring is applied to blocks tied on *both* components. Equivalently, this is the ε → 0 limit of the score perturbation C′(s) = C(s) − ε·(1 − H(s)) with ε smaller than any non-zero gap between distinct C values; we adopt the lexicographic form because it is exact, requires no constant to be chosen, and cannot be destabilised by floating-point noise (on RE1-TT the smallest non-zero C-gap is ≈ 10⁻¹², at the numerical resolution of the propagation itself). The refinement introduces no new information: H is already computed in §4.3 and already reported inside every explanation.

**Post-hoc disclosure.** This refinement was designed after inspecting the RE1-TT failure structure reported in §5.6, not before the evaluation. No held-out benchmark system was reserved for it, so we cannot claim independent validation. We therefore report it strictly as a characterized variant, evaluated on all three systems rather than on the failure system alone, and accompanied by the ablation of §5.9. **The as-shipped method's numbers remain the headline everywhere in this paper, including the abstract**; the refined variant is reported alongside, never in place of them.

**Headroom, and what bounds it.** The mechanism decomposition fixes an exact ceiling. Of the 87 saturation failures on RE1-TT, the ground truth lies inside the saturated block in 30. Of those 30, it is the strict unique maximum of local confidence within the block in **18**; in a further **8** it merely ties for the maximum, and strict handling — the honest choice, since a tie carries no evidential preference — leaves those unrescued. The ceiling is therefore 1 + 18 = **19 of 125, or AC@1 = 0.152**, where the leading 1 is the single case the as-shipped method already gets right (`ts-travel-service`, disk fault), disjoint from the 18. Any measured value above 0.152 would indicate an implementation error rather than a better method.

The remaining failures contribute nothing, for reasons that are structural rather than incidental. The 31 silence cases have **zero** headroom, confirmed two independent ways: every service has H = 0.000, so there is no local evidence to promote; and strict scoring rescues none of them, whereas the loose criterion would have spuriously "rescued" all 31 by treating a universal tie at zero as a satisfied maximum. The 6 residual failures also contribute nothing, since the ground truth lies outside the top block entirely. Mechanism (a) bounds the entire intervention.

**Measured effect.** Applied to all three systems, the refinement changes nothing on the two smaller ones and substantially improves the largest:

| System | As-shipped AC@1 | Refined AC@1 | Δ | cases gained / lost |
|---|---|---|---|---|
| RE1-OB | 0.400 | 0.400 | +0.000 | 0 / 0 |
| RE1-SS | 0.160 | 0.160 | +0.000 | 0 / 0 |
| RE1-TT | 0.008 | **0.144** | **+0.136** | 17 / 0 |

The result is bounded, mechanism-consistent, and costs nothing: the refinement realises 18 of the 19 cases its ceiling permits (0.144 against the 0.152 bound), and **loses no attribution on any system** — no case correct under the as-shipped ordering becomes incorrect.

**The null result on the two smaller systems is a successful prediction, and it is the answer to the tuning objection.** §5.6.1 characterises saturation as a dense-graph phenomenon: the Noisy-OR product collapses only when a service has many strongly-activated neighbours, which does not happen on 12- and 15-service graphs, where the ground truth is essentially never trapped inside a saturated block. A refinement targeted at that mechanism must therefore do nothing on RE1-OB and RE1-SS — and it does exactly nothing, to four decimal places, gaining and losing zero cases on both. This is the distinction between a mechanism-targeted intervention and a generic score adjustment: a generic adjustment would perturb every system, and a benchmark-tuned one would have been fitted where it was needed. The intervention's silence where the mechanism is absent is stronger evidence for its validity than its gain where the mechanism is present.

**Mechanism alignment, by fault type (RE1-TT, 25 cases each).**

| Fault | Correct, as-shipped | Correct, refined | Gained | Saturation failures | Silence failures |
|---|---|---|---|---|---|
| CPU | 0 | 8 | +8 | 18 | 5 |
| Disk | 1 | 7 | +6 | 15 | 7 |
| Delay | 0 | 1 | +1 | 17 | 7 |
| Packet loss | 0 | 1 | +1 | 20 | 4 |
| Memory | 0 | 1 | +1 | 17 | 8 |

The gains concentrate in CPU and disk faults, which together account for 14 of the 17 rescues, and the remaining three fault types move by a single case each. This is the mechanism analysis in tabular form: rescue requires the ground truth to be inside a saturated block *and* to carry strictly the highest local confidence there, which in turn requires the Mamdani rule base to have fired informatively on it — most reliably for CPU and disk signatures.

**A pre-commitment that did not fire.** Before measuring, we committed to reporting a materially unrealised ceiling as a finding in its own right: had the measured value fallen well short of 0.152, the gap would have indicated that local confidence is only weakly discriminative once propagation has saturated, and we would have reported that. It did not — the measurement reaches 18 of 19 admissible cases. We state the commitment because a mitigation section that reports only favourable outcomes is not evidence of a good mitigation, merely of selective reporting.

The single ceiling case not realised (`ts-auth-service_cpu_2`) is instructive about the formulation rather than the method: the ground truth's propagated confidence there differs from a competitor's by less than 10⁻¹², so which of the two ranks first is decided at the numerical resolution of the propagation itself. This is the concrete, measured instance of the fragility that motivated adopting the exact lexicographic form over an explicit ε — and, at one case in 125, a measurement of how much that choice is worth.

**Requalification in light of §5.9.** The damping sweep places this refinement precisely. It repairs the high-δ regime: `ac1_refined` departs from the as-shipped value only for δ ≥ 0.65, where saturated ties exist to break, and coincides with it exactly at δ ≤ 0.5 where they do not. The refinement is therefore a targeted repair for a configuration that §5.9 shows to be dominated in the first place — worth reporting because the shipped configuration is the evaluated one, but not the durable contribution. What endures is the loop: a mechanism analysis (§5.6) yielded a quantitative ceiling, an intervention was designed against that mechanism, its headroom was computed before measurement, and the measurement landed at 18 of 19 admissible cases with zero losses. That predict-then-verify cycle is reusable regardless of which damping setting a future deployment adopts.

**Interpretation regardless of outcome.** Even at its ceiling the refinement leaves FODA-FCP far below the baselines on RE1-TT ranking (0.152 against DejaVu's 0.744), so it does not alter the paper's characterization of the method: an explanation-optimised approach with a well-understood and only partially addressable ranking limitation on dense graphs. What the refinement does establish is that the limitation decomposes — a majority of it is a propagation-saturation artifact with a bounded, evidence-based remedy, and the remainder is a knowledge-coverage gap that ranking machinery cannot touch. The two deferred propagation-level remedies, density-aware damping and log-pool aggregation, together with the rule-coverage work implied by the silence mechanism, are the subject of §7.

## 5.9 Sensitivity: thresholds, bins, and the damping dose–response

Three parameters could in principle be carrying the results: the framework's text-match threshold τ, the calibration bin count B, and the method's damping factor δ. We sweep all three. Two are inert. The third produces this paper's most consequential measurement.

**Text-match threshold τ ∈ {0.5 … 0.9}.** For τ ∈ [0.6, 0.9] every reported value is stable to three decimals and no method ordering changes. At τ = 0.5 the two-group division collapses: the five ungrounded methods rise off the floor (MicroRCA 0.400, MonitorRank 0.387, CausalRCA 0.334, BARO 0.206, DejaVu 0.054 on groundedness), and MicroRCA and MonitorRank overtake yRCA, inverting the ordering. The cause is a vocabulary collision: at half-coverage a single shared token suffices, so an atom reading "cpu_user_pct z = 4.2" matches the label "CPU Saturation". The practical rule this yields — require whole-concept rather than single-token agreement, which for two-token labels means τ > 0.5 — is what the default τ = 0.7 implements, and it sits in the middle of the stable band rather than at its edge.

**Calibration bins B ∈ {5, 10, 15, 20}.** Fully robust: no ordering changes, and per-method calibration errors move by at most 0.019 (FODA-FCP 0.119 / 0.119 / 0.119 / 0.125 on RE1-OB; BARO identical at every B). B = 10 is reported as convention, not necessity.

**Damping δ ∈ {0.001 … 1.0}: the dose–response.** The propagation update is C ← (1 − δ)·C + δ·NoisyOR, so lower δ means heavier damping and less propagation influence; δ = 0.001 approximates ranking by local Mamdani confidence alone. Sweeping eleven values on all three systems, with all four metrics computed at each:

| δ | OB AC@1 | OB SC | SS AC@1 | SS SC | TT AC@1 | TT SC | TT EC |
|---|---|---|---|---|---|---|---|
| 0.001 | 0.552 | 0.398 | 0.408 | 0.302 | **0.464** | **0.372** | 0.835 |
| 0.100 | **0.560** | 0.400 | 0.408 | 0.294 | 0.376 | 0.282 | 0.835 |
| 0.200 | 0.544 | 0.396 | 0.408 | 0.296 | 0.216 | 0.212 | 0.824 |
| 0.500 | 0.480 | 0.304 | 0.256 | 0.210 | 0.064 | 0.084 | 0.784 |
| **0.850 (as-shipped)** | 0.400 | 0.266 | 0.160 | 0.158 | **0.008** | 0.086 | 0.789 |
| 1.000 | 0.344 | 0.234 | 0.064 | 0.144 | 0.000 | 0.172 | 0.827 |

Three findings, and one defence that failed.

*(i) Monotone dose–response, scaling with graph size.* Ranking accuracy improves as propagation influence is reduced, at essentially every step, on every system. The improvement from the shipped setting to the δ → 0 limit is **1.4× on RE1-OB (0.400 → 0.560), 2.6× on RE1-SS (0.160 → 0.408), and 58× on RE1-TT (0.008 → 0.464)**. The effect grows with service count, which is exactly the signature the saturation mechanism of §5.6.1 predicts: denser graphs give the Noisy-OR product more factors to collapse. Where §5.6 inferred the mechanism from one operating point, the sweep measures it as a continuous dose–response.

*(ii) At the δ → 0 limit the method re-enters the baseline band.* On RE1-TT, 0.464 places FODA-FCP above BARO (0.392) and within sampling distance of MicroRCA (0.456), CausalRCA (0.472) and MonitorRank (0.480), instead of below the 1/64 chance baseline. The method's ranking collapse at scale is therefore attributable to the propagation step specifically, not to the fuzzy-ontology approach: the same rule base, ontology, and explanations, with propagation switched off, rank competitively with the unsupervised field.

*(iii) The trade-off defence failed.* Before running the sweep we recorded the branch that would have to hold for the shipped configuration to be defensible: if damping bought ranking accuracy at the cost of explanation quality, δ = 0.85 would be a deliberate position on a trade-off curve. It does not. Coherence rises with the same damping that raises accuracy (RE1-TT 0.086 → 0.372, a 4.3× improvement), completeness rises or holds (0.789 → 0.835), and groundedness is invariant at 1.000 throughout. There is no trade-off to sit on: **propagation as currently formulated is dominated on this benchmark family** — it costs accuracy and coherence together.

**Why we nevertheless report δ = 0.85.** Selecting δ on the same benchmark that provides the evaluation would invalidate the evaluation; the sweep tells us where the optimum lies *on these systems*, which is precisely the knowledge a held-out selection is supposed to withhold. We therefore keep the shipped configuration as the reported method everywhere, including the abstract, and present low-δ settings as characterised variants under the same disclosure discipline as §5.7. Principled damping selection on held-out systems is the first item of future work (§7). The finding stands on its own as a recommendation to the field — for graphs beyond a few dozen services, this propagation formulation should default to off — but it is a finding about our method, not the configuration we evaluated.

## 5.8 Self-coherence: the method against its own knowledge base

FODA-FCP's semantic coherence is 0.266 on RE1-OB, 0.158 on RE1-SS, and 0.086 on RE1-TT. Coherence measures the fraction of a method's fault-to-fault causal links that match a propagation the ontology endorses; FCP is the only method in the study that emits such links at all, and these values say that most of the links it emits are **not** endorsed by the propagation table it ships with. Because the ontology is part of the method (§3), this is an internal inconsistency, and it deserves analysis rather than a footnote.

**Where the links come from.** FCP's causal links are induced by the correlation topology (§4.1), not by the ontology: an edge exists because two services' anomaly signals co-move with a lag, and the link inherits the fault types the Mamdani engine assigned to its endpoints. The propagation table, by contrast, encodes curated fault-type causality — which fault *kinds* typically produce which. The two disagree whenever a statistically real edge connects a pair of fault types the curator did not judge typical. Of the fault-to-fault links FCP emits on RE1-OB, roughly half match a curated propagation and half do not [AUTHOR-VERIFY: confirm the 165 Fault→Fault links / 84 endorsed figures from the deviation log against the current per-case data].

**Two readings, and why we prefer the second.** One reading is that the method is incoherent and should emit only ontology-endorsed links. That would raise coherence to 1.000 by construction and would make the metric uninformative — the method would be scored against a table it had been filtered through. The other reading, which we adopt, is that coherence here measures a genuine gap between *observed* propagation and *curated* propagation, and that the gap is diagnostic information: a persistently unendorsed edge type is either a curation omission or a spurious correlation. The declining trend across systems (0.266 → 0.086) then has a natural interpretation — denser graphs produce more correlation edges per fault, and the curated table's 22 propagations over 8 prototypes cover a shrinking fraction of them.

**Consequences for the framework and for the method.** For the framework: coherence as defined rewards methods whose causal claims are conservative, and a method that emits many links pays for each unendorsed one. For the method: the honest statement is that FCP's link structure is richer than its knowledge base can currently adjudicate, and the fix is ontology work — extending the propagation table, and distinguishing "not endorsed" from "contradicted" — not link suppression. Both are recorded in §7.

## 5.10 Calibration, and a correlation analysis redone

**Per-method calibration.** Expected calibration error separates the panel by confidence mechanism rather than by accuracy. DejaVu's supervised softmax is best-calibrated on the two smaller systems (0.099, 0.111); BARO is worst everywhere (0.534, 0.582, 0.390), reflecting a change-point posterior that is empirically flat — its band-normalised peak sits near 0.005 on every case, so its confidence channel carries almost no information; FODA-FCP is competitive on the smaller systems (0.119, 0.051) and degrades on RE1-TT (0.243) for the reason §5.6.1 identifies, saturated blocks carrying maximal confidence into wrong attributions.

**Aggregate calibration hides regime structure.** Per-fault breakdowns show DejaVu's aggregate 0.099 on RE1-OB is a population-weighted mean of near-zero error on CPU, disk and memory faults and moderate error on latency and packet-loss faults — two regimes, not one behaviour. CausalRCA shows the sharpest instance: its RE1-TT packet-loss error reaches roughly double its aggregate, as the PC algorithm produces noisier graphs on the 64-service system while the method's reported confidence does not track that noise. A single ECE number per method conceals this; per-fault reporting should be standard.

**The correlation analysis, redone.** Our earlier framework paper computed Spearman correlations between ranking accuracy and each semantic metric by pooling all 875 (method, case) pairs on RE1-OB, obtaining weak values — ρ(AC@1, SG) = −0.216, ρ(AC@1, SC) = +0.111, ρ(AC@1, EC) = −0.010 — and concluded that the axes are close to independent. That treatment is not defensible: the pairs are not independent observations, and the pooled coefficients are dominated by between-method structure. We therefore report the analysis within methods.

Doing so shows why the pooled numbers were uninformative. For five of the seven methods the semantic metrics are **constant across all 125 cases** — SG and SC are identically zero, EC identically 1/3 — so within-method correlation is undefined, and every bit of the pooled variation came from differences *between* methods rather than from any per-case relationship. Where the correlation is defined, it is much stronger than the pooled value suggested:

| method | system | ρ(AC@1, SC) | ρ(AC@1, EC) | ρ(AC@1, SG) |
|---|---|---|---|---|
| FODA-FCP | RE1-OB | **+0.593** | **+0.506** | undefined (SG ≡ 1) |
| FODA-FCP | RE1-SS | **+0.635** | +0.343 | undefined |
| FODA-FCP | RE1-TT | +0.197 | +0.069 | undefined |
| yRCA | RE1-OB | undefined (SC ≡ 0) | undefined (EC ≡ 1/3) | +0.422 |
| yRCA | RE1-SS | undefined | undefined | −0.456 |
| yRCA | RE1-TT | undefined | undefined | −0.062 |

**This reverses a conclusion.** Within FODA-FCP the cases it ranks correctly are substantially the cases whose explanations are more coherent and more complete — ρ ≈ +0.6 on the two smaller systems, weakening to +0.20 on RE1-TT where saturation flattens the coherence signal. Ranking accuracy and explanation quality are therefore *not* independent within a method that produces both; the appearance of independence in the pooled analysis was an artifact of averaging over a panel in which five methods contribute no semantic variation at all. The defensible statement is narrower and more useful than the original: the two axes are independent *across* methods — knowing a method's AC@1 tells you nothing about its explanation quality, which is the claim that motivates measuring both — while *within* an explanation-producing method they are positively coupled, plausibly because both degrade together when local inference is weak. yRCA's sign instability across systems (+0.42, −0.46, −0.06) is a caution against over-reading the second half of that statement from one method.

**Calibration correlations are mechanism artifacts.** The within-method correlation between correctness and per-case calibration error is strongly positive for BARO (+0.967 on RE1-OB) and strongly negative for DejaVu (−0.710) and CausalRCA (−0.839). These are not quality signals: with confidence pinned near zero, as BARO's is, a correct case is necessarily a high-error case, while a confident method inverts that arithmetic. FODA-FCP's moderate positive value (+0.505) says it is under-confident on the cases it gets right — a specific, actionable calibration defect rather than a general miscalibration.

---

## Drafting status

| Subsection | State |
|---|---|
| 5.1 Research questions | drafted |
| 5.2 Setup | drafted |
| 5.3 Adapter contracts | drafted (adapter table to be filled from the deviation log) |
| 5.4 Metrics + fuzzy variants | **pending run** |
| 5.5 Headline results | drafted (tables to be typeset from committed CSVs) |
| 5.6 Mechanism decomposition | drafted |
| 5.7 Mitigation | **pending ε-formulation ruling**; strict ceiling = 0.152 |
| 5.8 Self-coherence | drafted |
| 5.9 Sensitivity | **pending ablations** |
| 5.10 Calibration | pending |


---

# Appendices


---

## Appendix I — RE1-TT failure-mechanism decomposition

# RE1-TT Failure-Mechanism Decomposition (FODA-FCP, current head + pessimistic convention)

Generated 2026-08-10 from `fcp_tt_diagnostics` (FCP re-run over all 125 RE1-TT
cases, per-service C and H captured; classified CSV in session scratchpad,
to be promoted into results/ if quoted in the paper). Failure set = the
canonical pessimistic AC@1 = 0.008 (1 correct / 124 failures).

## Mechanism split of the 124 failures

| Mechanism | n | Share | Signature |
|---|---|---|---|
| (a) SATURATION | 87 | 70.2% | C ties at exactly 1.000, tie blocks of 2–30 services; ground-truth H median 0.950 (local detection succeeds, Noisy-OR washes it out) |
| (b) SILENCE | 31 | 25.0% | C = 0.000 for ALL 64 services (no Mamdani rule fires anywhere); ground-truth H = 0.000 in 31/31 |
| (d) discriminated-but-wrong | 6 | 4.8% | unique top-1 at C = 1.000, ground truth outside the block; gt H median 0.915 |

## Fingerprint confirmation (Paper 6 §4.5 claims, re-verified under head)

- 43 distinct top-1 services among the 124 failures ✓ (Paper 6: 43)
- Most-frequent failure top-1 = 25.8% ✓ (Paper 6: "26 percent")
- Ground-truth H = 0.88–0.95 on failures — **holds for mechanisms (a)+(d)
  (93/124, median 0.950) but NOT for (b), where H = 0.000.** Paper 6's
  blanket phrasing needs this caveat at its Q2 revision; the method paper
  states the split from the start.

## §5.7 consequence — measured, and a framing correction

**Order-level tiebreaking cannot move canonical AC@1 at all.** Pessimistic
scoring assigns the ground truth the worst rank in its score-tie block, so
any reordering *within* a tie block (alphabetical, local-H, anything) is
invisible to the metric. The D7 mitigation is only meaningful as **score
refinement** — folding local evidence into the score itself (e.g.
C′ = C − ε·(1 − H), ε small), which breaks score ties and therefore changes
pessimistic ranks.

Measured headroom of H-based score refinement, mechanism (a) only:
- ground truth inside the saturated tie block: 30 of 87
- of those, gt H strictly greater than every other block member's H (STRICT rescue): **18 cases** (26 under loose ≥ counting; 8 lost to H-ties)
- upper bound, STRICT (unique H-max; ruling 2a): 18 rescues → AC@1 0.008 → **0.152** on RE1-TT (19/125 = 1 baseline-correct + 18). Loose H-tie counting gives 26 rescues but is superseded.

Mechanism (b) headroom: **zero** — H = 0 for every service; there is no
signal to refine. Silence is Mamdani-rule-coverage territory (the injected
fault's telemetry signature matches no rule antecedent under the z-score
fuzzification): Future Work / Paper-8, exactly per the D7 ruling.

Mechanism (d) headroom: zero for ranking-side fixes (the block excludes the
ground truth); these are propagation-topology errors.

## §5.6 drafting notes

- Two-mechanism structure confirmed quantitatively: 70% saturation / 25%
  silence / 5% residual.
- Calibration cross-evidence: TT ECE worsens 0.219 → 0.243 under honest
  scoring because mechanism-(a) blocks carry C = 1.000 (maximal confidence,
  scored wrong) — the method is *confidently* wrong at scale.
- The 31 silence cases are fault-type-concentrated (loss/delay-dominated;
  see classified CSV) — connects to the OB finding that FCP's Mamdani base
  fires no Recommendation on 31/125 OB cases (12 delay, 12 loss, 7 disk).


---

## Appendix II — damping dose–response

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
