# Canonical Verification — 2026-08-10 (post convention-unification)

Scripted check of the LOCKED canonical set against regenerated phase2 outputs
(patched `run_phase2_ec` + `run_phase2_cc`, pessimistic tie handling).

```
_re1-ob: AC@1 0.4 (exp 0.4) | ECE 0.119 (exp 0.119) | SG all-1.0 True | PASS
_re1-ss: AC@1 0.16 (exp 0.16) | ECE 0.051 (exp 0.051) | SG all-1.0 True | PASS
_re1-tt: AC@1 0.008 (exp 0.008) | ECE 0.243 (exp 0.243) | SG all-1.0 True | PASS
VERIFICATION: PASS
```

## Canonical headline tables (regenerated via harness `headline_table` builder)

### RE1-OB (12 services, chance 1/12 ≈ 0.083)
| Method (family) | AC@1 | SG | SC | EC | ECE |
|---|---|---|---|---|---|
| DejaVu (supervised) | 0.696 | 0.000 | 0.000 | 0.333 | 0.099 |
| BARO (probabilistic) | 0.536 | 0.000 | 0.000 | 0.333 | 0.534 |
| CR (causal) | 0.624 | 0.000 | 0.000 | 0.333 | 0.300 |
| MR (graph-walk) | 0.632 | 0.000 | 0.000 | 0.333 | 0.335 |
| Micro (graph-walk) | 0.624 | 0.000 | 0.000 | 0.333 | 0.131 |
| yRCA (rule-based) | 0.328 | 0.267 | 0.000 | 0.333 | 0.349 |
| FODA-FCP (fuzzy-ontology) | 0.400 | 1.000 | 0.266 | 0.824 | 0.119 |

### RE1-SS (15 services, chance 1/15 ≈ 0.067)
| Method (family) | AC@1 | SG | SC | EC | ECE |
|---|---|---|---|---|---|
| DejaVu | 0.848 | 0.000 | 0.000 | 0.333 | 0.111 |
| BARO | 0.584 | 0.000 | 0.000 | 0.333 | 0.582 |
| CR | 0.656 | 0.000 | 0.000 | 0.333 | 0.266 |
| MR | 0.656 | 0.000 | 0.000 | 0.333 | 0.352 |
| Micro | 0.648 | 0.000 | 0.000 | 0.333 | 0.190 |
| yRCA | 0.256 | 0.149 | 0.000 | 0.333 | 0.380 |
| FODA-FCP | 0.160 | 1.000 | 0.158 | 0.749 | 0.051 |

### RE1-TT (64 services, chance 1/64 ≈ 0.016)
| Method (family) | AC@1 | SG | SC | EC | ECE |
|---|---|---|---|---|---|
| DejaVu | 0.744 | 0.000 | 0.000 | 0.333 | 0.171 |
| BARO | 0.392 | 0.000 | 0.000 | 0.333 | 0.390 |
| CR | 0.472 | 0.000 | 0.000 | 0.333 | 0.442 |
| MR | 0.480 | 0.000 | 0.000 | 0.333 | 0.182 |
| Micro | 0.456 | 0.000 | 0.000 | 0.333 | 0.174 |
| yRCA | 0.104 | 0.109 | 0.000 | 0.333 | 0.279 |
| FODA-FCP | 0.008 | 1.000 | 0.086 | 0.789 | 0.243 |

FODA-FCP on RE1-TT is **below the 1/64 chance baseline** (0.008 < 0.0156).

## Non-FCP ECE movements (expected, same cause)

The convention change also moves other methods' ECE where their rankings
contain score ties (e.g. MR RE1-TT 0.174 → 0.182, CR RE1-SS 0.300 → 0.266,
yRCA RE1-TT 0.245 → 0.279). AC@1 for all six non-FCP methods is unchanged
across the code states (verified: 0 row mismatches over 20 week2 cells).
