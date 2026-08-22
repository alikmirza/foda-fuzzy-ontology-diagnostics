# Independent propagation-table validation — protocol for P. Kosov

**Purpose.** The DiagnosticKB propagation table (22 individuals) was authored
during the evaluation phase, concurrently with the metric that scores against it
(see `ontology_provenance_finding.md`). This protocol converts an unverifiable
provenance claim into a measured agreement rate. Option B of the 2026-08-11
ruling; runs in parallel with the disclosure already drafted into §3.6/§5.8 and
does **not** gate submission. Target completion: two weeks from ruling.

**Why Kosov.** The draft CRediT statement assigns him ontology engineering and
validation, and he did not author the propagation table — the two conditions
independence requires.

## Materials to provide (and nothing else)

1. The eight fault prototypes, names and one-line descriptions only:
   `CpuSaturation`, `MemoryLeak`, `LatencySpike`, `NetworkCongestion`,
   `HighErrorRate`, `ResourceContention`, `ThroughputDegradation`,
   `DiskIoBottleneck`.
2. The strength vocabulary and its meaning: **1.0** = the target almost always
   co-occurs with the source; **0.5** = conditional, depends on configuration,
   load or severity; **absent** = atypical or not a propagation.
3. The empty 8 × 8 ordered-pair grid (64 cells, self-pairs included and to be
   left absent unless he judges otherwise).
4. The instruction that this concerns microservice fault propagation in general,
   not any specific system.

## Materials to withhold — this is what makes it blind

- The existing 22 propagations, in any form.
- All coherence results (0.266 / 0.158 / 0.086) and any per-link data.
- The benchmark systems, fault types, and the fact that RCAEval is involved.
- Any statement about which propagations the method's links tend to hit.

## Task

Enumerate independently, for each ordered pair (A, B), whether a fault of type A
typically propagates to a fault of type B, assigning 1.0, 0.5, or leaving
absent. No time limit; no consultation of the repository.

## Measurement

Let **E** be the existing 22-individual set and **K** his set.

1. **Set overlap on the existing 22:** |E ∩ K| / |E| — the fraction of shipped
   propagations he independently reproduces.
2. **Strength agreement on the intersection:** of the pairs in E ∩ K, the
   fraction assigned the same strength value; report the confusion between 1.0
   and 0.5 separately from presence/absence disagreement.
3. **His additions (K \ E):** candidate curation omissions. These feed §5.8's
   gap analysis directly — a link type FCP emits that is unendorsed by E but
   *endorsed* by K is evidence that the table under-covers rather than that the
   method is incoherent.
4. **His deletions (E \ K):** propagations he judges atypical. Report; do not
   remove them from the shipped table before submission (that would re-introduce
   post-hoc curation, this time in the flattering direction).

Record all four in `propagation_validation_results.md` with the raw grid.

## How the result enters the paper — both variants pre-written

**If completed before submission**, §5.8's provenance paragraph gains:

> An independent re-derivation supports the table's content: a co-author who did
> not author it, working blind from the prototype set and the strength
> vocabulary alone, reproduced [N] of the 22 propagations ([X] %) with [M]
> strength agreements on the intersection, and proposed [P] additional
> propagations that the shipped table omits. The agreement is evidence that the
> table encodes transferable domain knowledge rather than evaluation-specific
> curation; the proposed additions are analysed as coverage gaps below.

**If not completed**, the paragraph as currently drafted stands unchanged — the
disclosure plus the direction-of-result argument — and the validation moves to
§7 as declared future work. No other section depends on the outcome.

## Interpretation guardrail

A low overlap is not a failure of the protocol and must be reported as
faithfully as a high one. It would mean the propagation table encodes one
expert's judgement rather than consensus domain knowledge — which is worth
knowing, is consistent with the low measured coherence, and would strengthen
rather than weaken §5.8's conclusion that the fix is ontology work.
