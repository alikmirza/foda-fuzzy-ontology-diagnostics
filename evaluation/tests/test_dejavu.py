"""Tests for ``evaluation.methods.dejavu`` on :class:`NormalizedCase`.

Eight groups of tests:

1. **Train contract** — accepts a list of NormalizedCase, refuses
   empty input, populates ``services`` / ``fault_types`` / ``net``.
2. **Diagnose contract** — requires train() first, returns a
   :class:`DiagnosticOutput`, ranks the trained-on root cause top-1
   when the test case is identical to a training case.
3. **Protocol validator** — passes on ``diagnose``, ignores ``train``.
4. **Shift invariance** under ±300 s ground-truth offset.
5. **Training-size ablation interface** — train multiple times on
   subsets, AC@1 is well-defined for each.
6. **Attention extraction** — raw_output exposes the attention matrix
   in the right shape and dtype.
7. **Input validation** — bad init args, missing service vocab,
   missing model on diagnose.
8. **Parameter budget** — model has < 1 M parameters at default size.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from evaluation.extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
)
from evaluation.extraction.schema_normalizer import (
    NormalizedCase,
    normalize_case,
)
from evaluation.methods._protocol import validate_no_ground_truth_peeking
from evaluation.methods.dejavu import (
    DejaVuMethod,
    _DejaVuNet,
    parameter_count,
)
from evaluation.metrics.ranking_metrics import accuracy_at_k


# ---- helpers ----


def _make_case(
    df: pd.DataFrame,
    inject_time: float,
    root_cause: str,
    case_id: str = "synthetic",
    fault_type: str = "cpu",
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        telemetry={"metrics": df, "inject_time": inject_time},
        ground_truth_root_cause=root_cause,
        ground_truth_fault_type=fault_type,
        system_topology=None,
    )


_SYNTH_WINDOW_SECONDS = 200.0


def _synthetic_case(
    seed: int = 0,
    root_cause: str = "db",
    fault_type: str = "cpu",
    n: int = 240,
    case_id: str = "synthetic",
) -> NormalizedCase:
    """Compact synthetic case for unit tests.

    ``n=240`` samples + a 200 s window keep DejaVu's Conv1d encoder
    fast on CPU — ~10 ms per train epoch on 8 cases at the unit-test
    defaults. The RE1-OB harness uses the full 1200 s window.
    """
    inject_idx = n // 2
    rng = np.random.default_rng(seed)
    services = ["frontend", "cart", "db"]
    df: dict[str, np.ndarray] = {"time": np.arange(n, dtype=float)}
    for svc in services:
        df[f"{svc}_latency"] = 0.10 + rng.normal(0.0, 0.01, n)
        df[f"{svc}_traffic"] = 100.0 + rng.normal(0.0, 1.0, n)
        df[f"{svc}_cpu"] = 0.20 + rng.normal(0.0, 0.01, n)
        df[f"{svc}_mem"] = 0.30 + rng.normal(0.0, 0.01, n)
    # Inject a large step in the root cause's CPU and latency.
    df[f"{root_cause}_cpu"][inject_idx:] += 0.6
    df[f"{root_cause}_latency"][inject_idx:] += 0.2
    bcase = _make_case(
        pd.DataFrame(df),
        inject_time=float(inject_idx),
        root_cause=root_cause,
        case_id=case_id,
        fault_type=fault_type,
    )
    return normalize_case(bcase, window_seconds=_SYNTH_WINDOW_SECONDS)


def _method(**kwargs) -> "DejaVuMethod":
    """DejaVuMethod with the unit-test default ``window_seconds``."""
    kwargs.setdefault("window_seconds", _SYNTH_WINDOW_SECONDS)
    return DejaVuMethod(**kwargs)


def _training_set(seed_base: int = 0, n_per_class: int = 4) -> list[NormalizedCase]:
    """Small synthetic training set with two classes (db CPU, cart CPU)."""
    cases = []
    for i in range(n_per_class):
        cases.append(
            _synthetic_case(
                seed=seed_base + i,
                root_cause="db",
                fault_type="cpu",
                case_id=f"db_cpu_{i}",
            )
        )
        cases.append(
            _synthetic_case(
                seed=seed_base + 100 + i,
                root_cause="cart",
                fault_type="cpu",
                case_id=f"cart_cpu_{i}",
            )
        )
    return cases


# ---- 1. train contract ----


class TestTrainContract:
    def test_train_populates_state(self):
        m = _method(epochs=4)
        cases = _training_set()
        m.train(cases)
        assert m.net is not None
        assert m.services is not None
        assert set(m.services) == {"frontend", "cart", "db"}
        assert "cpu" in m.fault_types
        assert "mem" in m.fault_types

    def test_train_refuses_empty(self):
        m = _method()
        with pytest.raises(ValueError, match="empty"):
            m.train([])

    def test_train_drops_cases_outside_service_vocab(self):
        """Cases whose root_cause_service does not appear in any
        training case's services are dropped (the head cannot learn
        a class with zero positive examples)."""
        m = _method(epochs=2)
        cases = _training_set()
        # Add a case whose root cause is an unknown service.
        bad = _synthetic_case(
            seed=999, root_cause="db", case_id="bad",
        )
        bad = dataclasses.replace(
            bad,
            ground_truth=dataclasses.replace(
                bad.ground_truth,
                root_cause_service="never_seen_service",
            ),
        )
        m.train(cases + [bad])
        # Service vocab is the union of services in case_window columns,
        # which does NOT include "never_seen_service".
        assert "never_seen_service" not in m.services


# ---- 2. diagnose contract ----


class TestDiagnoseContract:
    def test_diagnose_requires_train(self):
        m = _method()
        case = _synthetic_case()
        with pytest.raises(RuntimeError, match="train"):
            m.diagnose_normalized(case)

    def test_diagnose_returns_diagnostic_output(self):
        m = _method(epochs=8)
        cases = _training_set()
        m.train(cases)
        out = m.diagnose_normalized(cases[0])
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "dejavu"
        assert out.wall_time_ms >= 0.0

    def test_diagnose_ranked_list_sorted(self):
        m = _method(epochs=8)
        cases = _training_set()
        m.train(cases)
        out = m.diagnose_normalized(cases[0])
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_diagnose_ranks_trained_class_top_1_on_seen_pattern(self):
        """A small DejaVu trained on db-cpu and cart-cpu should rank
        the correct root cause top-1 when shown a held-out db-cpu
        case generated the same way. Stochastic — use enough epochs
        and a seed."""
        m = _method(epochs=60, seed=0)
        m.train(_training_set(seed_base=0, n_per_class=4))
        held_out = _synthetic_case(seed=42, root_cause="db", case_id="held_out_db")
        out = m.diagnose_normalized(held_out)
        top, _ = out.ranked_list[0]
        assert top == "db", (
            f"expected db top-1 on held-out db-cpu case, got "
            f"{out.ranked_list}"
        )

    def test_explanation_carries_predicted_failure_type_root(self):
        m = _method(epochs=8)
        m.train(_training_set())
        out = m.diagnose_normalized(_synthetic_case(seed=42))
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        roots = out.explanation_chain.roots()
        assert len(roots) == 1
        assert "predicted failure type" in roots[0].text

    def test_confidence_in_unit_interval(self):
        m = _method(epochs=8)
        m.train(_training_set())
        out = m.diagnose_normalized(_synthetic_case(seed=42))
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0


# ---- 3. protocol validator ----


class TestProtocolValidator:
    def test_diagnose_does_not_reference_ground_truth(self):
        validate_no_ground_truth_peeking(DejaVuMethod())

    def test_train_is_exempt_from_validator(self):
        """The AST validator scans ``diagnose`` by name. ``train``
        legitimately reads ``ground_truth`` (it's labeled data); the
        validator never looks at it."""
        # If it did, this would raise — DejaVu.train references
        # nc.ground_truth.root_cause_service multiple times.
        validate_no_ground_truth_peeking(DejaVuMethod())  # should not raise


# ---- 4. shift invariance ----


class TestShiftInvariance:
    def test_output_identical_under_pm_300s_shift(self):
        """Diagnose must produce bit-identical output under the
        ±300 s ground-truth offset shift, by construction (no
        ``ground_truth`` reads in ``diagnose``)."""
        m = _method(epochs=8, seed=0)
        m.train(_training_set())
        held_out = _synthetic_case(seed=42, root_cause="db")
        out_true = m.diagnose_normalized(held_out)
        for shift in (-300.0, 300.0):
            shifted_gt = dataclasses.replace(
                held_out.ground_truth,
                inject_time=held_out.ground_truth.inject_time + shift,
                inject_offset_seconds=(
                    held_out.ground_truth.inject_offset_seconds
                ),
            )
            shifted = dataclasses.replace(
                held_out, ground_truth=shifted_gt
            )
            out = m.diagnose_normalized(shifted)
            assert out.ranked_list == out_true.ranked_list
            assert out.confidence == out_true.confidence


# ---- 5. training-size ablation interface ----


class TestTrainingSizeAblation:
    def test_train_repeatedly_with_growing_subsets(self):
        """Sanity check: train() can be called multiple times with
        different subsets, and AC@1 is well-defined for each. The
        harness's training-size ablation relies on this."""
        full = _training_set(seed_base=0, n_per_class=4)
        held_out = _synthetic_case(seed=999, root_cause="db", case_id="held_out")
        for n in (2, 4, 6, 8):
            m = _method(epochs=20, seed=0)
            m.train(full[:n])
            out = m.diagnose_normalized(held_out)
            top, _ = out.ranked_list[0]
            assert top in m.services
            ac1 = accuracy_at_k(out.ranked_list, "db", 1)
            assert ac1 in (True, False)


# ---- 6. attention extraction ----


class TestAttentionExtraction:
    def test_raw_output_attention_shape_matches_service_vocab(self):
        m = _method(epochs=4)
        m.train(_training_set())
        out = m.diagnose_normalized(_synthetic_case())
        attn = out.raw_output["attention"]
        S = len(m.services)
        assert isinstance(attn, list)
        assert len(attn) == S
        assert all(len(row) == S for row in attn)

    def test_attention_rows_sum_to_one_for_present_services(self):
        m = _method(epochs=4)
        m.train(_training_set())
        out = m.diagnose_normalized(_synthetic_case())
        attn = np.asarray(out.raw_output["attention"])
        mask = np.asarray(out.raw_output["present_mask"])
        for i, mi in enumerate(mask):
            if mi <= 0:
                continue
            row_sum = float(attn[i].sum())
            assert 0.99 <= row_sum <= 1.01

    def test_explanation_contains_neural_attention_attribution_links(self):
        m = _method(epochs=20)
        m.train(_training_set())
        out = m.diagnose_normalized(_synthetic_case(seed=42))
        relations = {
            link.relation_type for link in out.explanation_chain.links()
        }
        assert "predicted-failure-unit" in relations
        assert "neural-attention-attribution" in relations


# ---- 7. input validation ----


class TestInputValidation:
    @pytest.mark.parametrize("hidden", [0, 1, 3])
    def test_hidden_must_be_at_least_four(self, hidden):
        with pytest.raises(ValueError, match="hidden"):
            DejaVuMethod(hidden=hidden)

    def test_epochs_must_be_positive(self):
        with pytest.raises(ValueError, match="epochs"):
            DejaVuMethod(epochs=0)

    def test_lr_must_be_positive(self):
        with pytest.raises(ValueError, match="lr"):
            DejaVuMethod(lr=0.0)

    def test_batch_size_must_be_positive(self):
        with pytest.raises(ValueError, match="batch_size"):
            DejaVuMethod(batch_size=0)

    def test_weight_decay_must_be_non_negative(self):
        with pytest.raises(ValueError, match="weight_decay"):
            DejaVuMethod(weight_decay=-1e-3)

    def test_type_loss_weight_in_range(self):
        with pytest.raises(ValueError, match="type_loss_weight"):
            DejaVuMethod(type_loss_weight=-0.1)
        with pytest.raises(ValueError, match="type_loss_weight"):
            DejaVuMethod(type_loss_weight=11.0)

    def test_window_seconds_must_be_positive(self):
        with pytest.raises(ValueError, match="window_seconds"):
            DejaVuMethod(window_seconds=0.0)


# ---- 8. parameter budget ----


class TestParameterBudget:
    def test_default_size_under_one_million(self):
        """The brief sets a 1 M parameter ceiling. The 3-service /
        7-feature / hidden=32 default is well under it (~10 k)."""
        from evaluation.methods.dejavu import _DejaVuNet
        net = _DejaVuNet(
            n_features=7, n_fault_types=6, hidden=32,
        )
        assert parameter_count(net) < 1_000_000

    def test_hidden_64_still_under_budget(self):
        from evaluation.methods.dejavu import _DejaVuNet
        net = _DejaVuNet(
            n_features=7, n_fault_types=6, hidden=64,
        )
        assert parameter_count(net) < 1_000_000
