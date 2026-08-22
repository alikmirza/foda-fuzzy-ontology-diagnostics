# SG_fuzzy verification before §5.4 drafting — 2026-08-10

Requested checks on the membership-weighted SG variant (FCP RE1-OB = 0.752 vs
crisp 1.000) before the number becomes citable. Measured on RE1-OB, 125 cases,
commit `d485957`. Definition under test:
`SG_fuzzy = Σ g(a)·μ(a) / Σ μ(a)`, `SG_crisp = mean g(a)`.

## Check 1 — is 0.752 a real spread or an adapter constant?

**Real spread, with structure.** FODA-FCP emits 465 atoms over the 125 cases,
none with a null membership:

| statistic | value |
|---|---|
| min / q25 / median / q75 / max | 0.000 / 0.033 / 0.333 / 0.339 / 1.000 |
| mean | 0.294 |
| distinct values (6 dp) | **251** |
| top-5 exact values | 0.000 (×113), 0.333 (×87), 0.334 (×38), 0.335 (×16), 1.000 (×12) |

251 distinct values over 465 atoms is a genuine continuum, not a constant. But
two plateaus are visible and must be disclosed: **113 atoms carry membership
exactly 0.000** and **141 sit in a narrow band around 0.333–0.335**. The 0.333
cluster is a rule-plateau artifact — a Mamdani firing strength of CF × min(μ)
lands there whenever a single antecedent at partial membership dominates
[AUTHOR-VERIFY: confirm which rule/antecedent combination produces the 1/3
plateau]. So the honest characterisation is: a real graded distribution with a
mass at zero and a plateau at ≈ 1/3, not a smooth spread.

## Check 2 — zero-signal (silence-class) cases and empty-explanation handling

**This is the finding that most affects interpretation.** On RE1-OB there are
**31 cases in which every FCP atom carries membership 0.000** — the same
silence class identified on RE1-TT (no Mamdani rule fires). On those cases:

- `SG_crisp = 1.000` (the atoms still carry DiagnosticKB IRIs), while
- `SG_fuzzy = 0.000` (the weighted denominator is zero → the definition's
  `den > 0 else 0.0` branch fires).

So the 1.000 → 0.752 drop is **not** a uniform down-weighting of confident
atoms. It is almost entirely these 31 cases collapsing to zero:
0.752 ≈ (125 − 31)/125 = 0.752 exactly. **The fuzzy variant on RE1-OB is, to
three decimals, the fraction of cases in which the rule base fired at all.**

That is a defensible and arguably desirable property — an explanation whose
every claim is held with degree zero should not score as perfectly grounded —
but §5.4 must state it plainly rather than presenting 0.752 as a graded
re-weighting. It also means SG_fuzzy and the §5.6 silence mechanism measure
overlapping things, which is a point in favour of the variant's validity and
must not be double-counted as independent evidence.

**Comparability:** crisp SG returns 0.0 for an empty atom set; fuzzy SG returns
0.0 for a zero-mass atom set. The two are consistent in form. No method
produced an empty explanation on RE1-OB (0 for all three tested), so the
empty-set branch is untested empirically here.

## Check 3 — do non-FCP adapters default to membership ≈ 1.0?

**No — all seven adapters emit graded memberships.** Source inspection:
MonitorRank / MicroRCA / CausalRCA use score-ratio normalisation
(`score / pi_max`); BARO uses a change-point membership and a
score-ratio; DejaVu uses a type membership and clipped scores; yRCA and FCP use
their own graded confidences. None writes a constant 1.0.

Measured on RE1-OB:

| method | atoms | median μ | mean μ | distinct values | SG crisp | SG fuzzy |
|---|---|---|---|---|---|---|
| FODA-FCP | 465 | 0.333 | 0.294 | 251 | 1.000 | **0.752** |
| yRCA | 863 | 0.051 | 0.212 | 697 | 0.267 | **0.253** |
| MonitorRank | 375 | 0.729 | 0.743 | 250 | 0.000 | 0.000 |

**The correct §5.4 statement is therefore neither of the two candidates in the
request.** It is not "only FCP exercises graded membership" (all seven do), and
it is not "all seven were reweighted" (five are unaffected). It is:

