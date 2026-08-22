# Reviewer findings — Part 1, Tasks 4–7

Reviewed 2026-08-22. C1–C3 confirmed applied. Three new findings, one of them
material; two questions returned to the author.

## NF-1 (material) — the baselines' SC = 0.000 is an empty denominator, not a measurement

Computed from `results/phase2_semantic_coherence.csv`, which carries
`scored_link_count` and `unmapped_links` per case:

| method | coherent | incoherent | **scored links** | cases with ≥1 scored link |
|---|---|---|---|---|
| FODA-FCP | 84 | 81 | **165** | 89 / 125 |
| BARO | 0 | 0 | **0** | 0 / 125 |
| CausalRCA | 0 | 0 | **0** | 0 / 125 |
| DejaVu | 0 | 0 | **0** | 0 / 125 |
| MonitorRank | 0 | 0 | **0** | 0 / 125 |
| MicroRCA | 0 | 0 | **0** | 0 / 125 |
| yRCA | 0 | 0 | **0** | 0 / 125 |

So six of seven methods have **nothing in the coherence denominator**. Their
0.000 is a convention applied to an empty set, not a low score.

§5.5 currently reports it as a measurement: *"Five methods score exactly zero on
groundedness and coherence…"*, printed alongside FCP's 0.266 as if the two sit on
one scale. They do not — FCP has 165 scored links of which 84 are endorsed; the
others have no scored links at all.

This is the same species as the SG_fuzzy result §5.4 already handles well: a
metric value forced by structure rather than earned by measurement. §5.4 says of
that case *"the membership-weighted variant is therefore algebraically identical
to an indicator of whether the rule base fired at all"* and reports it as such.
SC on the baselines needs the same treatment — one or two sentences distinguishing
"emitted links that the ontology declined to endorse" from "emitted no link whose
endpoints resolve to fault prototypes." A reviewer who recomputes from the
released per-link data will find the empty denominators immediately.

Note this **strengthens** rather than weakens the paper's position: FCP is the
only method that can be scored on coherence at all, which is a sharper claim than
"FCP scores higher."

## NF-2 — §5.5's "empty middle" now contradicts §5.3's corrected table

§5.3, as rewritten this round, correctly records that **three** adapters write an
ontology-class string, DejaVu among them (`foda:Service/…`, `foda:FailureType/…`
in its own namespace, resolving to nothing in DiagnosticKB).

§5.5 four paragraphs later still says: *"No method occupies an intermediate
position: methods either commit to ontology grounding fully or **do not engage
with a diagnostic vocabulary at all**."*

DejaVu engages with a vocabulary. It is just not a *shared* one. As written the
two passages contradict each other.

The fix is not to delete the claim — it is to sharpen it, because DejaVu is
arguably the middle position and that is more interesting than an empty one.
Suggested restatement: no method occupies a middle position on **shared**
grounding; DejaVu shows that structured, typed output in a private namespace is a
real design point, and it scores zero not because it says nothing but because what
it says is not interoperable. That is a better motivation for §2 and a better
lead-in to whatever carries the discussion.

## NF-3 — §5.8 does not state the coherence denominator

FCP has ≥1 scored link in **89 of 125** cases. §5.8 says coherence *"is computed
per case and then averaged over cases, and that average is 0.266"* without saying
whether the average runs over 125 cases (36 contributing a convention zero) or
over the 89 that have scored links. The two differ materially: 0.266 over 125
corresponds to roughly 0.374 over 89.

This is the same failure mode A3 already repaired for 0.509 / 0.403 / 0.266 —
three defensible quantities, only one of them the metric. Add the denominator
explicitly, and say whether empty-denominator cases enter the mean as zeros. If
they do, that is a methodological choice worth one clause of defence.

## Confirmations

- **C1–C3 applied correctly.** C2 was re-verified numerically before editing,
  which is the right instinct.
- **§5.3's rewrite is well argued.** *"A method that names its own outputs in its
  own namespace has not grounded them in shared vocabulary"* is the correct
  reading of the adapter contract, and recording it prevents a reviewer from
  concluding the adapter simply failed to populate the field.
- **SF-3's partition is sound:** 18 + 8 + 4 = 30, loose 26 = 18 + 8. Noting that
  the 4 are qualitatively distinct — promoting by local confidence there would
  select the wrong service — is a better answer than the bare count.
- **Paper 6's Eq. (13) analysis is right.** No δ, neighbour H where the code uses
  propagated C, no (1 − H(s)) anchor, and no convex-mixing term — so Paper 6 does
  not inherit the journal draft's error, and no Paper 6 number moves.

## Correction to check

Your report says the Paper 6 equation item was filed as **ledger correction #6**.
#6 is already the no-Recommendation 35-vs-31 item, and the file shows a
*"Candidate correction #7"*. Confirm the equation item is #7 and that #6 is
untouched — a collision here would silently merge two open corrections.

## Two items I got wrong or under-specified

- **MF-7 was based on a conflation.** I read "§6′.1" as a reference to the
  abandoned operator-study §6 and told you to remove or redirect it. §6′ is a
  *Discussion* section, distinct from §6, and it was in the plan. Redirecting the
  pointer to §7 was a reasonable local fix, but the underlying question — whether
  the paper has a Discussion — is mine to have specified and I did not. Returned
  to the author.
- **The 12,000–15,000 word target has no source I can find.** PROJECT_STATE
  specifies ~29.5 pages, not a word count. Before anything is trimmed, that target
  needs to be traced to EMSE's actual author guidelines. At 14,749 words for
  §3–§5 with tables and figures still to come, a ~18,700-word projection is
  plausibly 34–37 Springer pages, which is within normal EMSE length. **Do not
  trim §5 to hit an unsourced number** — §5 is the paper's substance and the
  trimming would fall hardest on exactly the analytical passages that make it
  publishable.
