"""DejaVu (Li, Chen, et al. — FSE 2022, "Actionable and Interpretable
Fault Localization for Recurring Failures in Online Service Systems")
refactored for the inject_time-clean :class:`NormalizedCase` contract.

DejaVu is the first method in this evaluation suite that requires a
**training phase**. Historical labeled failure cases are used to train
a small neural classifier that, given a new case's bounded telemetry,
predicts ``(failure_unit, failure_type)`` jointly. Onset detection is
absorbed into the model's temporal encoder — there is no shared
``_onset.detect_onset`` call.

The :class:`RCAMethod` base class exposes a no-op ``train`` by default;
DejaVu overrides it. The protocol validator
(:func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`)
inspects only ``diagnose``, so ``train`` is exempt by name — training
*needs* labels, that is the whole point. ``diagnose`` at inference time
remains forbidden from reading ``ground_truth``.

Architecture (paper-faithful, simplified for tractability — see
``DEVIATIONS.md`` § "DejaVu adapter" for the full list):

1. **Per-service temporal encoder.** Two stacked 1D convolutions
   (kernel 5) over the ``F``-channel × ``T``-step tensor for each
   service, followed by adaptive average pooling, producing a single
   ``hidden``-dimensional embedding per service.
2. **Service-level self-attention.** Single-head scaled-dot-product
   attention over services. The post-attention attention matrix is the
   "neural attention attribution" surfaced in the explanation chain
   (and saved to ``results/dejavu_attention_samples.json`` for paper-
   level inspection of correct vs. incorrect cases).
3. **Two heads.** A per-service ``unit_logits`` linear (predicts which
   service is the failure unit), and a global ``type_logits`` linear
   on the mean-pooled service embedding (predicts which fault type).
4. **Joint loss.** Cross-entropy on ``unit_logits`` plus
   ``type_loss_weight × `` cross-entropy on ``type_logits``.

Service vocabulary is the **union** of services seen across training
cases. Cases that supply only a subset use a service mask so the
attention and unit head do not attribute to absent services. Cases
whose ground-truth root-cause service is outside the vocabulary are
dropped from training with a warning; they cannot teach the unit head
a class it doesn't have.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover - dependency-installed env
    raise ImportError(
        "DejaVu requires PyTorch. Install with "
        "`pip install -e \"evaluation[baselines]\"`."
    ) from exc

from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    CausalLink,
    DiagnosticOutput,
    ExplanationAtom,
)
from ..extraction.schema_normalizer import (
    DEFAULT_WINDOW_SECONDS,
    NormalizedCase,
    normalize_case,
)
from .base import RCAMethod


_FEATURE_PRIORITY: tuple[str, ...] = (
    "latency",
    "traffic",
    "error",
    "cpu",
    "mem",
    "disk",
    "net",
)

_FAULT_TYPE_VOCAB: tuple[str, ...] = (
    "cpu", "mem", "disk", "delay", "loss", "unknown",
)


# ---- per-case tensor construction ----


def _case_to_tensor(
    case: NormalizedCase,
    service_vocab: list[str],
    n_features: int = len(_FEATURE_PRIORITY),
) -> tuple[np.ndarray, np.ndarray]:
    """Project a normalized case onto a ``(S, F, T)`` tensor + ``(S,)`` mask.

    ``S`` is the size of the global service vocabulary; ``F`` is the
    canonical feature count; ``T`` is the number of rows in
    ``case_window``. Per-column standardization (z-score with the
    column's own statistics) normalizes the heterogeneous scales of
    latency / traffic / cpu / mem. Constant columns become zero. The
    mask is 1 for services present in the case, 0 otherwise.
    """
    df = case.case_window
    T = len(df)
    S = len(service_vocab)
    x = np.zeros((S, n_features, T), dtype=np.float32)
    mask = np.zeros(S, dtype=np.float32)
    for si, svc in enumerate(service_vocab):
        if svc not in case.services:
            continue
        mask[si] = 1.0
        for fi, feat in enumerate(_FEATURE_PRIORITY):
            col = f"{svc}_{feat}"
            if col not in df.columns:
                continue
            v = df[col].to_numpy(dtype=np.float32)
            if not np.isfinite(v).all():
                v = np.where(np.isfinite(v), v, 0.0).astype(np.float32)
            sd = float(v.std())
            if sd > 1e-12:
                v = (v - float(v.mean())) / sd
            else:
                v = v - float(v.mean())
            x[si, fi] = v
    return x, mask


# ---- neural net ----


class _TemporalEncoder(nn.Module):
    """Two-layer Conv1d + GELU + adaptive average pool over time."""

    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_features, hidden, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(hidden, hidden, kernel_size=5, padding=2),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B*S, F, T) → (B*S, hidden)
        return self.net(x).squeeze(-1)


class _ServiceAttention(nn.Module):
    """Single-head scaled-dot-product self-attention over services.

    Returns ``(h_out, attn)`` where ``attn`` is the ``(B, S, S)`` row-
    stochastic attention matrix surfaced as the model's interpretability
    output.
    """

    def __init__(self, hidden: int) -> None:
        super().__init__()
        self.q = nn.Linear(hidden, hidden)
        self.k = nn.Linear(hidden, hidden)
        self.v = nn.Linear(hidden, hidden)
        self.scale = hidden ** -0.5

    def forward(
        self, h: torch.Tensor, mask: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # h: (B, S, H), mask: (B, S) — 1.0 where service is present.
        Q, K, V = self.q(h), self.k(h), self.v(h)
        scores = (Q @ K.transpose(-2, -1)) * self.scale  # (B, S, S)
        if mask is not None:
            key_mask = mask.unsqueeze(1) == 0  # (B, 1, S) bool
            # If a batch element has zero present keys, softmax over all
            # -inf yields nan. Detect this and feed a uniform 0 instead;
            # the row-multiplication by ``mask.unsqueeze(-1)`` below will
            # zero out the corresponding attention rows anyway.
            scores = scores.masked_fill(key_mask, float("-inf"))
            any_key_present = mask.sum(dim=1) > 0  # (B,) bool
            sanitized = torch.where(
                any_key_present.view(-1, 1, 1),
                scores,
                torch.zeros_like(scores),
            )
            attn = F.softmax(sanitized, dim=-1)
            attn = attn * mask.unsqueeze(-1)
        else:
            attn = F.softmax(scores, dim=-1)
        out = attn @ V
        return h + out, attn


class _DejaVuNet(nn.Module):
    """DejaVu classifier: temporal encoder → service attention → two heads."""

    def __init__(
        self,
        n_features: int,
        n_fault_types: int,
        hidden: int,
    ) -> None:
        super().__init__()
        self.encoder = _TemporalEncoder(n_features, hidden)
        self.attn = _ServiceAttention(hidden)
        self.unit_head = nn.Linear(hidden, 1)
        self.type_head = nn.Linear(hidden, n_fault_types)

    def forward(
        self, x: torch.Tensor, mask: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        B, S, Fc, T = x.shape
        h = self.encoder(x.reshape(B * S, Fc, T)).reshape(B, S, -1)
        h, attn = self.attn(h, mask=mask)
        unit_logits = self.unit_head(h).squeeze(-1)  # (B, S)
        if mask is not None:
            unit_logits = unit_logits.masked_fill(mask == 0, float("-inf"))
            # Mean-pool only over present services.
            denom = mask.sum(dim=1, keepdim=True).clamp(min=1.0)
            pooled = (h * mask.unsqueeze(-1)).sum(dim=1) / denom
        else:
            pooled = h.mean(dim=1)
        type_logits = self.type_head(pooled)
        return unit_logits, type_logits, attn


# ---- DejaVuMethod ----


class DejaVuMethod(RCAMethod):
    """DejaVu on :class:`NormalizedCase`.

    Parameters
    ----------
    hidden:
        Embedding and attention dimensionality. Default 32 (≈ 14k
        parameters with 12 services × 7 features — comfortably under
        the 1 M budget the brief sets).
    epochs:
        Training epochs. 80 is enough on RE1-OB at ~100 cases/fold; the
        small classifier saturates well before then on the
        cross-entropy losses.
    lr, weight_decay:
        Adam hyperparameters.
    batch_size:
        Mini-batch size in training. ``len(training_cases)`` is the
        upper bound — on small folds the implementation degenerates to
        full-batch.
    type_loss_weight:
        Coefficient on the ``failure_type`` cross-entropy term; the
        primary objective is ``failure_unit`` (the service rank), so
        we hold the type loss at half weight.
    window_seconds:
        Passed to :func:`normalize_case` when ``diagnose`` is called
        with a :class:`BenchmarkCase`.
    seed:
        Seed for ``torch`` / ``numpy``; the cross-validation harness
        seeds folds independently.
    device:
        ``"cpu"`` (default) or ``"cuda"`` / ``"mps"``. The RE1-OB
        validation runs entirely on CPU within the brief's 2-hour
        budget.
    """

    name = "dejavu"

    def __init__(
        self,
        hidden: int = 32,
        epochs: int = 80,
        lr: float = 1e-3,
        batch_size: int = 16,
        weight_decay: float = 1e-4,
        type_loss_weight: float = 0.5,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        seed: int = 0,
        device: str = "cpu",
    ) -> None:
        if hidden < 4:
            raise ValueError(f"hidden must be >= 4, got {hidden}")
        if epochs < 1:
            raise ValueError(f"epochs must be >= 1, got {epochs}")
        if lr <= 0.0:
            raise ValueError(f"lr must be > 0, got {lr}")
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        if weight_decay < 0.0:
            raise ValueError(
                f"weight_decay must be >= 0, got {weight_decay}"
            )
        if not 0.0 <= type_loss_weight <= 10.0:
            raise ValueError(
                f"type_loss_weight must be in [0, 10], got {type_loss_weight}"
            )
        if window_seconds <= 0.0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.weight_decay = weight_decay
        self.type_loss_weight = type_loss_weight
        self.window_seconds = window_seconds
        self.seed = seed
        self.device = torch.device(device)
        # Set after train()
        self.services: Optional[list[str]] = None
        self.fault_types: tuple[str, ...] = _FAULT_TYPE_VOCAB
        self.net: Optional[_DejaVuNet] = None

    # ---- training ----

    def train(self, training_cases: list[NormalizedCase]) -> None:
        if not training_cases:
            raise ValueError(
                "DejaVu.train called with empty training_cases — at least "
                "one labeled case is required"
            )
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        # Service vocabulary = union of services across training cases.
        services: set[str] = set()
        for nc in training_cases:
            services.update(nc.services)
        self.services = sorted(services)
        if not self.services:
            raise ValueError(
                "DejaVu.train: no recognizable services across any "
                "training case"
            )

        Xs: list[np.ndarray] = []
        Ms: list[np.ndarray] = []
        unit_labels: list[int] = []
        type_labels: list[int] = []
        for nc in training_cases:
            rc = nc.ground_truth.root_cause_service
            if rc not in self.services:
                # Cannot teach a class the head doesn't have. Drop.
                continue
            x, m = _case_to_tensor(nc, self.services)
            Xs.append(x)
            Ms.append(m)
            unit_labels.append(self.services.index(rc))
            ft = (nc.ground_truth.fault_type or "unknown").lower()
            if ft not in self.fault_types:
                ft = "unknown"
            type_labels.append(self.fault_types.index(ft))

        if not Xs:
            raise ValueError(
                "DejaVu.train: every training case's root cause is "
                "outside the service vocabulary; nothing to train on"
            )

        X = torch.from_numpy(np.stack(Xs)).to(self.device)
        M = torch.from_numpy(np.stack(Ms)).to(self.device)
        Yu = torch.tensor(unit_labels, dtype=torch.long, device=self.device)
        Yt = torch.tensor(type_labels, dtype=torch.long, device=self.device)

        self.net = _DejaVuNet(
            n_features=len(_FEATURE_PRIORITY),
            n_fault_types=len(self.fault_types),
            hidden=self.hidden,
        ).to(self.device)

        opt = torch.optim.Adam(
            self.net.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )

        n = X.shape[0]
        bs = max(1, min(self.batch_size, n))
        idx = np.arange(n)
        self.net.train()
        for _ in range(self.epochs):
            np.random.shuffle(idx)
            for s in range(0, n, bs):
                batch = idx[s : s + bs]
                xb = X[batch]
                mb = M[batch]
                yub = Yu[batch]
                ytb = Yt[batch]
                unit_logits, type_logits, _ = self.net(xb, mask=mb)
                loss_u = F.cross_entropy(unit_logits, yub)
                loss_t = F.cross_entropy(type_logits, ytb)
                loss = loss_u + self.type_loss_weight * loss_t
                opt.zero_grad()
                loss.backward()
                opt.step()
        self.net.eval()

    # ---- inference ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run DejaVu on a pre-built :class:`NormalizedCase`.

        Requires :meth:`train` to have been called first — DejaVu cannot
        produce a diagnosis without a fitted classifier.
        """
        t0 = time.perf_counter()
        if self.net is None or self.services is None:
            raise RuntimeError(
                "DejaVu.diagnose called before train(); a fitted "
                "classifier is required"
            )

        x, m = _case_to_tensor(norm, self.services)
        xb = torch.from_numpy(x[None]).to(self.device)
        mb = torch.from_numpy(m[None]).to(self.device)
        with torch.no_grad():
            unit_logits, type_logits, attn = self.net(xb, mask=mb)
        unit_logits = unit_logits[0].cpu().numpy()  # (S,)
        type_probs = (
            F.softmax(type_logits[0], dim=-1).cpu().numpy()
        )  # (n_fault_types,)
        attn = attn[0].cpu().numpy()  # (S, S)

        # Build ranked list over services in the vocabulary.
        # Mask absent services to -inf via the head's own masking;
        # surface them at the tail with score 0 for downstream metrics.
        present_pairs: list[tuple[str, float]] = []
        absent_pairs: list[tuple[str, float]] = []
        # Softmax over present services for a probability-like score.
        present_idx = [i for i, mi in enumerate(m) if mi > 0]
        if present_idx:
            logits_present = unit_logits[present_idx]
            # Stable softmax.
            logits_present = logits_present - logits_present.max()
            probs = np.exp(logits_present)
            probs = probs / probs.sum() if probs.sum() > 0 else probs
            for i, p in zip(present_idx, probs):
                present_pairs.append((self.services[i], float(p)))
        for i, svc in enumerate(self.services):
            if m[i] == 0:
                absent_pairs.append((svc, 0.0))

        ranked = sorted(
            present_pairs, key=lambda kv: kv[1], reverse=True
        ) + absent_pairs

        # Confidence: top-1 minus top-2 softmax probability mass.
        if len(present_pairs) >= 2:
            sorted_probs = sorted(
                (p for _, p in present_pairs), reverse=True
            )
            confidence = float(max(0.0, min(1.0, sorted_probs[0])))
        elif len(present_pairs) == 1:
            confidence = float(present_pairs[0][1])
        else:
            confidence = 0.0

        type_idx = int(np.argmax(type_probs))
        predicted_fault_type = self.fault_types[type_idx]

        explanation = _build_dejavu_explanation(
            ranked=ranked,
            predicted_fault_type=predicted_fault_type,
            type_probs=type_probs,
            fault_types=self.fault_types,
            attention=attn,
            services=self.services,
            present_mask=m,
            top_k=3,
        )

        raw = {
            "predicted_failure_unit": ranked[0][0] if ranked else None,
            "predicted_failure_type": predicted_fault_type,
            "type_probs": {
                self.fault_types[i]: float(type_probs[i])
                for i in range(len(self.fault_types))
            },
            "attention": attn.tolist(),
            "service_vocab": list(self.services),
            "present_mask": m.tolist(),
        }
        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=raw,
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )


