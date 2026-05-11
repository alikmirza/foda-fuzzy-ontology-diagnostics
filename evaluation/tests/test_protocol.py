"""Tests for evaluation.methods._protocol — the AST validator.

These tests are the safety-guarantee of the inject_time-removal design:
without them, the "loud-fail when methods peek at ground_truth" promise
in DESIGN_inject_time_removal.md is declared but never proven.

Each ``_*Method`` class below is a fake RCAMethod whose ``diagnose``
body exercises one validator case. They are defined at module level
(rather than inside the test class) because ``inspect.getsource`` —
which the validator calls — requires a real source file and a
discoverable enclosing scope.
"""

from __future__ import annotations

import pytest

from evaluation.methods._protocol import (
    ProtocolViolationError,
    validate_no_ground_truth_peeking,
)


# ---- fixture method classes ----


class _CleanMethod:
    """diagnose() reads only ``case.case_window`` and ``case.services``."""

    def diagnose(self, case):
        df = case.case_window
        svcs = case.services
        return (df, svcs)


class _AttributePeeker:
    """diagnose() reads ``case.ground_truth.inject_time`` — leak via Attribute."""

    def diagnose(self, case):
        leaked = case.ground_truth.inject_time
        return leaked


class _BareNamePeeker:
    """diagnose() references ``CaseGroundTruth`` as a bare Name."""

    def diagnose(self, case):
        # The import sets the binding; the reference on the next line is
        # what the validator catches (Name node with id='CaseGroundTruth').
        from evaluation.extraction.schema_normalizer import CaseGroundTruth
        type_ref = CaseGroundTruth
        return type_ref


class _StaticallyCleanRuntimeBroken:
    """diagnose() raises at runtime but never references the side
    channel. The validator must pass this — it inspects AST only."""

    def diagnose(self, case):
        raise NotImplementedError("method body intentionally unimplemented")


# ---- the test class ----


class TestProtocolValidator:
    """The four-test floor specified in the design review.

    All four must pass for the inject_time-removal safety guarantee to
    hold. Removing any one of these weakens the contract.
    """

    def test_validator_blocks_method_reading_ground_truth_attribute(self):
        with pytest.raises(ProtocolViolationError) as exc_info:
            validate_no_ground_truth_peeking(_AttributePeeker())
        msg = str(exc_info.value)
        # The offending attribute name must appear in the message so a
        # reviewer can localize the leak without rereading the source.
        assert "ground_truth" in msg
        # And the offending class name must be identified.
        assert "_AttributePeeker" in msg
        # And a hint at where in the source the violation was found.
        assert "line" in msg

    def test_validator_blocks_method_importing_CaseGroundTruth(self):
        with pytest.raises(ProtocolViolationError) as exc_info:
            validate_no_ground_truth_peeking(_BareNamePeeker())
        msg = str(exc_info.value)
        assert "CaseGroundTruth" in msg
        assert "_BareNamePeeker" in msg

    def test_validator_passes_clean_method(self):
        # No raise → pass. Returns None per the contract; the call is
        # the assertion.
        result = validate_no_ground_truth_peeking(_CleanMethod())
        assert result is None

    def test_validator_pass_does_not_depend_on_method_runtime_behavior(self):
        # The diagnose() body would raise NotImplementedError if invoked,
        # but the validator must NOT invoke it — purely static AST walk.
        # Therefore validation succeeds even though the method itself is
        # broken at runtime.
        result = validate_no_ground_truth_peeking(
            _StaticallyCleanRuntimeBroken()
        )
        assert result is None
