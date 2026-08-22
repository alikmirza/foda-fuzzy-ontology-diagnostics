# Cold read v2 — PARTIAL (blocked)

Reviewer pass: 2026-08-22. Scope: `draft/section3_*.md`, `draft/section4_*.md`,
`draft/section5_*.md` as they exist on disk, checked against PROJECT_STATE.md
(2026-08-11), the v1 supplement, the δ/SC ruling of 2026-08-22,
`coldread_v1_fixes.md`, and `delta_tradeoff_2026-08-11.md`.

**This is not the cold read that was commissioned.** See STOP-1. What follows is
a review of the manuscript that is actually present, which is the pre-fix-round
manuscript. Every finding below is against that text.

---

## STOP-1 — The assembled manuscript does not exist on disk

The task brief states that the consolidated fix round (A1–A6, F1–F5, S1–S8,
Fix 5, Fix 8) is complete and that §1/§2/§7 are drafted. Neither connected
folder contains evidence of this.

**No §1, §2, or §7 exists.** A recursive search of both connected roots
(`research/papers`, `IdeaProjects/foda-fuzzy-ontology-diagnostics`) for any file
matching section1/section2/section6/section7/intro/related/conclusion/
manuscript/assembled/abstract returns **zero results**. The only drafts present
are §3, §4, §5.

**Nothing has been modified in ~9 days.** Newest paper file on either root:
`PROJECT_STATE.md`, 2026-08-13. The three section drafts: 2026-08-12. Today is
2026-08-22.

**The fix tracker itself still records the work as outstanding.**
`coldread_v1_fixes.md` (unmodified since 2026-08-12) lists:

| item | tracker status |
|---|---|
| S1 self-contained definitions | **PENDING** |
| S2 §5.5/§5.10 contradiction | **PENDING** |
| S3 δ headline concession | **PENDING** |
| S4 §3.5 forward clause | **PENDING** |
| S5 §1 from shifted story | **PENDING** |
| S7 canonical ceiling derivation | **PENDING** |
| S8 LaTeX-time checklist | **PENDING** |
| Fix 8a Theorem 1 W = 1 repair | **PENDING** |
| Fix 8b Theorem 2 Perron–Frobenius | **PENDING** |
| Fix 8c worked example re-derivation | **PENDING** |
| Fix 8d confidence formula + graph params | **PENDING** |

**The drafts corroborate the tracker, not the brief.** Spot-checks:

- §5.4 still contains the literal placeholder
  `[COMPRESSED DEFINITIONS — ~1 p, carried from the framework specification.]`
  → S1 not executed.
- §5.5 still asserts *"the claim that the two axes are independent"* with no
  across-methods narrowing and no forward pointer, while §5.10 says
  *"This reverses a conclusion... not independent within a method."*
  → S2 not executed; the contradiction is live in the text.
- §3.5 contains no forward clause to §5.9 → S4 not executed.
- §4.5 still carries the unrepaired bracket
  `[NEW-MATH: the W = 1 boundary case ... AUTHOR-VERIFY this condition against
  the implementation]` → Fix 8a not executed.
- §4.5 Theorem 2 names no Perron–Frobenius step → Fix 8b not executed.
- §4.5 worked example still reads *"numbers recomputed from the AICT worked
  example; re-derive independently before submission"* → Fix 8c not executed.
- §4.1 and §4.6 still carry `[AUTHOR-VERIFY]` on the correlation-graph
  parameters and the confidence formula → Fix 8d not executed.

**What did land:** Fix 5 / A-execution is genuinely complete and visible — §3.6
carries the two-layer provenance disclosure with both commits, §3.4's framing is
corrected, and §5.8 opens with the A-only disclosure paragraph. A1 (silence
taxonomy) and A3 (§5.8 arithmetic) are also in the text. A2 is partially in
(see MF-1).

**Required before cold read v2 can run:** either point me at where the fixed
manuscript actually lives, or treat the fix round as unstarted. The three
headline targets you named — the two theorems, the fresh §1/§2 prose, and the
§1 contribution list against the ratified spine — are **all unreviewable**: the
theorems are in their pre-repair state and §1/§2 do not exist.

---

## Must-fix (in the text that does exist)

### MF-1. §5.9(i) claims step-monotonicity that the sweep data contradicts

Current text: *"Ranking accuracy improves as propagation influence is reduced,
**monotonically at every step from δ = 0.85 downward on all three systems**."*

`delta_tradeoff_2026-08-11.md`, RE1-OB:

| δ | 0.850 | 0.500 | 0.200 | 0.100 | 0.001 |
|---|---|---|---|---|---|
| AC@1 | 0.400 | 0.480 | 0.544 | **0.560** | **0.552** |

AC@1 **falls** from 0.560 to 0.552 in the last step down. The interior optimum
at δ = 0.1 — which §4's framing note explicitly acknowledges — breaks the claim
on RE1-OB. RE1-TT also has a flat step (0.024 at both δ = 0.75 and δ = 0.65),
and RE1-SS a three-point plateau (0.408 at δ ≤ 0.2), so "at every step" is
non-strict on all three systems and outright false on one.

