"""Kennzahlen, Urteil und die Experimente der Demo (Verteilungen über feste Netze, Kreiswahlen im Vergleich, Startfluss, Schranke, Skalierung gegen SSP, Kapazitäten, Negativkontrolle).
Alles ganzzahlig gerechnet; Prozente entstehen erst bei der Ausgabe."""

from dataclasses import dataclass
from functools import lru_cache
from statistics import mean, median

import numpy as np

import cyc_algorithm as cy
import cyc_constants as C
import cyc_edmonds_karp as ek
import cyc_scenario as sc
import cyc_ssp as ssp

K_SUPPLY, K_LANE_IN, K_THROUGHPUT, K_LANE_OUT, K_DEMAND = sc.K_SUPPLY, sc.K_LANE_IN, sc.K_THROUGHPUT, sc.K_LANE_OUT, sc.K_DEMAND
STAGE_KINDS = (K_SUPPLY, K_LANE_IN, K_THROUGHPUT, K_LANE_OUT)


@dataclass(frozen=True)
class Analysis:
    net: sc.Net
    result: cy.Result            # mit der gewählten Kreiswahl und dem gewählten Startfluss
    optimum: ssp.Result          # Successive Shortest Paths, größter Fluss (die Messlatte)
    start: ek.Result             # kostenblinder Startfluss (Edmonds-Karp)
    start_flow: tuple
    max_value: int
    demand: int
    stage_caps: dict
    selection: str
    rule: str


def _demand(net):
    return sum(c for _, _, c, _, kind in net.arcs if kind == K_DEMAND)


def _stage_caps(net, cut_arcs):
    caps = {}
    for i in cut_arcs:
        kind = net.arcs[i][4]
        caps[kind] = caps.get(kind, 0) + net.arcs[i][2]
    return caps


def pct(numerator, denominator, digits=1):
    return round(100 * numerator / denominator, digits) if denominator else 0.0


def analyse(net, selection=C.DEFAULT_SELECTION, rule=C.DEFAULT_RULE):
    e = ek.max_flow(net, rule)
    f0 = e.flows[-1]
    res = cy.cancel(net, f0, selection)
    opt = ssp.ssp(net, "dijkstra", None, keep_trace=False)
    return Analysis(net, res, opt, e, f0, e.value, _demand(net) if net.logistic else 0, _stage_caps(net, e.cut_arcs), selection, rule)


def curve_points(a):
    """Menge-Kosten-Ebene: SSP-Kurve (Menge, Gesamtkosten) nach jeder Runde ab (0, 0), Startpunkt und Endpunkt von Cycle-Canceling bei fester Menge."""
    ssp_curve = [(0, 0)] + [(r.value, r.total) for r in a.optimum.rounds]
    return ssp_curve, (a.max_value, a.result.start_total), (a.max_value, a.result.total)


def verdict(a):
    """(Stufe, Code, Daten): 'optimal' = kostenminimal, 'nothing' = der Startfluss war schon billigst, 'wrong' = ein negativer Kreis bleibt übrig, 'disconnected' = gar nichts kommt an."""
    res = a.result
    its = res.iterations
    savings = [i.saving for i in its]
    data = {
        "value": res.value, "demand": a.demand, "share": pct(res.value, a.demand) if a.demand else None,
        "start_total": res.start_total, "total": res.total, "optimal_total": a.optimum.total,
        "start_gap_pct": pct(res.start_total - a.optimum.total, a.optimum.total) if a.optimum.total else 0.0,
        "end_gap_pct": pct(res.total - a.optimum.total, a.optimum.total) if a.optimum.total else 0.0,
        "cycles": len(its), "scanned": res.scanned_total, "ssp_rounds": len(a.optimum.rounds), "ssp_scanned": a.optimum.scanned_total,
        "ek_rounds": len(a.start.rounds), "stage_caps": a.stage_caps, "savings": savings, "total_saving": sum(savings),
        "avg_saving": sum(savings) / len(savings) if savings else 0.0, "first_share": pct(savings[0], sum(savings), 0) if savings else 0.0,
        "longest": max((len(i.cycle) for i in its), default=0), "back_arcs": sum(1 for i in its for e in i.cycle if e % 2),
        "bound": res.start_total - a.optimum.total,
    }
    if res.value == 0:
        return "warning", "disconnected", data
    if res.total > a.optimum.total:
        return "warning", "wrong", data
    if not its:
        return "info", "nothing", data
    return "success", "optimal", data