> All seven adapters emit graded membership values, so the fuzzy variant is
> defined uniformly across the panel. It changes the score only for methods
> with non-zero grounding, because a method whose atoms score g(a) = 0 has
> those zeros weighted by any membership and remains at zero. Empirically the
> variant is therefore visible on exactly the two ontology-aware methods:
> FODA-FCP (1.000 → 0.752) and yRCA (0.267 → 0.253).

MonitorRank is the instructive control: its atoms carry the *highest* mean
membership of the three tested (0.743, with 125 atoms at exactly 1.0 — the
top-1 service of each case), and its SG is 0.000 under both variants. Strong
confidence in an ungrounded claim earns nothing, which is the behaviour the
framework should have.

## Verdict on citability

- **0.752 is verified as reproducible and mechanically explained**, but it must
  be reported with its cause (31 zero-firing cases), not as a graded
  re-weighting of confident atoms.
- yRCA's 0.267 → 0.253 *is* a genuine graded re-weighting (no zero-mass cases),
  and is the cleaner illustration of the variant's intended behaviour.
- One open item: the 1/3 membership plateau needs a one-line explanation from
  the rule base before §5.4 quotes the distribution [AUTHOR-VERIFY].
- Suggested addition: report SG_fuzzy for all three systems, and state whether
  the "fraction of cases where the rule base fired" identity holds on SS and TT
  as well (predicted: yes on TT, where the silence class is 31/125 — which
  would give ≈ 0.752 there too, an unusually neat coincidence worth checking
  rather than asserting).


## Check 4 (ruling 4) — plateau traced: the CF × min(μ) hypothesis is REFUTED

Ten plateau atoms traced through their propagated confidence and firing rules:

| case | service | μ | C | Σ_head C | H (Mamdani) | fired rules |
|---|---|---|---|---|---|---|
| adservice_delay_1 | productcatalogservice | 0.3341 | 0.9221 | 2.7604 | **0.008** | R06 |
| adservice_delay_2 | adservice | 0.3378 | 0.9668 | 2.8621 | 0.880 | R10 |
| adservice_delay_2 | currencyservice | 0.3353 | 0.9596 | 2.8621 | 0.254 | R01, R03 |
| adservice_disk_1 | adservice | 0.3334 | 0.9999 | 2.9994 | 0.950 | R03, R10 |
| adservice_disk_1 | recommendationservice | 0.3333 | 0.9998 | 2.9994 | 0.880 | R03, R06 |
| adservice_disk_1 | emailservice | 0.3333 | 0.9997 | 2.9994 | 0.880 | R03, R10 |
| adservice_disk_2 | cartservice | 0.3335 | 1.0000 | 2.9986 | 0.880 | R03, R06 |
| adservice_disk_2 | adservice | 0.3335 | 1.0000 | 2.9986 | 0.950 | R02, R03 |
| adservice_disk_2 | productcatalogservice | 0.3330 | 0.9986 | 2.9986 | 0.686 | R01, R03 |
| adservice_disk_4 | productcatalogservice | 0.3347 | 0.9995 | 2.9864 | 0.880 | R10 |

**Cause.** The explanation builder assigns
`fuzzy_membership = clip(C(s) / Σ_{head} C, 0, 1)` with `top_k = 3`. When the
three head services are saturated at C ≈ 1.0 the share is 1/3 for each — the
plateau is the **top-3 confidence share under saturation**, and has nothing to
do with rule firing strengths. The zero mass has the same origin: when the head
is entirely at C = 0 (silence class) the guarded denominator makes every share
0.0.

**The consequential part.** The atom's `fuzzy_membership` is therefore **not the
Mamdani membership H(s)**. The trace shows the two decoupling completely — row 1
carries μ = 0.334 with H = 0.008, and rows 4–6 carry near-identical μ over H
values from 0.880 to 0.950. The field is a normalised confidence share within
the top-k head, i.e. a ranking-derived quantity, not a Zadeh-style degree of
truth.

**Three consequences requiring author decisions.**

1. **A drafted claim in §4.7 is false and must be corrected either way.** The
   §4.7 text states that each atom carries "its Mamdani membership as the atom's
   fuzzy membership." It carries the head-share instead.
