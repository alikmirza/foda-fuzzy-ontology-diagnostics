"""Pytest-wide configuration for the evaluation suite.

Pins ``torch`` to single-threaded execution during tests. The unit
tests run many small forward/backward passes on tiny tensors;
multi-threaded BLAS on M-series CPUs spends more time in thread
contention than in compute, slowing the suite by an order of
magnitude. The standalone harnesses (`evaluate_dejavu.py`, etc.) do
not import this conftest and continue to use torch's default thread
count for real RE1-OB runs.
"""

from __future__ import annotations

try:
    import torch
    torch.set_num_threads(1)
except ImportError:  # torch is an optional baseline dep
    pass
