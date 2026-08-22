"""Fix 8c closure — worked-example re-derivation from the CORRECTED equations.

Independent of paper/notes/fix8c_rederive.py, which implements the manuscript's
former (mis-transcribed) equations and is retained only as evidence of the
disagreement that raised the STOP.

This script implements §4.4's corrected (2)-(4) and nothing else:

    P(s)  = 1 - prod_t (1 - delta * w(s,t) * C(t))
    C(s) <- clamp_[0,1]( 1 - (1 - H(s)) * (1 - P(s)) )
    C^(0) = H,  terminate on ||C^(k) - C^(k-1)||_inf <= eps

Example: 3-cycle A->B->C->A, all w = 0.7, H = (0.6, 0.3, 0.2), delta = 0.85.

Checks (any failure is a STOP):
  1. fixed point C* = (0.7255, 0.5271, 0.5453) to 4 dp, and the 10 dp values
  2. 14 iterations to eps = 1e-6
  3. rho(J) = 0.3614; Theorem 1 and Theorem 2 bounds both = 0.476
  4. the geometric-mean identity 0.85 * 0.7 * 0.6073 = 0.3614
"""
from __future__ import annotations

import numpy as np

SERVICES = ["A", "B", "C"]
CALLEES = {"A": [("B", 0.7)], "B": [("C", 0.7)], "C": [("A", 0.7)]}
H = {"A": 0.6, "B": 0.3, "C": 0.2}
DELTA, EPS, MAX_ITER = 0.85, 1e-6, 100

EXPECTED_C4 = (0.7255, 0.5271, 0.5453)
EXPECTED_C10 = (0.7254554565, 0.5271243564, 0.5453167505)
EXPECTED_ITERS = 14
EXPECTED_RHO_J = 0.3614
EXPECTED_BOUND = 0.476


def propagate(delta=DELTA, eps=EPS, max_iter=MAX_ITER):
    """Jacobi iteration of corrected eq. (4)."""
    C = dict(H)
    for k in range(1, max_iter + 1):
        nxt = {}
        for s in SERVICES:
            comp = 1.0
            for t, w in CALLEES[s]:
                comp *= 1.0 - delta * w * C[t]
            p = 1.0 - comp
            nxt[s] = min(1.0, max(0.0, 1.0 - (1.0 - H[s]) * (1.0 - p)))
        resid = max(abs(nxt[s] - C[s]) for s in SERVICES)
        C = nxt
        if resid <= eps:
            return C, k, resid
    return C, max_iter, resid


def jacobian(C, delta=DELTA):
    """J_st = (1 - H(s)) * delta * w(s,t) * prod_{u != t}(1 - delta*w(s,u)*C(u))."""
    J = np.zeros((3, 3))
    idx = {s: i for i, s in enumerate(SERVICES)}
    for s in SERVICES:
        for t, w in CALLEES[s]:
            trailing = 1.0
            for u, wu in CALLEES[s]:
                if u != t:
                    trailing *= 1.0 - delta * wu * C[u]
            J[idx[s], idx[t]] = (1.0 - H[s]) * delta * w * trailing
    return J


def main() -> int:
    fails = []
    C, iters, resid = propagate()
    got4 = tuple(round(C[s], 4) for s in SERVICES)
    got10 = tuple(round(C[s], 10) for s in SERVICES)

    print("=== Fix 8c closure — corrected equations ===\n")
    print(f"{'quantity':34s} {'expected':>26s} {'got':>26s}  ok")
    def chk(name, exp, got, ok):
        print(f"{name:34s} {str(exp):>26s} {str(got):>26s}  {'OK' if ok else '*** FAIL ***'}")
        if not ok: fails.append(name)

    chk("C* (4 dp)", EXPECTED_C4, got4, got4 == EXPECTED_C4)
    chk("C* (10 dp)", EXPECTED_C10, got10,
        all(abs(a - b) < 5e-10 for a, b in zip(got10, EXPECTED_C10)))
    chk("iterations to eps=1e-6", EXPECTED_ITERS, iters, iters == EXPECTED_ITERS)

    W = max(sum(w for _, w in CALLEES[s]) for s in SERVICES)          # 0.7
    max_1mH = max(1.0 - H[s] for s in SERVICES)                        # 0.8
    Wt = np.zeros((3, 3)); idx = {s: i for i, s in enumerate(SERVICES)}
    for s in SERVICES:
        for t, w in CALLEES[s]:
            Wt[idx[s], idx[t]] = w
    rho_Wt = max(abs(np.linalg.eigvals(Wt)))
    g_bound = DELTA * max_1mH * W
    l_bound = DELTA * max_1mH * rho_Wt
    J = jacobian(C)
    rho_J = max(abs(np.linalg.eigvals(J)))

    chk("Theorem 1 global bound", EXPECTED_BOUND, round(g_bound, 4), abs(g_bound - EXPECTED_BOUND) < 5e-4)
    chk("Theorem 2 local bound", EXPECTED_BOUND, round(l_bound, 4), abs(l_bound - EXPECTED_BOUND) < 5e-4)
    chk("true rho(J)", EXPECTED_RHO_J, round(rho_J, 4), abs(rho_J - EXPECTED_RHO_J) < 5e-4)

    # geometric-mean identity: rho(J) = delta * w * geomean_s(1 - H(s))
    geo = float(np.prod([1.0 - H[s] for s in SERVICES]) ** (1.0 / 3.0))
    ident = DELTA * 0.7 * geo
    print()
    print(f"geometric mean of (1-H) over the cycle = (0.4*0.7*0.8)^(1/3) = {geo:.4f}")
    chk("identity delta*w*geomean", round(rho_J, 4), round(ident, 4), abs(ident - rho_J) < 5e-4)

    n_from_rhoJ = np.log(EPS) / np.log(rho_J)
    n_from_bound = np.log(EPS) / np.log(g_bound)
    print(f"\nN(1e-6) from rho(J)      = {n_from_rhoJ:.1f}  -> ceil {int(np.ceil(n_from_rhoJ))}"
          f"   (observed {iters})")
    print(f"N(1e-6) from the 0.476 bound = {n_from_bound:.1f} -> ceil {int(np.ceil(n_from_bound))}")
    chk("ceil(N from rho(J)) == observed", iters, int(np.ceil(n_from_rhoJ)),
        int(np.ceil(n_from_rhoJ)) == iters)

    print()
    if fails:
        print("*** STOP — DIGIT DISAGREEMENT: " + ", ".join(fails) + " ***")
        return 1
    print("ALL CHECKS PASS — Fix 8c closed, no STOP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
