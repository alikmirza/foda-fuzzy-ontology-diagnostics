# SF-3 — the four unaccounted saturation cases

**Resolved. Count is exactly 4, so no §5 number moves.**

§5.7 stated that on RE1-TT the ground truth lies inside the saturated block in 30
cases, is the strict unique H-maximum in 18, and ties for the maximum in a further
8 — leaving 4 unexplained. The expected explanation was that in those 4 some other
service in the block carries strictly higher local confidence. **Verified against
the instrumentation rather than assumed.**

Source: `results/tt_mechanism_instrumentation.csv`, regenerated 2026-08-22 by
`scripts/regenerate_tt_instrumentation.py` at commit `2d359bc` (per-case, δ = 0.85,
pessimistic convention). Netting system silence out of the aggregates leaves the
87 saturation failures; of those, 30 have the ground truth inside the top block.

## Partition of the 30

| category | count | rescuable by local-H refinement? |
|---|---|---|
| ground truth is the strict maximum of H in its block | **18** | yes — these are the ceiling |
| ground truth ties for the maximum | **8** | no — a tie carries no evidential preference |
| ground truth is strictly below the maximum | **4** | no — another service has stronger rule support |

18 + 8 + 4 = 30 ✓, and the loose criterion's 26 = 18 + 8 ✓. Both identities hold,
so the partition is complete and the ceiling of 19/125 = 0.152 is unchanged.

## Why the 4 matter

They are the only group where promoting by local confidence would actively select
the *wrong* service: the block contains a service the rule base backs more
strongly than it backs the ground truth. That makes them qualitatively different
from the 8 ties, where the refinement is merely indifferent. §5.7 now says so.

## Per-case evidence

### below maximum — 4 cases

| case | fault | block size | gt H | block max H |
|---|---|---|---|---|
| `re1-tt_ts-auth-service_loss_4` | loss | 26 | 0.511 | 0.717 |
| `re1-tt_ts-order-service_disk_5` | disk | 10 | 0.820 | 0.880 |
| `re1-tt_ts-train-service_cpu_1` | cpu | 29 | 0.820 | 0.880 |
| `re1-tt_ts-travel-service_delay_2` | delay | 34 | 0.529 | 0.704 |

### tie for maximum — 8 cases

| case | fault | block size | gt H | block max H |
|---|---|---|---|---|
| `re1-tt_ts-auth-service_delay_1` | delay | 30 | 0.880 | 0.880 |
| `re1-tt_ts-auth-service_loss_3` | loss | 34 | 0.880 | 0.880 |
| `re1-tt_ts-route-service_delay_1` | delay | 29 | 0.950 | 0.950 |
| `re1-tt_ts-route-service_disk_2` | disk | 8 | 0.950 | 0.950 |
| `re1-tt_ts-route-service_loss_3` | loss | 32 | 0.880 | 0.880 |
| `re1-tt_ts-train-service_delay_3` | delay | 14 | 0.880 | 0.880 |
| `re1-tt_ts-train-service_loss_4` | loss | 33 | 0.880 | 0.880 |
| `re1-tt_ts-travel-service_loss_5` | loss | 17 | 0.880 | 0.880 |

counts: {'strict maximum': 18, 'tie for maximum': 8, 'below maximum': 4}
