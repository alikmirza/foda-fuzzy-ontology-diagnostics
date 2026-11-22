"""Call graphs of Online Boutique and Train Ticket, measured from RCAEval RE2 traces.

RE1 ships metrics only. RE2 was collected by the same authors on the same
applications and adds distributed traces (RE2-OB and RE2-TT; RE2-SS has none).
This script reads the trace files straight from the Zenodo archives, without
unpacking them, and counts calls between services:

  span     a span whose parent span, in the same trace, belongs to another
           service: parent service -> span's service.
  rpc      Online Boutique only. Three of its services (ad, cart, shipping) emit
           no spans of their own, so their callers' client spans are the only
           record of those calls. A span named ``hipstershop.<X>Service/<Method>``
           emitted by a service other than <x>service is counted as a call
           from the emitting service to <x>service.

An edge's count is the larger of the two (they count the same calls where both
exist). Counts are kept separately for spans that start before the case's fault
injection ("pre": normal operation) and for all spans. The experiment uses the
edges seen before injection.

What the traces cannot show, and this script does not add: database calls
(spans name a database, not the service that hosts it; cart -> redis is plain
TCP), the Train Ticket gateway ts-ui-dashboard, and services the load generator
never reached.

Usage:
    python3 scripts/extract_re2_call_graphs.py --zips ~/research/rcaeval-tools/RCAEval/data/RE2_zips
Writes results/re2_call_graph_edges.csv and results/re2_call_graph_coverage.csv.
"""
from __future__ import annotations

import argparse
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).resolve().parent.parent / "results"
ENTRY = re.compile(r"^(RE2-(?:OB|TT))/([^/]+)/(\d+)/traces\.csv$")
RPC = re.compile(r"^/?(?:grpc\.)?hipstershop\.(\w+?)Service/")
#: trace service name -> the name RE1's metrics use
RENAME = {"frontendservice": "frontend"}
COLS = ["traceID", "spanID", "serviceName", "operationName", "startTimeMillis", "parentSpanID"]


def case_edges(df: pd.DataFrame, inject_ms: int, with_rpc: bool):
    df = df.assign(pre=df.startTimeMillis.astype("int64") < inject_ms,
                   serviceName=df.serviceName.replace(RENAME))
    parents = df[["traceID", "spanID", "serviceName"]].rename(columns={"spanID": "parentSpanID", "serviceName": "caller"})
    m = df[df.parentSpanID != ""].merge(parents, on=["traceID", "parentSpanID"], how="inner")
    m = m[m.caller != m.serviceName]
    out = {"span": {}, "rpc": {}}
    for pre, g in m.groupby("pre"):
        for (a, b), n in g.groupby(["caller", "serviceName"]).size().items():
            out["span"].setdefault((a, b), [0, 0])[0 if pre else 1] += int(n)
    if with_rpc:
        callee = df.operationName.str.extract(RPC, expand=False).str.lower() + "service"
        r = df.assign(callee=callee.replace(RENAME))
        r = r[r.callee.notna() & (r.callee != r.serviceName)]
        for pre, g in r.groupby("pre"):
            for (a, b), n in g.groupby(["serviceName", "callee"]).size().items():
                out["rpc"].setdefault((a, b), [0, 0])[0 if pre else 1] += int(n)
    return out, set(df.serviceName.unique()), int(len(df)), int(df.traceID.nunique())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zips", type=Path, required=True)
    args = ap.parse_args()
    rows, cover = [], []
    for system, tag in (("RE2-OB", "re1-ob"), ("RE2-TT", "re1-tt")):
        z = zipfile.ZipFile(args.zips.expanduser() / f"{system}.zip")
        entries = sorted(n for n in z.namelist() if ENTRY.match(n))
        assert len(entries) == 90, (system, len(entries))
        pre, total = defaultdict(Counter), defaultdict(Counter)        # kind -> edge -> calls
        cases_pre, cases_all, services, spans, traces = Counter(), Counter(), set(), 0, 0
        for k, name in enumerate(entries, 1):
            inject_ms = int(z.read(name.replace("traces.csv", "inject_time.txt")).strip()) * 1000
            with z.open(name) as f:
                df = pd.read_csv(f, usecols=COLS, dtype=str, keep_default_na=False)
            out, svc, n_spans, n_traces = case_edges(df, inject_ms, with_rpc=system == "RE2-OB")
            services |= svc; spans += n_spans; traces += n_traces
            seen_pre, seen_all = set(), set()
            for kind, edges in out.items():
                for e, (a, b) in edges.items():
                    pre[kind][e] += a; total[kind][e] += a + b
                    if a:
                        seen_pre.add(e)
                    seen_all.add(e)
            cases_pre.update(seen_pre); cases_all.update(seen_all)
            if k % 15 == 0:
                print(f"[{system}] {k}/90 cases", flush=True)
        edges = set(total["span"]) | set(total["rpc"])
        for a, b in sorted(edges):
            rows.append({"system": tag, "source": system, "caller": a, "callee": b,
                         "evidence": "+".join(k for k in ("span", "rpc") if (a, b) in total[k]),
                         "calls_pre": max(pre["span"][(a, b)], pre["rpc"][(a, b)]),
                         "calls_all": max(total["span"][(a, b)], total["rpc"][(a, b)]),
                         "cases_pre": cases_pre[(a, b)], "cases_all": cases_all[(a, b)]})
        nodes = {x for e in edges for x in e}
        cover.append({"system": tag, "source": system, "cases": len(entries), "spans": spans, "traces": traces,
                      "services_with_spans": len(services), "services_in_graph": len(nodes),
                      "edges_all": len(edges), "edges_pre": sum(1 for e in edges if cases_pre[e])})
        print(f"[{system}] services emitting spans: {sorted(services)}", flush=True)
    pd.DataFrame(rows).to_csv(RESULTS / "re2_call_graph_edges.csv", index=False)
    pd.DataFrame(cover).to_csv(RESULTS / "re2_call_graph_coverage.csv", index=False)
    print(pd.DataFrame(cover).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
