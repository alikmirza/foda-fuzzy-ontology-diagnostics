# BARO standard-AC@1 discrepancy investigation

## Symptom

- `paper/notes/findings.md` (committed at `d1eb0e9` on 19:51) reports
  BARO overall AC@1 = **0.480**, per-fault `{cpu 0.520, mem 0.760,
  disk 0.360, delay 0.640, loss 0.120}`.
- `results/week2_baro_validation.csv` (mtime 19:47, on disk now)
  contains per-case data summing to overall AC@1 = **0.536**,
  per-fault `{cpu 0.680, mem 0.800, disk 0.400, delay 0.680,
  loss 0.120}`.
- Cross-method edge-shift diagnostic in this session reports BARO
  standard AC@1 = **0.536**, matching the on-disk CSV.

## Step 1 — git log of `evaluation/methods/baro.py` since c9077b0

```
$ git log --oneline c9077b0..HEAD -- evaluation/methods/baro.py
(no output)
$ git diff c9077b0 HEAD -- evaluation/methods/baro.py
(no diff)
```

**`baro.py` has not been modified since the BARO commit.** Zero
post-commit changes. Rule out (b) — code change since c9077b0.

## Step 2 — git log of `evaluation/methods/_onset.py` since c9077b0

```
$ git log --oneline c9077b0..HEAD -- evaluation/methods/_onset.py
(no output)
$ git diff c9077b0 HEAD -- evaluation/methods/_onset.py
(no diff)
```

**`_onset.py` also unchanged.** `baro.py` only references `detect_onset`
in docstring text — no `import` line, no runtime call. The shared
detector cannot influence BARO's native AC@1.

## Step 3 — Seed settings in `evaluate_baro.py`

The only seed is `_RANDOM_ONSET_SEED = 0`, used to construct
`random.Random()` for the **random-onset diagnostic** column. No
seeding for the native AC@1 path. No `np.random` calls. No `torch`
imports. BARO does not use any RNG in its standard path.

## Step 4 — Stochastic components in `baro.py`

```
$ grep -nE "np.random|random|shuffle|rand|np.choice|np.permut" \
        evaluation/methods/baro.py
(only docstring matches; zero RNG references in code)
```

Constants only: `hazard_lambda`, `prior_var`, `obs_var_floor`,
`max_run_length`. BOCPD predictive is pure linear algebra
(`np.log`, `np.exp`, `np.sum`, `np.concatenate`). Rule out (a) —
stochastic non-determinism.

## Step 5 — Re-run validation, compare per-case

Two consecutive re-runs of the harness today produce **bit-identical
per-case AC@1** (stable columns; `AC@1_random` differs because the
diagnostic uses an unsynchronized `random.Random` instance between
runs but the native path is identical). Both re-runs report overall
AC@1 = **0.536**.

Per-case diff between `results/week2_baro_validation.csv` (mtime
19:47, on disk) and today's re-run: **zero rows differ**. Both files
contain identical per-case AC@1 data summing to 67/125 = 0.536.

## Root cause — pre-commit iteration

Timeline reconstructed from `git reflog` + file mtimes:

| time  | event |
|-------|-------|
| 19:06 | `git reset` to HEAD (clearing earlier staged changes) |
| ~19:10 | initial draft of `baro.py` |
| **19:21** | first BARO validation run → printed overall AC@1 = **0.480**; CSV written |
| 19:21 – 19:47 | code iteration on `baro.py` (not yet committed) |
| **19:47** | second BARO run (via `pytest test_baro.py::test_re1_ob_ac_at_k_sanity_check` or a manual harness call) → CSV **overwritten** with new per-case data summing to 0.536 |
| 19:51 | three BARO commits land (`c9077b0`, `63979e7`, `d1eb0e9`) — code in repo is the post-19:47 version |
| 19:51 | findings entry (in `d1eb0e9`) carries the **19:21 printed numbers (0.480)**, not the post-fix CSV numbers (0.536) |

The 0.480 in the findings entry reflects a **pre-commit version of
`baro.py`** that produced lower AC@1. That earlier version is no
longer recoverable (no commit was made for it), but the fix landed
in the committed code at `c9077b0`. The fix increases overall AC@1
from 0.480 to 0.536 (+5.6 pp), with the largest per-fault improvement
on `cpu` (0.520 → 0.680, +16 pp).

The **per-case AC@1_random and AC@1_zscore_onset values match
between the findings entry (0.376 / 0.568) and the on-disk CSV
(0.376 / 0.568) exactly.** This is because those diagnostic paths
use `_detect_change_point` with a *forced* pivot (random in-band or
shared z-score onset), which doesn't depend on whatever BOCPD-related
bug was in the pre-commit version. Only the BOCPD-detected pivot
path was affected by the pre-commit fix; the forced-pivot paths were
unaffected.

## Classification

- (a) **Stochastic non-determinism that needs seeding** → NO. BARO
  is fully deterministic; consecutive re-runs are bit-identical.
- (b) **Code change since c9077b0 that needs investigation** → NO.
  `baro.py` is unchanged since the commit.
- (c) **Something else** → YES. The findings entry quotes numbers
  from a **pre-commit dev iteration of `baro.py`** that was later
  fixed before the commit landed. The committed code's actual output
  is 0.536; the findings entry's 0.480 is from an intermediate
  buggy version that was never committed and is no longer
  recoverable.

## Implication for the cross-method table

The cross-method edge-shift diagnostic's BARO standard AC@1 = 0.536
is **correct and consistent** with the committed code. The findings
entry's 0.480 is stale — written based on a version of `baro.py`
that does not match the committed source.

**Recommended fix:** update the BARO findings entry to use 0.536
(per the actual committed code's output). Per-fault corrections:

| fault | findings claim | actual (CSV) | delta |
|-------|----------------|--------------|-------|
| cpu   | 0.520          | 0.680        | +16pp |
| mem   | 0.760          | 0.800        | +4pp  |
| disk  | 0.360          | 0.400        | +4pp  |
| delay | 0.640          | 0.680        | +4pp  |
| loss  | 0.120          | 0.120        | 0     |
| **overall** | **0.480** | **0.536** | **+5.6pp** |

The qualitative narrative in the BARO findings entry stands:
- BARO still sits below the MR/CR/Micro convergence band
  (0.536 < 0.62), but the gap is now 9pp not 14pp.
- BARO's reference comparison structure (RCAEval ref 0.720 → our
  oracle 0.600 → our native AC@1) holds: the new native number is
  0.536 instead of 0.480, narrowing the BOCPD-vs-oracle gap from
  12pp to 6.4pp.
- The cross-method edge-shift table is correctly sourced; no need
  to re-run.

No code changes. No commits. Pure characterization of pre-commit
dev iteration vs committed state.