This is precisely the class of statement A2 was ratified to remove. Per the
2026-08-22 ruling: replace with dominance framing. The dominance claim is
sound — I verified δ = 0.2 beats δ = 0.85 on every axis on all three systems:

| system | AC@1 | SC | EC |
|---|---|---|---|
| OB | 0.544 > 0.400 | 0.396 > 0.266 | 0.835 > 0.824 |
| SS | 0.408 > 0.160 | 0.296 > 0.158 | 0.755 > 0.749 |
| TT | 0.216 > 0.008 | 0.212 > 0.086 | 0.824 > 0.789 |

### MF-2. §5.9(iii) — the explanation-axis basin extends *below* the shipped setting, not only above it

Current text: *"Coherence rises with the same damping that raises accuracy
(RE1-TT 0.086 → 0.372) ... completeness **rises or holds** (0.789 → 0.835)."*

RE1-TT, stepping down from the shipped setting:

| δ | 0.850 | 0.750 | 0.650 | 0.500 | 0.400 | … | 0.001 |
|---|---|---|---|---|---|---|---|
| SC | 0.086 | 0.074 | 0.086 | **0.084** | 0.106 | | 0.372 |
| EC | 0.789 | 0.768 | 0.763 | **0.784** | 0.800 | | 0.835 |

Both dip **below** the shipped value at δ = 0.5 before rising. "Rises or holds"
is false for EC at δ = 0.5 (0.784 < 0.789) and for SC at δ = 0.5 (0.084 <
0.086). §5.9(i) currently confines the non-monotonicity to *above* the shipped
setting; the basin is two-sided, roughly δ ∈ [0.5, 0.85], exactly as your
ruling describes. Same correction needed in §4's framing note, which says the
propagation *"costs both ranking accuracy and coherence"* over the whole range
from the shipped setting downward.

### MF-3. §5.9(i) mis-sites the explanation-axis minimum

Current text: *"coherence and completeness reach their minimum near δ ≈ 0.7–0.75."*
SC's minimum is 0.074 at δ = 0.75 ✓, but EC's minimum is 0.763 at δ = **0.65**,
below both 0.768 (δ = 0.75) and 0.784 (δ = 0.5). Widen to ≈ 0.65–0.75, or
state the two minima separately.

### MF-4. Theorem 1's contraction condition is stated wrongly, independent of Fix 8a

Current text: *"If W < 1 **or δ < 1** with W ≤ 1 strictly feasible, T is a
contraction."*

From the theorem's own bound ρ = 1 − δ(1 − W): contraction requires ρ < 1
⟺ δ(1 − W) > 0 ⟺ δ > 0 **and** W < 1. The disjunct "or δ < 1" is false —
at W = 1, ρ = 1 for **every** δ ∈ (0, 1], so δ < 1 buys nothing. The clause
"with W ≤ 1 strictly feasible" is also undefined. Fix 8a addresses the *repair*
for W = 1; this is a separate error in the statement of the condition itself
and would survive the repair as drafted.

### MF-5. The Corollary derives a finite iteration bound from a formula that diverges

Current text: *"N(ε) ≈ log ε / log ρ; with δ = 0.85 and worst-case effective
ρ = 0.15 + 0.85·W_eff, ε = 10⁻⁶ is reached in ≈ 30 iterations for W_eff = 1
treated via the non-expansive argument."*

At W_eff = 1, ρ = 0.15 + 0.85 = 1.000, and log ε / log ρ = −13.8155 / 0 → ∞.
A non-expansive operator has no iteration bound at all. The "≈ 30" is in fact
what Theorem 2's *local* bound gives: log(10⁻⁶)/log(0.626) = 29.5. So the
number is attributed to the wrong bound. As drafted the Corollary asserts a
finite convergence guarantee in exactly the regime where the theorem provides
none — and per PROJECT_STATE that regime is **common** (system-silent services,
25–37 % of cases), not pathological.

### MF-6. Two broken forward references to §5.9 — evidence displacement is promised but absent

§5.4: *"We call this **evidence displacement**; **§5.9 shows** it is the endpoint
of the same propagation behaviour that §5.6.1 analyses."*
§5.4 again: *"the same population identified by ... the system-silent cases in
**the damping sweep of §5.9**."*

§5.9 as drafted mentions neither evidence displacement nor silence. Both
pointers dangle. `coldread_v1_fixes.md` claims the terminology was "applied in
§5.4, §5.6.2, §5.9" — the first two are true, the third is not. Per supplement
item 4 this is also where the one-sentence §5.9 treatment is owed.

### MF-7. §5.5 cross-references a section that will not exist

*"We return to what this implies for method design in **§6′.1**."* §6 is NO-GO
for v1. Dead reference.

### MF-8. S2 contradiction is live between §5.5 and §5.10

§5.5: *"which is the empirical content of the claim that the two axes are
independent."* §5.10: *"Ranking accuracy and explanation quality are therefore
**not** independent within a method that produces both."* A reviewer reading in
order hits the reversal with no warning. S2's ratified fix (narrow §5.5 to
across-methods + forward pointer) is still unapplied.

---

## Should-fix

