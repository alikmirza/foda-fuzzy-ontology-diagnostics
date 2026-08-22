import math
NAMES=["A","B","C"]; callees={0:[1],1:[2],2:[0]}
w={(0,1):0.7,(1,2):0.7,(2,0):0.7}; H=[0.6,0.3,0.2]; delta=0.85
TARGET=(0.7255,0.5271,0.5453)

def P(s,C):
    p=1.0
    for t in callees[s]: p*= (1.0-w[(s,t)]*C[t])
    return 1.0-p

def run(stepfn,label):
    C=list(H); res=[]
    for k in range(1,201):
        Cn=stepfn(C); r=max(abs(Cn[i]-C[i]) for i in range(3)); res.append(r); C=Cn
        if r<=1e-6: break
    got=tuple(round(v,4) for v in C)
    ratios=[res[i+1]/res[i] for i in range(len(res)-1) if res[i]>0]
    rate=ratios[-1] if ratios else float('nan')
    print(f"{label:52s} iters={k:3d} C*={got}  rate={rate:.4f}  MATCH={got==TARGET}")
    return C,k,rate

# (4) exactly as printed in the manuscript: damping anchored to previous iterate C
run(lambda C:[(1-delta)*C[s]+delta*(1-(1-H[s])*(1-P(s,C))) for s in range(3)],
    "printed eq (4): (1-d)*C(s) + d*[1-(1-H)(1-P)]")

# (3) exactly as printed: no H term at all
run(lambda C:[(1-delta)*C[s]+delta*P(s,C) for s in range(3)],
    "printed eq (3): (1-d)*C(s) + d*[1-prod(1-wC)]")

# H-anchored variant: damping anchored to LOCAL EVIDENCE H
Cstar,iters,rate = run(lambda C:[(1-delta)*H[s]+delta*(1-(1-H[s])*(1-P(s,C))) for s in range(3)],
    "H-anchored:     (1-d)*H(s) + d*[1-(1-H)(1-P)]")

print()
print("H-anchored fixed point to 10dp:", ", ".join(f"{v:.10f}" for v in Cstar))
print("asserted C* in manuscript      :", TARGET)

# analytic spectral radius of the H-anchored Jacobian on the 3-cycle
prod=1.0
for s in range(3):
    for t in callees[s]:
        prod *= delta*(1-H[s])*w[(s,t)]
rho_true=prod**(1/3)
print(f"\nH-anchored Jacobian rho(J) = {rho_true:.4f}")
print(f"  -> N(1e-6) = log(1e-6)/log(rho) = {math.log(1e-6)/math.log(rho_true):.1f} iterations")
print(f"  geometric factor excluding delta = {(rho_true/delta):.4f}   (manuscript reports 'empirical rate ~0.43')")

# correct global Lipschitz bound for the H-anchored operator
W=max(sum(w[(s,t)] for t in callees[s]) for s in range(3))
print(f"\ncorrect global bound for H-anchored T: rho <= delta*max(1-H)*W = {delta*max(1-h for h in H)*W:.4f}")
print(f"  at W=1 (full budget):               rho <= delta*max(1-H)   = {delta*max(1-h for h in H):.4f}  (<1: no boundary case)")
print(f"  worst case H=0 everywhere, W=1:     rho <= delta            = {delta:.4f}  (<1: still a contraction)")
print(f"\nmanuscript Theorem 1 bound 1-delta*(1-W) with W=0.7: {1-delta*(1-W):.4f}")

print("\n=== additional variant: delta INSIDE the product (python adapter docstring) ===")
def P_din(s,C):
    p=1.0
    for t in callees[s]: p*=(1.0-w[(s,t)]*C[t]*delta)
    return 1.0-p
run(lambda C:[1-(1-H[s])*(1-P_din(s,C)) for s in range(3)],
    "docstring: C = 1-(1-H)*prod(1-w*C*d)   [no (1-d) term]")
