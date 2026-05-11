# DESIGN: removing inject_time from the method-facing contract

**Status:** proposal, awaiting approval. **No code in this commit.**

## 1. Motivation

The diagnostic shift run on MonitorRank showed that shifting
`inject_time` by +300 s collapses RE1-OB AC@1 to chance (0.104, down
from 0.664 overall). The collapse is structural, not statistical:
MonitorRank uses `inject_time` as the literal fencepost between its
"pre" and "post" z-score windows. Any method that does the same is
not deployable — in production, no oracle hands the algorithm the
exact moment the fault began.

Because every other baseline we plan to port (CausalRCA, MicroRCA,
BARO, DejaVu, yRCA, FODA-FCP) will pass through
`NormalizedCase`, the cleanest place to fix the leak is the
normalization layer. Fixing it once there means downstream methods
*cannot* peek even if their published reference implementation does.

This document proposes the API change, the per-method onset-detection
strategy, the placement-randomization scheme, the shift-evaluation
protocol, and the test fallout. It does **not** include code.

## 2. New `NormalizedCase` API

The current `NormalizedCase` exposes `inject_time`, `window_start`,
`window_end`, `metrics`, `services`, `schema_summary` on a single
flat dataclass. The proposal splits the flat dataclass into a
method-facing view and a ground-truth side channel.

### 2.1 Method-facing view

```python
@dataclass(frozen=True)
class NormalizedCase:
    """Telemetry presented to RCA methods.

    Methods MUST NOT read ``ground_truth``. The validator in the
    evaluation harness will inspect each method's source via AST
    walk on its first run and refuse to score any method that
    references ``ground_truth`` from inside ``diagnose``.
    """

    id: str
    case_window: pd.DataFrame        # fixed-length window (default 1800 s)
                                     # ALWAYS contains the fault somewhere
    window_start: float              # absolute Unix time of case_window[0]
    window_end:   float              # absolute Unix time of case_window[-1]
    sampling_dt:  float              # constant between samples
    services:     list[str]
    schema_summary: dict[str, list[str]]
    ground_truth: "CaseGroundTruth"  # side-channel — see below
```

Notes on what changed and why:

* **No more `inject_time` on the top level.** Methods that need the
  onset run change-point detection on `case_window` themselves.
* **`window_start` / `window_end` stay** — they describe the bounded
  observation window. They do **not** leak inject_time because the
  inject point sits at a per-case random offset (§3) inside the
  window, not at its centre.
* **`sampling_dt` is now explicit.** Methods used to recompute it
  from `df.time` diffs; making it a field saves duplicated work and
  guarantees every method sees the same value.
* **`metrics` renamed to `case_window`.** The rename makes the
  "this is your bounded telemetry slice" semantics unmistakable in
  code review and avoids any habit of treating the frame as
  unbounded ground truth.

### 2.2 Ground-truth side channel

```python
@dataclass(frozen=True)
class CaseGroundTruth:
    """Labels available ONLY to the evaluation harness.

    Methods that import this dataclass or read its fields inside
    ``diagnose`` are by definition not deployable and the harness
    will fail their evaluation run with ``ProtocolViolationError``.
    """

    inject_time:           float    # absolute Unix timestamp
    inject_offset_seconds: float    # inject_time - window_start
    root_cause_service:    str
    fault_type:            str
```

`inject_offset_seconds` is convenient for scoring — the harness can
compare a method's detected onset to ground truth in window-local
coordinates without juggling absolute times.

### 2.3 Function signatures

```python
DEFAULT_WINDOW_SECONDS:   float = 1800.0   # was 600.0 half-width
DEFAULT_INJECT_LOW_PCT:   float = 0.25
DEFAULT_INJECT_HIGH_PCT:  float = 0.75

def normalize_case(
    case: BenchmarkCase,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    inject_offset_seconds: float | None = None,   # for shift protocol
) -> NormalizedCase: ...
```

When `inject_offset_seconds` is omitted, it is derived per-case from
the `case.id` (see §3). When supplied, the caller (always the
evaluation harness, never a method) gets to pick the offset — this is
the lever the shift protocol pulls.

### 2.4 Protocol enforcement (optional but recommended)

```python
class ProtocolViolationError(RuntimeError): ...

def validate_method_does_not_peek(method: RCAMethod) -> None:
    """AST-walk method.diagnose to confirm it never references
    'ground_truth' or 'CaseGroundTruth'. Raise on violation."""
```