@lru_cache(maxsize=64)
def _start(p, d, s, density, spread, load, seed, rule):
    net = sc.generate(p, d, s, density, spread, load, seed)
    e = ek.max_flow(net, rule, keep_flows=True)
    return net, e.flows[-1], e.scanned_total, len(e.rounds)


@lru_cache(maxsize=128)
def _runs(p, d, s, density, spread, load, rule=C.DEFAULT_RULE, seeds=C.DIST_SEEDS):
    """Je Netz Startfluss, SSP-Optimum und alle Kreiswahlen (ohne Trace); von den Verteilungen gemeinsam genutzt."""
    out = []
    for seed in seeds:
        net, f0, ek_scans, ek_rounds = _start(p, d, s, density, spread, load, seed, rule)
        opt = ssp.ssp(net, "dijkstra", None, keep_trace=False)
        out.append((net, f0, opt, {sel: cy.cancel(net, f0, sel, keep_trace=True) for sel in cy.SELECTIONS}, ek_rounds))
    return out


@lru_cache(maxsize=128)
def distribution(p, d, s, density, spread, load, rule=C.DEFAULT_RULE, seeds=C.DIST_SEEDS):
    """Über feste Netze: Kreise und durchsuchte Kanten je Kreiswahl, Startlücke, Anteil optimal, Sprung des ersten Kreises, Schranke, SSP-Vergleich."""
    keys = ["gap", "gap_pct", "ssp_rounds", "ssp_scanned", "bound_ratio", "value"]
    for sel in cy.SELECTIONS:
        keys += [f"cycles_{sel}", f"scans_{sel}", f"excess_{sel}", f"first_{sel}"]
    cols = {k: [] for k in keys}
    optimal = {sel: 0 for sel in cy.SELECTIONS}
    nothing = neg_from_unreachable = all_served = 0
    for net, f0, opt, results, _ in _runs(p, d, s, density, spread, load, rule, seeds):
        start_total = ssp.flow_cost(net, f0)
        gap = start_total - opt.total
        cols["gap"].append(gap)
        cols["gap_pct"].append(pct(gap, opt.total) if opt.total else 0.0)
        cols["ssp_rounds"].append(len(opt.rounds))
        cols["ssp_scanned"].append(opt.scanned_total)
        cols["value"].append(opt.value)
        nothing += gap == 0
        r = results["klein"]
        cols["bound_ratio"].append(r.n_cycles / gap if gap else 0.0)
        for sel, res in results.items():
            cols[f"cycles_{sel}"].append(res.n_cycles)
            cols[f"scans_{sel}"].append(res.scanned_total)
            cols[f"excess_{sel}"].append(pct(res.total - opt.total, opt.total) if opt.total else 0.0)
            savings = [i.saving for i in res.iterations]
            cols[f"first_{sel}"].append(savings[0] / sum(savings) if savings else 0.0)
            optimal[sel] += res.total == opt.total
        all_served += opt.value == sum(c for _, _, c, _, kind in net.arcs if kind == K_DEMAND)
    n = len(seeds)
    out = {"n_seeds": n, "cols": cols, "share_nothing": nothing / n, "share_all_served": all_served / n, "share_optimal": {sel: optimal[sel] / n for sel in cy.SELECTIONS},
           "nodes_mean": mean(net.n for net, *_ in _runs(p, d, s, density, spread, load, rule, seeds)), "edges_mean": mean(net.m for net, *_ in _runs(p, d, s, density, spread, load, rule, seeds))}
    for k in keys:
        out[k + "_mean"], out[k + "_median"], out[k + "_max"] = mean(cols[k]), median(cols[k]), max(cols[k])
    return out


@lru_cache(maxsize=32)
def rule_table(p, d, s, density, spread, load, seeds=C.SWEEP_SEEDS):
    """Startfluss: Breitensuche, Tiefensuche, breitester Weg - Startlücke und Zahl der Kreise (Klein) je Regel, dazu die Korrelation Lücke gegen Kreise über alle Netze."""
    rows, all_gap, all_cycles = [], [], []
    for rule in ek.SEARCHES:
        gaps, cycles, opt_gap = [], [], []
        for seed in seeds:
            net, f0, _, _ = _start(p, d, s, density, spread, load, seed, rule)
            opt = ssp.ssp(net, "dijkstra", None, keep_trace=False)
            r = cy.cancel(net, f0, "klein", keep_trace=False)
            gaps.append(pct(r.start_total - opt.total, opt.total) if opt.total else 0.0)
            cycles.append(r.n_cycles)
            opt_gap.append(r.total == opt.total)
        rows.append({"rule": rule, "gap_mean": mean(gaps), "gap_median": median(gaps), "cycles_mean": mean(cycles), "cycles_max": max(cycles), "all_optimal": all(opt_gap)})
        all_gap += gaps
        all_cycles += cycles
    corr = float(np.corrcoef(all_gap, all_cycles)[0, 1])
    return rows, corr