# ---- explanation chain ----


def _build_dejavu_explanation(
    ranked: list[tuple[str, float]],
    predicted_fault_type: str,
    type_probs: np.ndarray,
    fault_types: tuple[str, ...],
    attention: np.ndarray,
    services: list[str],
    present_mask: np.ndarray,
    top_k: int,
) -> CanonicalExplanation:
    """Predicted-failure-type-rooted graph with attention-attributed
    service atoms.

    * One atom per top-K predicted failure unit (with ``ontology_class``
      derived from the predicted failure type).
    * One atom for the predicted failure type itself.
    * Causal links between each failure-unit atom and the most-
      attended services by the attention matrix, with
      ``relation_type="neural-attention-attribution"``.
    """
    explanation = CanonicalExplanation()
    type_idx = int(np.argmax(type_probs))
    type_membership = float(np.clip(type_probs[type_idx], 0.0, 1.0))
    type_atom = ExplanationAtom(
        text=(
            f"predicted failure type: {predicted_fault_type} "
            f"(p={type_probs[type_idx]:.3f})"
        ),
        ontology_class=f"foda:FailureType/{predicted_fault_type}",
        fuzzy_membership=type_membership,
    )
    explanation.add_atom(type_atom)

    head = [(s, sc) for s, sc in ranked[:top_k] if sc > 0.0]
    if not head:
        return explanation

    # Map service → vocab index for attention lookup.
    svc_to_idx = {s: i for i, s in enumerate(services)}
    for service, score in head:
        atom = ExplanationAtom(
            text=(
                f"predicted failure unit: {service} "
                f"(p={score:.3f}, type={predicted_fault_type})"
            ),
            ontology_class=f"foda:Service/{service}",
            fuzzy_membership=float(np.clip(score, 0.0, 1.0)),
        )
        explanation.add_atom(atom)
        # Predicted type → predicted unit edge.
        explanation.add_link(
            CausalLink(
                source_atom_id=type_atom.id,
                target_atom_id=atom.id,
                weight=float(np.clip(score, 0.0, 1.0)),
                relation_type="predicted-failure-unit",
            )
        )
        # Attention attribution: pick top-3 attended services (excluding self).
        if service in svc_to_idx:
            si = svc_to_idx[service]
            attn_row = attention[si].copy()
            attn_row[si] = -1.0
            # Mask absent services so they don't appear as attended.
            attn_row = np.where(present_mask > 0, attn_row, -1.0)
            top_attn_idx = np.argsort(-attn_row)[:3]
            for ai in top_attn_idx:
                w = float(attn_row[ai])
                if w <= 0.0:
                    continue
                attended_svc = services[ai]
                attended_atom = ExplanationAtom(
                    text=(
                        f"attended: {attended_svc} "
                        f"(α={w:.3f} from {service})"
                    ),
                    ontology_class=f"foda:Service/{attended_svc}",
                    fuzzy_membership=float(np.clip(w, 0.0, 1.0)),
                )
                explanation.add_atom(attended_atom)
                explanation.add_link(
                    CausalLink(
                        source_atom_id=atom.id,
                        target_atom_id=attended_atom.id,
                        weight=float(np.clip(w, 0.0, 1.0)),
                        relation_type="neural-attention-attribution",
                    )
                )
    return explanation


# ---- utility for harness: model size ----


def parameter_count(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters()))