This is cheap insurance. Without it, a method that imports
`CaseGroundTruth` and reads it would silently keep working. With it,
the leak is caught at evaluation time. The validator is best-effort
(can't catch reflection-style access), but covers the common case of
sloppy refactors.

## 3. How the inject offset is chosen

**Deterministic per-case, derived from `case.id`.** Concretely:

```python
def default_inject_offset_seconds(
    case_id: str,
    window_seconds: float,
    low_pct:  float = DEFAULT_INJECT_LOW_PCT,
    high_pct: float = DEFAULT_INJECT_HIGH_PCT,
) -> float:
    h = hashlib.sha256(case_id.encode("utf-8")).digest()
    u = int.from_bytes(h[:8], "big") / (1 << 64)        # u ∈ [0, 1)
    return window_seconds * (low_pct + (high_pct - low_pct) * u)
```

Per-case hashing wins over a single global seed because:

* **Reproducibility.** Re-running a year later (or on another laptop)
  gives the same offsets as long as the case ids are stable.
* **Stability under dataset growth.** Adding a 26th `adservice_cpu_26`
  case does not perturb the offset of the first 25.
* **Cross-method comparability.** Every method, on every run, sees
  the same `case_window` for the same `case_id`. Reviewers comparing
  two methods don't have to wonder if the windows were re-rolled.
* **Cross-fault uniformity.** The cpu and delay variants of the same
  service get *different* offsets (their ids differ), so a method
  that overfits to "the inject is around 360 s in" on short cases
  cannot exploit that on long cases.

`hashlib.sha256` (not Python's built-in `hash`) is needed because the
built-in is salted per process (`PYTHONHASHSEED`).

## 4. How methods detect anomaly onset without `inject_time`

Three strategies, in order of how I'd recommend default behavior:

### 4.1 Strategy A — explicit change-point detection (recommended)

Each method runs a cheap change-point detector on `case_window` to
locate the inject onset, then uses that detected onset where it
previously used `inject_time`. A simple, robust default that works
across all the canonical features:

```python
def detect_onset(case_window: pd.DataFrame, services: list[str]) -> float:
    """Return a candidate ``time`` value that maximizes the aggregate
    z-score of post-vs-pre across all service-feature columns.

    Scans candidate pivots in [25%, 75%] of the window (so we never
    pivot on a padded edge). Per-pivot cost is O(C × T) where C is
    column count and T is window length; with C≈60 and T≈1800 the
    full scan is sub-100ms per case."""
```

Pros: cheap, deterministic, drops in everywhere the old code used
`inject_time`, transparent to reviewers.

Cons: it is a heuristic, so on cases where the fault propagates
slowly (loss, sometimes mem) the detected onset can lag the true one
by tens of seconds. That cost is real and will show up as a per-fault
AC@1 hit — which is the *correct* signal. A method whose AC@1 doesn't
fall under this regime is one that was using the side channel.

### 4.2 Strategy B — model-free magnitude scoring

Skip onset detection entirely. Score services by how anomalous they
are *across the whole window*, e.g.

```
score_i = max_f  (|x_f^i| - median(x_f^i)) / MAD(x_f^i)
```

or simply the variance of each feature over the window. Cheap and
inject-time-independent by construction. Weaker on faults where the
post-injection magnitude is small relative to baseline variance
(typically delay and loss).

### 4.3 Strategy C — split-search (most accurate, most expensive)

The method itself does the [25%, 75%] pivot scan to choose its own
pre/post split per service. Used when the method is naturally
formulated in terms of pre/post statistics but you want it
inject-time-clean.

MonitorRank should use **strategy A**. The first port (FODA-FCP) will
likely use strategy B or C depending on whether it formulates anomaly
fuzzy-membership as window-aggregate or as a propagation-time score.

## 5. Shift-evaluation protocol

For every method M and every case C:

1. `norm_true  = normalize_case(C)`
2. `out_true   = M.diagnose(norm_true)`
3. `ac1_true   = accuracy_at_k(out_true.ranked_list, gt, 1)`
4. For each shift δ ∈ {−300, +300} seconds:
   1. `offset' = norm_true.ground_truth.inject_offset_seconds + δ`
   2. Clip `offset'` to the same `[25%, 75%]` band so it remains a
      legal offset for the window. (Shifts that fall outside the
      band are recorded as `nan` and excluded from the aggregate.)
   3. `norm_shifted = normalize_case(C, inject_offset_seconds=offset')`
   4. `out_shifted  = M.diagnose(norm_shifted)`
   5. `ac1_shifted  = accuracy_at_k(out_shifted.ranked_list, gt, 1)`
5. Record per-case `(ac1_true, ac1_shift_minus, ac1_shift_plus)`.

Aggregate per-method **inject-time sensitivity**:

```
S(M) = mean over cases of |ac1_true - mean(ac1_shifted)|
```

`S(M) > 0.20` ⇒ method flagged as `inject_time_dependent` in the
Paper-6 Section 4 method-characterization table.

A clean, deployable method has `S(M) ≈ 0`. A method that quietly
reads `ground_truth.inject_time` will have `S(M)` near its AC@1
itself.

Note that "shift" here moves the **declared** inject point, not the
underlying telemetry. The `case_window` is identical between
`norm_true` and `norm_shifted`; only the side-channel changes. Hence
a method that ignores the side channel is invariant.

## 6. Impact on existing tests

Inventory of files touching `inject_time` / `normalize_case` /
`NormalizedCase` (greps above):

| file                                                | inject_time refs | affected? | what changes |
|-----------------------------------------------------|-----------------:|-----------|--------------|
| `evaluation/benchmarks/rcaeval_loader.py`           | several          | no        | still reads `inject_time.txt` into `telemetry`; that is upstream of normalization |
| `evaluation/benchmarks/foda12_loader.py`            | a few            | no        | same — loader contract unchanged |
| `evaluation/benchmarks/boutique_loader.py`          | a few            | no        | same |
| `evaluation/extraction/schema_normalizer.py`        | many             | **yes**   | dataclass split, new offset scheme, new signature |
| `evaluation/methods/monitorrank.py`                 | many             | **yes**   | switch to strategy A (change-point detect); drop direct `inject_time` reads |
| `evaluation/experiments/evaluate_monitorrank.py`    | indirect         | **yes**   | thread the shift-evaluation loop; widen result CSV |
| `evaluation/tests/test_rcaeval_loader.py`           | 17               | no        | loader tests only assert on the BenchmarkCase, which still carries `inject_time` |
| `evaluation/tests/test_boutique_loader.py`          | a few            | no        | same |
| `evaluation/tests/test_foda12_loader.py`            | a few            | no        | same |
| `evaluation/tests/test_schema_normalizer.py`        | 28               | **yes**   | every test that reads `norm.inject_time` / asserts on the window centre / asserts on row count needs porting to the new fields |
| `evaluation/tests/test_monitorrank.py`              | 10               | **yes**   | the contract tests are fine; the synthetic & RE1-OB sanity numbers change |
| `DEVIATIONS.md`                                     | indirect         | **yes**   | document that the inject_time-pre/post split was replaced by strategy A |
| `results/week2_monitorrank_validation.csv`          | n/a              | **yes**   | regenerated; gains `AC@1_shift_minus`, `AC@1_shift_plus`, `S(M)` columns |

### 6.1 Tests that need rewriting (concrete list)

`evaluation/tests/test_schema_normalizer.py`:

* **must change** — assert on new field name or behavior:
  - `test_window_bounds_are_symmetric_around_inject_time` — symmetry was
    the whole point of the old design; the new window is *asymmetric
    around inject_time*. The test should be renamed and rewritten to
    assert that `inject_offset_seconds ∈ [25%*W, 75%*W]`.
  - `test_window_size_is_2W_plus_1_for_long_case` — new size is
    `W/dt + 1`, not `2W/dt + 1`. Replace literal `1201` with formula.
  - `test_short_case_window_pads_when_data_is_shorter_than_window` —
    update padding-row expectations for the new window length.
  - `test_window_padding_uses_last_observed_value_at_trailing_edge` —
    same; the trailing edge is no longer pinned to `inject_time + W`.
  - `test_window_padding_uses_first_observed_value_at_leading_edge` —
    same.
  - `test_custom_window_size` — change the numerology.
  - `test_real_re1_ob_sample_normalizes_to_uniform_window` — change
    the asserted row count from 1201 to whatever the new W/dt + 1 is.

* **may need a touch-up** — accesses `norm.metrics`:
  - `test_short_case_latency_uses_p50`, `test_short_case_traffic_uses_workload`,
    `test_long_case_latency_uses_mean_column`,
    `test_long_case_traffic_prefers_load_over_workload`,
    `test_latency_prefers_mean_over_p50_when_both_present`,
    `test_latency_falls_through_to_p90_only`,
    `test_time_dot_one_dropped`,
    `test_resource_columns_passed_through`,
    `test_error_column_passed_through_under_service_prefix`
    — these read `norm.metrics`; rename to `norm.case_window`.
  - Same trivial rename for `test_schema_summary_*`.

* **unchanged**:
  - All `parse_service_list` tests.
  - All error-path tests (`test_missing_metrics_raises`,
    `test_missing_inject_time_raises`,
    `test_missing_time_column_raises`).

`evaluation/tests/test_monitorrank.py`:

* **contract tests** (`TestContractOnFakeFixture::*`,
  `TestFrontendSelection::*`, `TestInputValidation::*`) — pass through
  unchanged with one exception: `test_missing_inject_time_raises` may
  shift from `KeyError` to `ValueError` depending on where in the
  call chain we raise, and `test_metrics_with_no_services_raises` is
  unchanged.

* **synthetic scenarios** — the 3-service and 5-service tests should
  *still* place the anomalous service at top-1 under strategy A
  (the anomaly is dramatic, change-point detection has no trouble
  finding it). They will be **re-validated** rather than rewritten;
  if a test fails, the implementation needs work, not the test.

* **RE1-OB sanity** — the numbers change, probably downward, but the
  test's assertion ("at least one fault within 20 pp of either
  published baseline") is still the right guardrail. The flag-table
  also gains shifted-AC@1 and `S(M)` columns.

### 6.2 Tests that were passing only because of leakage

The 100% AC@1 we saw on `delay` faults almost certainly came from
the pre/post split landing perfectly at the injection spike. Under
strategy A the detector still finds that spike easily, but with a
few-sample lag — AC@1 should remain high but probably not 1.0. If it
drops to MicroCause/MicroRank territory that is *evidence the leak
fix worked*, not a regression.

## 7. Risk register

* **Risk:** `case_window` rename breaks downstream callers I didn't
  catch. **Mitigation:** keep `metrics` as a deprecated property
  alias for one release that warns and forwards to `case_window`,
  *plus* a grep across the whole repo at PR time.
* **Risk:** per-case hash offsets produce a pathological clump on
  some `case_id` namings (very unlikely with SHA-256, but worth a
  sanity histogram on RE1-OB). **Mitigation:** add a one-line test
  that asserts the 125 RE1-OB offsets cover the [25%, 75%] band with
  std > 10% of the band width.
* **Risk:** strategy A's onset detector is itself fragile on noisy
  short cases. **Mitigation:** the shift protocol catches this — if
  the detector is correct, `S(M) ≈ 0`; if it cheats and reads
  ground_truth, `S(M) ≫ 0` and the validator flags it.
* **Risk:** changing `DEFAULT_WINDOW_SECONDS` from 600 to 1800 makes
  short-case padding dominant (1080 s of bfill/ffill in a 1800 s
  window). **Mitigation:** either keep window at 1200 s (smaller
  random-positioning band) or document that short-case AC@1 will be
  systematically penalized for any method that depends on having
  real data on both sides of the inject point.

## 8. Open questions for approval

1. **Window length.** Is 1800 s the right default, or should we keep
   1200 s (current 2×W=2×600) with the random offset in [25%, 75%]
   thereof? 1800 s gives more spread for the offset but more padding
   on short cases. Recommendation: 1200 s — same row count as today,
   minimum disruption, still 600 s of valid offset band.
2. **Protocol validator (§2.4).** Implement now, or leave as a
   `TODO(paper-6)`? Recommendation: implement now — it's ~20 lines
   and prevents future-method regressions silently.
3. **Old `inject_time` property alias.** Keep as a deprecated
   property that raises `DeprecationWarning`, or remove cleanly?
   Recommendation: raise outright — the whole point is to make
   leakage loud, not gentle.
4. **Strategy A reference implementation.** Should it live in
   `schema_normalizer.py` (so every method gets the same default
   onset detector for free) or stay private to `monitorrank.py`
   (each method implements its own, on the principle that onset
   detection is part of the method, not the layer)?
   Recommendation: private to `monitorrank.py` for now;
   if the next two ports also want it, lift to a shared utility
   in `evaluation/methods/_onset.py`.

## 9. Awaiting approval

No code changes yet. Approve / amend / reject §2 (API), §3
(offset scheme), §4 (onset strategy), §5 (shift protocol), §6 (test
fallout), §7 (risks), §8 (open questions).