@lru_cache(maxsize=32)
def scaling(sizes=C.SCALE_SIZES, seeds=C.SCALE_SEEDS):
    """Durchsuchte Kanten gegen die Netzgröße: Cycle-Canceling (Klein, Minimum-Mean) und SSP, dazu die Kreiszahlen."""
    rows = []
    for (p, d, s) in sizes:
        cols = {k: [] for k in ("klein", "min_mean", "ssp", "cycles_klein", "cycles_min_mean", "ssp_rounds", "n", "m")}
        for seed in seeds:
            net, f0, _, _ = _start(p, d, s, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD, seed, C.DEFAULT_RULE)
            for sel in ("klein", "min_mean"):
                r = cy.cancel(net, f0, sel, keep_trace=False)
                cols[sel].append(r.scanned_total)
                cols[f"cycles_{sel}"].append(r.n_cycles)
            o = ssp.ssp(net, "dijkstra", None, keep_trace=False)
            cols["ssp"].append(o.scanned_total)
            cols["ssp_rounds"].append(len(o.rounds))
            cols["n"].append(net.n)
            cols["m"].append(net.m)
        rows.append({"size": (p, d, s), **{k: mean(v) for k, v in cols.items()}})
    return rows


def slopes(rows):
    x = np.log([r["m"] for r in rows])
    return {k: float(np.polyfit(x, np.log([r[k] for r in rows]), 1)[0]) for k in ("klein", "min_mean", "ssp")}


@lru_cache(maxsize=16)
def capacity_table(p, d, s, density, spread, load, factors=C.CAPACITY_FACTORS, seeds=C.SCALE_SEEDS):
    """Kapazitäten mal k: Kreise und durchsuchte Kanten (Klein und Minimum-Mean) - der Startfluss wird jeweils neu berechnet."""
    rows = []
    for k in factors:
        cols = {"cycles_klein": [], "cycles_min_mean": [], "scans_klein": [], "gap": [], "bound": [], "value": []}
        for seed in seeds:
            net = sc.scale_capacities(sc.generate(p, d, s, density, spread, load, seed), k)
            e = ek.max_flow(net, C.DEFAULT_RULE)
            f0 = e.flows[-1]
            opt = ssp.ssp(net, "dijkstra", None, keep_trace=False)
            for sel in ("klein", "min_mean"):
                cols[f"cycles_{sel}"].append(cy.cancel(net, f0, sel, keep_trace=False).n_cycles)
            cols["scans_klein"].append(cy.cancel(net, f0, "klein", keep_trace=False).scanned_total)
            cols["gap"].append(ssp.flow_cost(net, f0) - opt.total)
            cols["value"].append(e.value)
        rows.append({"k": k, **{key: mean(v) for key, v in cols.items() if v}})
    return rows


def proof(net, flow, pi):
    """Optimalitätsprüfung mit Potenzialen pi: jede Restkante hat reduzierte Kosten >= 0 (Vorwärtsrest: c + pi(u) - pi(v) >= 0; Kante mit Fluss: <= 0).
    Rückgabe: geprüfte Restkanten, Verletzungen, Kanten mit Fluss (`flow_arcs`) und davon die mit reduzierten Kosten 0 (`tight`), kleinste reduzierte Kosten einer Vorwärts-Restkante."""
    checked = violations = tight = flow_arcs = 0
    worst = None
    for i, (u, v, cap, cost, _) in enumerate(net.arcs):
        rc = cost + pi[u] - pi[v]
        if flow[i] < cap:
            checked += 1
            violations += rc < 0
            worst = rc if worst is None else min(worst, rc)
        if flow[i] > 0:
            checked += 1
            violations += rc > 0
            flow_arcs += 1
            tight += rc == 0
    return {"valid": violations == 0, "checked": checked, "violations": violations, "tight": tight, "flow_arcs": flow_arcs, "worst": worst}