2. **The R2 answer changes character.** Making a metric consume
   `fuzzy_membership` closes the letter of the criticism ("the field is consumed
   by no metric"), but if the field is a normalised ranking score then the
   spirit of the criticism survives: the fuzzy machinery still does not enter
   the measurement. A careful reviewer will make exactly this move.
3. **Options.** (a) Report as-is with precise language — the variant weights by
   confidence share, and say so, dropping any claim that it weights degree of
   truth. (b) Change the adapter to emit H(s) as the atom membership, which is
   what §3.5's design story implies, then re-run — this is a code change to the
   evaluated method and would alter atom semantics and every fuzzy-variant
   number. (c) Emit both: keep the share as a confidence field and add H(s) as
   the membership, making SG_fuzzy genuinely membership-weighted.

Recommendation: **(c)**, because it makes the paper's own §3.5 claim true
without discarding the existing confidence channel, and because SG_fuzzy
weighted by H would then measure something the crisp metric cannot — how
strongly the *rule base* backs each grounded claim. Under (a) the honest §5.4
sentence would have to concede that the fuzzy variant is a confidence-weighted,
not membership-weighted, re-scoring.


## Check 5 — dual-channel correction applied; PREDICTION ON RECORD (pre-run)

Ruling (c) implemented 2026-08-10: atoms now carry two channels —
`confidence_share` (the former `fuzzy_membership`: share of the reported head's
propagated-confidence mass) and `fuzzy_membership` := H(s), the Mamdani local
confidence. Both FCP link-weight computations were pinned to
`confidence_share`, so the change is provably semantic only.

**Regression check (RE1-OB, post-change):** AC@1 0.4000, SG 1.0000, SC 0.2660,
EC 0.8240 — identical to the committed canonical values. Verified, not assumed.

**New channel distributions (RE1-OB, 465 atoms):**

| channel | mean | median | distinct | zeros |
|---|---|---|---|---|
| `fuzzy_membership` = H(s) | 0.514 | 0.820 | 71 | 149 |
| `confidence_share` (old field) | 0.294 | 0.333 | 251 | 113 |

**Predictions recorded before the H-weighted run (ruling 5).** Deviation from
any of these is to be reported loudly rather than absorbed:

1. **H-weighted SG_fuzzy on RE1-OB will be below 0.752** and genuinely graded
   (not an integer fraction of the case count).
2. **The silence identity persists**: the 31 zero-firing cases still collapse to
   SG_fuzzy = 0, because H = 0 for every atom there — indeed more strongly, since
   H has 149 zeros against the share's 113.
3. **The within-case component becomes non-trivial**, unlike the share-weighted
   v1 where it was negligible. Propagation-inflated atoms — high C, low H, e.g.
   `adservice_delay_1 / productcatalogservice` at share 0.334 but H 0.008 — will
   now be heavily down-weighted, so cases in which the rule base fired weakly
   will score below 1.0 rather than at it.
4. Because H is bimodal (median 0.820 with a large zero mass) the resulting
   distribution should be **less smooth** than the share-weighted one.

If (1) or (3) fails — i.e. the H-weighted number lands at or above 0.752, or the
decomposition remains purely case-level — that indicates H and the share are
more correlated than the trace suggests, and the R2 answer would need rethinking
again rather than restating.


## Check 6 — RESOLUTION (2026-08-11): uniform identity, and it is algebraic

The authorised SS diagnostic resolves the question and supersedes the
mid-analysis suggestion that SS showed a stronger within-case component.

| system | silence cases | (125 − silence)/125 | measured SG_fuzzy |
|---|---|---|---|
| RE1-OB | 32 | 0.744 | 0.744 |
| RE1-SS | 46 | 0.632 | 0.632 |
| RE1-TT | 33 | 0.736 | 0.736 |

The identity holds exactly on all three systems. SS's larger drop is a higher
silence rate (46/125 = 37 %), not a different weighting behaviour. H
distributions are otherwise comparable (median when firing 0.880 / 0.880 /
0.593; partial memberships 17 % / 15 % / 38 % of firing atoms).

**And the identity is forced, not observed.** Every FODA-FCP atom carries an
ontology IRI, so g(a) = 1 for all atoms, giving
SG_fuzzy = Σ 1·μ / Σ μ = 1 whenever any μ > 0, and 0 otherwise. For a
total-grounding method the membership-weighted variant *is* the firing
indicator, by construction. The pre-registered prediction could not have
succeeded; the failure is analytic, not empirical. Membership weighting
discriminates only under partial grounding — which is why yRCA moves genuinely
(0.267 → 0.253 on OB, 0.149 → 0.112 on SS) and FCP cannot.

**Status:** SG_fuzzy citable with this framing. No further metric iteration
(forking-paths closure stands).
