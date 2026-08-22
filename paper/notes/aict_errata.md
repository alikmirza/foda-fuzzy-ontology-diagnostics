# AICT 2026 conference version — errata assessment

**Status: AUTHOR-ONLY — PENDING.** Nothing here may be filled in without reading
the AICT manuscript. Do not infer what it printed from the journal draft.

## Why this file exists

The method paper's §4.4 printed a propagation update that does not match the
implementation (see `DEVIATIONS.md` § "Propagation equations: manuscript
mis-transcription", and `STOP_propagation_equation_finding.md`). δ was shown as a
convex mixing weight between iterates rather than as a per-edge attenuator inside
the Noisy-OR product, and a `(1 − δ)·C_prev(s)` term appeared that the code does
not have.

The preliminary 6-page AICT 2026 version, currently under review, presents the
same algorithm. **If it carries the same transcription, it carries the same
error**, and that has to be handled through the conference's own channel rather
than silently corrected in the journal paper.

## To be completed by the author

| item | finding |
|---|---|
| Equations as printed in the AICT manuscript (quote verbatim, with equation numbers) | *pending author check* |
| Does the AICT form match the implementation? | *pending* |
| If not: which of its stated results depend on the printed form? (its convergence argument, its iteration-count bound, its worked example) | *pending* |
| Corrected form to be substituted | P(s) = 1 − ∏_t (1 − δ · w(s,t) · C(t)); C(s) = clamp(1 − (1 − H(s))·(1 − P(s))) |
| Required action | erratum · camera-ready correction · none — *pending* |
| Decision and date | *pending* |

## Constraints on whichever route is chosen

- The journal paper does **not** cite AICT (Option C); §1 carries a disclosure
  sentence instead. So the journal paper is not itself asserting the AICT
  equations, and a correction there is not blocked by this file.
- If AICT is still in review, a camera-ready correction is the cheaper route than
  a post-publication erratum, which argues for checking this promptly rather than
  after acceptance.
- If AICT is accepted before journal submission, the ruling upgrades the
  disclosure sentence to a proceedings citation — in which case the cited version
  must be the corrected one.
