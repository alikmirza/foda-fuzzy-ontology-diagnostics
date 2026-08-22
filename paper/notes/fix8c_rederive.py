"""Fix 8c: independent re-derivation of the 4.5 worked example.
Written from the equations as printed in section4_fcp_algorithm.md (2), (4).
No reuse of AICT numbers. Ground truth to check against: C* = (0.7255, 0.5271, 0.5453),
converging in 14 steps; empirical rate ~0.43; Thm2 bound 0.626; Thm1 bound 0.745.
"""
from fractions import Fraction
import math

# 3-cycle A->B->C->A, all w = 0.7, H = (0.6, 0.3, 0.2), delta = 0.85
NAMES = ["A", "B", "C"]
callees = {0: [1], 1: [2], 2: [0]}      # s -> list of t with edge (s,t)
w = {(0, 1): 0.7, (1, 2): 0.7, (2, 0): 0.7}
H = [0.6, 0.3, 0.2]
delta = 0.85
EPS = 1e-6
MAX_ITER = 100

def P(s, C):
    prod = 1.0
    for t in callees[s]:
        prod *= (1.0 - w[(s, t)] * C[t])
    return 1.0 - prod

def step(C):
    return [(1 - delta) * C[s] + delta * (1 - (1 - H[s]) * (1 - P(s, C)))
            for s in range(3)]

C = list(H)                              # C^(0)(v) = H(v)
hist = [list(C)]
residuals = []
k = 0
while k < MAX_ITER:
    Cn = step(C)
    r = max(abs(Cn[i] - C[i]) for i in range(3))
    residuals.append(r)
    C = Cn
    hist.append(list(C))
    k += 1
    if r <= EPS:
        break

print(f"iterations to residual <= {EPS:g}: {k}")
print("fixed point:", ", ".join(f"{v:.10f}" for v in C))
print("rounded 4dp:", tuple(round(v, 4) for v in C))

TARGET = (0.7255, 0.5271, 0.5453)
got = tuple(round(v, 4) for v in C)
print("matches asserted C*:", got == TARGET, "| asserted:", TARGET)

# empirical asymptotic rate = ratio of successive residuals near convergence
tail = [residuals[i+1] / residuals[i] for i in range(len(residuals) - 1) if residuals[i] > 0]
print("empirical rate (last 5 residual ratios):", [f"{x:.4f}" for x in tail[-5:]])

# Theorem 1 global bound: rho = 1 - delta*(1 - W), W = max_s sum_t w(s,t) = 0.7
W = max(sum(w[(s, t)] for t in callees[s]) for s in range(3))
rho_global = 1 - delta * (1 - W)
print(f"W = {W}; Theorem 1 global bound rho = {rho_global:.4f}")

# Theorem 2 local bound: (1-delta) + delta * max_s(1-H(s)) * rho(Wtilde)
# rho(Wtilde) for the uniform 3-cycle with weight 0.7 is 0.7 (eigenvalues 0.7*cube roots of unity)
rho_Wt = 0.7
rho_loc = (1 - delta) + delta * max(1 - h for h in H) * rho_Wt
print(f"Theorem 2 local bound rho_loc <= {rho_loc:.4f}")

# true local rate: spectral radius of the Jacobian at C*
# J_st = (1-delta)*1[s=t] + delta*(1-H(s)) * dP(s)/dC(t)
# dP(s)/dC(t) = w(s,t) * prod_{u != t} (1 - w(s,u) C(u)) ; single callee => = w(s,t)
J = [[0.0] * 3 for _ in range(3)]
for s in range(3):
    J[s][s] += (1 - delta)
    for t in callees[s]:
        J[s][t] += delta * (1 - H[s]) * w[(s, t)]
# circulant-ish 3x3: get spectral radius by power iteration on |eigenvalues| via numpy-free char poly
# product of the three off-diagonal couplings gives the cycle term
prod_off = 1.0
for s in range(3):
    for t in callees[s]:
        prod_off *= J[s][t]
# eigenvalues of (1-delta)I + N where N is the cycle matrix: (1-delta) + cbrt(prod_off)*omega^k
cb = prod_off ** (1/3)
eigs = [complex((1 - delta) + cb * math.cos(2*math.pi*k/3), cb * math.sin(2*math.pi*k/3)) for k in range(3)]
print("true rho(J) =", f"{max(abs(e) for e in eigs):.4f}")

# iteration count implied by each bound at eps = 1e-6
for label, r in (("Thm1 global 0.745", rho_global), ("Thm2 local 0.626", rho_loc)):
    if 0 < r < 1:
        print(f"N(eps) from {label}: {math.log(EPS)/math.log(r):.1f}")
    else:
        print(f"N(eps) from {label}: DIVERGES (rho = {r})")
# and the W=1 case the Corollary currently claims
r1 = 0.15 + 0.85 * 1.0
print(f"N(eps) at W_eff = 1, rho = {r1}: ", "DIVERGES" if r1 >= 1 else math.log(EPS)/math.log(r1))