### SF-1. §5.7's ceiling claim is unscoped and the released sweep data violates it

*"Any measured value above 0.152 would indicate an implementation error rather
than a better method."*

`delta_tradeoff_2026-08-11.md` reports `ac1_refined` = **0.192** at δ = 0.95 and
**0.208** at δ = 1.00 — both above 0.152. The ceiling was derived from the
δ = 0.85 failure decomposition and is valid only there, but the sentence as
written is unconditional. Anyone who recomputes from the released sweep will
read it as a self-contradiction. Scope the claim to the shipped configuration.

### SF-2. §3.4's "64 ordered prototype pairs" silently admits self-propagation

8 prototypes give 64 ordered pairs only if self-pairs (CpuSaturation →
CpuSaturation) are counted; excluding them gives 8 × 7 = 56, and the remainder
would be 34, not 42. Either state that self-propagation is representable and
simply uncurated, or switch to 56/34. As written a reviewer cannot tell which
denominator the coverage argument uses.

### SF-3. §5.7's headroom arithmetic leaves 4 cases unexplained

*"the ground truth lies inside the saturated block in 30. Of those 30, it is the
strict unique maximum ... in **18**; in a further **8** it merely ties."*
18 + 8 = 26, leaving 4 of the 30 unaccounted. Presumably GT is inside the block
but not the local-H maximum; say so, or the reader assumes a slip.

### SF-4. No-Recommendation counts appear nowhere in §5

Supplement item 5 requires the measured 35 (not Paper 6's 31) with the
discrepancy left open. §5.5 refers to cases where "its rule engine fires no
recommendation" without a number, and §5.4's silence table reports head silence
only. If the 35 is meant to surface in the manuscript, it currently does not;
if it is not, correction #6 has no anchor in the text.

---

## Cleared — checked and correct

These were on my list and survive scrutiny; recorded so they are not re-checked.

- **§5.8 disclosure variant is correct.** The A-only language is in place
  (*"An independent re-derivation ... is under way and, **if** completed before
  submission, will replace this argument"*). No qualified-independence claim.
  No STOP.
- **§5.8 arithmetic, all three figures distinguished.** 520 − (270 + 85) = 165;
  84/165 = 0.509 named as the endorsement rate; (49·1.0 + 35·0.5)/165 = 0.403
  named as the pooled strength-weighted mean; 0.266 named as the mean of
  per-case means, with the reason it is lower. Exactly per A3.
- **§5.6 / §5.7 failure decomposition is internally exact.** 87 + 31 + 6 = 124
  failures + 1 correct = 125. The per-fault table reconciles on every axis:
  as-shipped correct 0+1+0+0+0 = 1 (= AC@1 0.008); refined 8+7+1+1+1 = 18
  (= 0.144); gained 17; saturation 18+15+17+20+17 = 87; silence 5+7+7+4+8 = 31,
  matching §5.6.2's "memory 8, delay 7, disk 7, CPU 5, packet loss 4"; residual
  by subtraction 2+2+1+1+0 = 6. Per-fault totals all 25.
- **§5.4 silence identity reproduces.** Head silence 32/46/33 → (125 − n)/125 =
  0.744 / 0.632 / 0.736, matching measured SG_fuzzy exactly. Gap vs system
  silence is 1 (OB) + 0 (SS) + 2 (TT) = 3 cases = the evidence-displacement
  count.
- **§3.2 ontology counts.** 12 classes, 13 object properties, 13 data
  properties all enumerate correctly; 8 + 16 + 8 + 22 + 4 = 58 individuals ✓,
  consistent with §3.3's "exactly two contributing factors, exactly one
  recommendation" per prototype and §3.4's 12 + 10 = 22.
- **§4.3 rule accounting.** R01–R16 across six categories sums to 16 ✓.
- **§5.2 case accounting.** 125 × 3 = 375 per method; × 7 = 2,625 ✓.
  §5.10's pooled 875 = 7 × 125 ✓.
- **Theorem 2 worked-example arithmetic.** ρ_loc ≤ 0.15 + 0.85 · 0.8 · 0.7 =
  0.626 ✓; ρ(W̃) = 0.7 for the uniform 3-cycle ✓; Theorem 1's global bound
  1 − 0.85(1 − 0.7) = 0.745 ✓. The numbers are consistent; what is missing is
  Fix 8b's named steps and Fix 8c's independent re-derivation.
- **TT headline phrasing** is verbatim canonical in §5.5, CI included, claim
  rested on the point estimate ✓.
- **δ→0 is presented as a finding, not a configuration.** §5.9's "Why we
  nevertheless report δ = 0.85" paragraph holds the S3 line correctly.

---

## What I could not check

- §1 contribution list against the four ratified items — **§1 does not exist**.
- §2 related work, §7 conclusions — **do not exist**.
- Abstract (variant B) — does not exist.
- Whether numbers trace to `results/` at `d485957`: I read the notes and drafts,
  not the CSVs. All arithmetic above is internal-consistency checking against
  `delta_tradeoff_2026-08-11.md` and the drafts, not provenance verification.
- Appendices A–F, Tables 1a–c, Figures 2–4 — all still markers.
