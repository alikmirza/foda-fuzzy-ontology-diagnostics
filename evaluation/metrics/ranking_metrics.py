"""Standard ranking metrics for top-k root-cause localization.

Both metrics treat the input list as already ranked best-first by the
caller. Ties are resolved by the caller's ordering, with one exception:
when two entries share the same score and one of them is the ground
truth, the ground truth is given the *worst* (largest) rank among the
tied group. This is the conservative choice and prevents a method from
"winning" AC@1 just by happening to list the right service first when
its score is no higher than several alternatives.
"""

from __future__ import annotations

from typing import Sequence


def _ground_truth_rank(
    ranked_list: Sequence[tuple[str, float]],
    ground_truth: str,
) -> int | None:
    """Return the 1-indexed rank of `ground_truth`, or None if absent.

    With ties (entries sharing the ground truth's score), the ground
    truth is assigned the worst rank in the tied block.
    """
    gt_index: int | None = None
    for i, (name, _) in enumerate(ranked_list):
        if name == ground_truth:
            gt_index = i
            break
    if gt_index is None:
        return None

    gt_score = ranked_list[gt_index][1]
    worst_index = gt_index
    for j in range(gt_index + 1, len(ranked_list)):
        if ranked_list[j][1] == gt_score:
            worst_index = j
        else:
            break
    return worst_index + 1


def accuracy_at_k(
    ranked_list: Sequence[tuple[str, float]],
    ground_truth: str,
    k: int,
) -> bool:
    """True iff `ground_truth` appears in the top `k` of `ranked_list`.

    `k` must be a positive integer. An empty `ranked_list` or a missing
    `ground_truth` returns False.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    rank = _ground_truth_rank(ranked_list, ground_truth)
    if rank is None:
        return False
    return rank <= k


def mean_reciprocal_rank(
    ranked_list: Sequence[tuple[str, float]],
    ground_truth: str,
) -> float:
    """Reciprocal rank of `ground_truth` in `ranked_list`.

    Returns 1/rank using 1-indexed positions, or 0.0 if the ground truth
    is absent or the list is empty. (Named `mean_reciprocal_rank` for
    consistency with how it is averaged across cases at the experiment
    level — for a single case this is just the reciprocal rank.)
    """
    rank = _ground_truth_rank(ranked_list, ground_truth)
    if rank is None:
        return 0.0
    return 1.0 / rank
