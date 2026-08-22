# A1 — "silence" is two phenomena, three counts. Definitions and case IDs.

Measured 2026-08-11 at commit `d485957` + dual-channel semantics, δ = 0.85.
The drafts used one word for three different measurements. Two named terms are
introduced below and applied in §5.4, §5.6, §5.9 and Appendix I.

## The three counts

| system | system silence (all C = 0) | head silence (all reported atoms H = 0) | no Recommendation atom |
|---|---|---|---|
| RE1-OB | 31 | 32 | 35 |
| RE1-SS | 46 | 46 | 48 |
| RE1-TT | **31** | **33** | 48 |

## The two terms

**System silence** — no service anywhere in the case carries positive local
evidence, and the propagated confidence is zero for every service. The method
has produced no hypothesis at all. This is the count §5.6.2 means by "silence"
as a *failure mechanism*: TT = 31.

**Head silence** — every atom in the reported explanation carries H = 0, i.e.
the explanation the operator sees rests on zero rule-base support. This is the
count the §5.4 identity uses, because SG_fuzzy is computed over the reported
atoms: OB = 32, SS = 46, TT = 33. **The §5.4 identity is
(125 − head-silence)/125 and reproduces the measured SG_fuzzy exactly**
(0.744 / 0.632 / 0.736), which is why this is the correct count there.

System silence implies head silence. The converse fails, and the gap is the
interesting part.

## The gap cases — evidence displacement (3 cases)

Head-silent but *not* system-silent: `re1-ob_cartservice_mem_2`,
`re1-tt_ts-order-service_cpu_5`, `re1-tt_ts-train-service_disk_2`.

The advisor's expected explanation is confirmed, and it is sharper than
expected. In each case the method *did* have local evidence — but propagation
promoted zero-evidence services above it, so the reported explanation contains
none of the evidence the method actually found:

| case | services with H > 0 | reported head (top-3 by C) | head H |
|---|---|---|---|
| `re1-ob_cartservice_mem_2` | **1** — `cartservice`, H = 0.290 (**and it is the ground truth**) | redis (C = 0.911), shippingservice (0.776), checkoutservice (0.639) | 0, 0, 0 |
| `re1-tt_ts-order-service_cpu_5` | 25 | ts-assurance-mongo, ts-consign-service, ts-news-service (all C = 1.000) | 0, 0, 0 |
| `re1-tt_ts-train-service_disk_2` | 19 | ts-config-mongo, ts-order-other-mongo, ts-contacts-mongo (all C = 1.000) | 0, 0, 0 |

The OB case is the cleanest demonstration in the whole study: exactly one
service had rule-base support, that service was the ground truth, and
propagation pushed it out of the reported top-3 in favour of three services with
no support whatsoever.

**Naming:** *evidence displacement* — propagation ranking zero-support services
above positive-support ones. It is not a separate mechanism from saturation; it
is saturation's endpoint, where the propagated signal has entirely replaced the
inferred one rather than merely blurring it. Three cases at δ = 0.85 across 375,
and it strengthens §5.9's dominance conclusion: the propagation step does not
only dilute local evidence, it can invert it.

## Third count: no-Recommendation ≠ silence, and it does not match Paper 6

A case can fire rules yet emit no Recommendation atom (the fired category has no
mapped `Rec_*` individual, or the root fault is unmapped). Counts: OB 35, SS 48,
TT 48 — strictly larger than head silence in every system, so this is a third,
weaker condition and must not be called silence.

**Discrepancy flagged:** Paper 6 states that FCP's OB completeness of 0.824
reflects "31 of 125 cases (12 delay, 12 packet-loss, 7 disk)" with no fired-rule
Recommendation. The measured count at current head is **35**, and the fault
split does not match either. Candidate Paper 6 correction #6 — pending
confirmation of whether the earlier figure was measured differently or is stale.

## Application

- §5.6.2 — "silence" → **system silence**, TT = 31. Unchanged numerically.
- §5.4 — identity table → **head silence**, 32 / 46 / 33. The earlier text said
  "31 of 125" for OB, which was the system-silence count; corrected to 32.
- §5.9 — "zero-signal cases" → **system silence**.
- Appendix I — mechanism (b) is **system silence**, 31 of 124 failures.
- §5.7 — mechanism-(b) zero headroom argument holds under either definition
  (both require H = 0 on every candidate that could be promoted).
