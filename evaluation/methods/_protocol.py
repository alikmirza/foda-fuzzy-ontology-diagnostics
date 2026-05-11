"""AST validator that refuses to score methods which peek at the
:class:`~evaluation.extraction.schema_normalizer.CaseGroundTruth`
side channel from inside :meth:`RCAMethod.diagnose`.

Usage from the evaluation harness::

    validate_no_ground_truth_peeking(method)   # raises on violation
    for case in loader.iter_cases():
        out = method.diagnose(normalize_case(case))

The check is intentionally narrow: it only walks the AST of
``type(method).diagnose``. A method that obfuscates access by going
through ``getattr``, ``__dict__``, or a helper function in a separate
module will bypass the validator. The point isn't to be a full taint
tracker — it's to make the *obvious* shape of "I look at
``case.ground_truth.inject_time`` from inside diagnose" loud and
unmissable. Methods that go to the trouble of obfuscation are
self-evidently cheating and the shift-evaluation protocol
(``S(M)`` per the design doc) will catch them empirically.
"""

from __future__ import annotations

import ast
import inspect
import textwrap


class ProtocolViolationError(RuntimeError):
    """Raised when a method's ``diagnose`` body references the ground-
    truth side channel."""


_BANNED_NAMES: frozenset[str] = frozenset({"ground_truth", "CaseGroundTruth"})


def validate_no_ground_truth_peeking(method: object) -> None:
    """Inspect ``type(method).diagnose`` and raise
    :class:`ProtocolViolationError` if its AST references any banned
    name.

    Parameters
    ----------
    method:
        An instance whose class defines ``diagnose``. Bound method or
        unbound — the validator unwraps either.
    """
    cls = type(method) if not isinstance(method, type) else method
    cls_name = cls.__name__
    diagnose = getattr(cls, "diagnose", None)
    if diagnose is None or not callable(diagnose):
        raise ProtocolViolationError(
            f"{cls_name} does not define a diagnose() method — cannot "
            f"validate the protocol contract."
        )

    try:
        source = inspect.getsource(diagnose)
    except (OSError, TypeError) as exc:
        # OSError: source not available (e.g. built-in or REPL-defined).
        # TypeError: object isn't introspectable (rare).
        raise ProtocolViolationError(
            f"{cls_name}.diagnose source is not introspectable "
            f"({exc!r}); cannot validate the protocol contract. Define "
            f"diagnose in a regular module file."
        ) from exc

    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise ProtocolViolationError(
                _violation_message(cls_name, node.id, node.lineno)
            )
        if isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            raise ProtocolViolationError(
                _violation_message(cls_name, node.attr, node.lineno)
            )


def _violation_message(cls_name: str, banned: str, lineno: int) -> str:
    return (
        f"{cls_name}.diagnose references {banned!r} on line {lineno} of "
        f"its source. NormalizedCase.ground_truth is a side channel that "
        f"only the evaluation harness may read — methods must detect "
        f"anomaly onset and root cause from case_window alone. If your "
        f"method legitimately needs the injection time for offline "
        f"prototyping, use evaluation.methods._onset.detect_onset (or "
        f"your own change-point detector) to find it from telemetry."
    )
