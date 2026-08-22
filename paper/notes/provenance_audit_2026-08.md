# Provenance audit — scratchpad-only measurements (Task P2-1)

Audited 2026-08-22. The project's standing rule is that every number in the
paper traces to a file under `results/` recorded in `RESULTS_PROVENANCE.md`.
Several measurements did not: they were computed in a session-local scratchpad
under `/private/tmp/`, quoted into analysis notes, and the CSVs then lost when
the session ended. This audit records what was durable, what was not, and what
has been regenerated.

## Finding as confirmed

- `find` across the repository for `*delta*`, `*sweep*`, `*ablation*`,
  `*refined*` returned only two markdown notes and a log — **no CSVs**.
- `grep -icE "delta|sweep|ablation|scratch" RESULTS_PROVENANCE.md` returned **0**.
- The scratchpad path cited by `delta_tradeoff_2026-08-11.md`
  (`scratchpad/delta_ext/…`) no longer exists.

So the paper's most consequential measurement — §5.9's dose–response, which is
also ratified contribution (iii) — was backed by a markdown note rather than by
data.

## Status after regeneration

| measurement | consumers | was durable? | now |
|---|---|---|---|
| **δ dose–response**, 11 δ × 3 systems × 125 cases | §5.9 table, 1.4×/2.6×/58× headline, dominance argument, MF-1/2/3 basins, SF-1's appendix reference, contribution (iii) | **no** | **REGENERATED** — `results/delta_sweep_per_case_{re1-ob,re1-ss,re1-tt}.csv` + `…_summary_….csv`, by `scripts/regenerate_delta_sweep.py`. **91 values diffed against the note: all match to three decimals. No STOP.** |
| **§5.7 refined variant** (ac1_shipped vs ac1_refined) | §5.7 measured-effect table, 17-gained/0-lost | **no** | **REGENERATED** — falls out of the δ sweep at δ = 0.85; verified OB 0.400→0.400, SS 0.160→0.160, TT 0.008→0.144, 17 gained / 0 lost. No separate artifact needed. |
| **§5.6 mechanism instrumentation** + §5.7 ceiling derivation | mechanism split 87/31/6, 43-distinct-top-1 / 25.8 %, gt_H median 0.950, ceiling 0.152, system-silence per fault | **no** | **REGENERATED** — `results/tt_mechanism_instrumentation.csv` by `scripts/regenerate_tt_instrumentation.py`. Every published figure reproduced exactly: 87/31/6; 43 and 0.258; 30 in-block / 26 loose / 18 strict / 8 lost to H-ties; median 0.950; ceiling (1+18)/125 = 0.1520; silence per fault cpu 5 / delay 7 / disk 7 / loss 4 / mem 8. |
| **τ and B ablations** | §5.9's τ = 0.5 cliff and vocabulary-collision rule; B-robustness claim | **no** | **REGENERATED** — `results/ablation_tau_{per_case,summary}.csv`, `results/ablation_bins_summary.csv` by `scripts/regenerate_tau_bin_ablations.py`. **23 values diffed against the note: all match.** τ = 0.5 cliff exact (Micro 0.400, MR 0.387, CR 0.334, BARO 0.206, DejaVu 0.054, yRCA 0.267, FCP 1.000); floor exactly 0.000 for all five ungrounded methods at every τ ≥ 0.6; B × ECE grid exact. |
| headline tables, per-case EC/CC, week2 validation, bootstrap CIs | §5.5, §5.10 | **yes** | unchanged; already in `results/` and recorded |

## Status: all four measurements now durable

No measurement quoted in the paper is scratchpad-backed any longer.

## Provenance recorded

`RESULTS_PROVENANCE.md` gains rows for the six δ-sweep files and a regeneration
note. Generating commit for all regenerated files: **`2d359bc`** — the dual-channel atom change it carries was
verified numerically neutral when it was made (AC@1 0.4000, SG 1.0000, SC 0.2660,
EC 0.8240 unchanged), and the diffs above re-confirm it end to end. The
regeneration scripts live in `scripts/` and are deterministic; no RNG on the FCP
path, DejaVu fixed-seed.

## Why the numbers survived

Worth recording, because it bears on how much to trust the notes elsewhere: the
lost CSVs were *reproducible*, and every regenerated value matched. The analysis
notes were accurate. What was missing was not correctness but auditability — a
reviewer or replicator could not have checked them, and the project's own
provenance rule was silently violated for the paper's most important
measurement.

## Rule tightened

Any future measurement that will be quoted in the paper is written to
`results/` **by a script in `scripts/`** and recorded in
`RESULTS_PROVENANCE.md` in the same session it is computed. Scratchpad output
is for exploration only and may not be cited.
