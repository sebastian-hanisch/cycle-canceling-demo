"""Szenario (Aufbau, Reproduzierbarkeit, Stufen, Lehrnetze), Auswertung (Urteil, Verteilungen, Startfluss, Skalierung, Kapazitäten, Menge-Kosten-Ebene)."""

import pytest

import cyc_algorithm as cy
import cyc_constants as C
import cyc_edmonds_karp as ek
import cyc_evaluation as ev
import cyc_scenario as sc
import cyc_ssp as ssp

DEFAULT = (C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD)


def _net(seed=C.DEFAULT_SEED, *settings):
    return sc.generate(*(settings or DEFAULT), seed)


def test_generation_is_reproducible_and_seed_dependent():
    assert _net(5) == _net(5) and _net(5) != _net(6)


def test_structure_of_a_distribution_net():
    p, d, s = 3, 3, 8
    net = _net()
    assert net.n == 2 + p + 2 * d + s and net.s == 0 and net.t == 1 and net.logistic
    kinds = [a[4] for a in net.arcs]
    assert kinds.count(sc.K_SUPPLY) == p and kinds.count(sc.K_THROUGHPUT) == d and kinds.count(sc.K_DEMAND) == s
    assert all(a[2] >= 1 for a in net.arcs)
    for u, v, _, _, kind in net.arcs:
        assert net.pos[u][1] > net.pos[v][1]


def test_costs_lie_in_the_documented_ranges():
    for seed in range(20):
        for u, v, _, cost, kind in _net(seed).arcs:
            lo, hi = {sc.K_SUPPLY: (1, 5), sc.K_LANE_IN: (1, 9), sc.K_THROUGHPUT: (1, 3), sc.K_LANE_OUT: (1, 9), sc.K_DEMAND: (0, 0)}[kind]
            assert lo <= cost <= hi


@pytest.mark.parametrize("seed", range(20))
def test_every_plant_and_store_has_a_lane_even_on_the_thinnest_net(seed):
    net = _net(seed, 3, 3, 8, C.DENSITY_MIN, C.DEFAULT_SPREAD, C.DEFAULT_LOAD)
    assert {a[1] for a in net.arcs if a[4] == sc.K_SUPPLY} <= {a[0] for a in net.arcs if a[4] == sc.K_LANE_IN}
    assert {a[0] for a in net.arcs if a[4] == sc.K_DEMAND} <= {a[1] for a in net.arcs if a[4] == sc.K_LANE_OUT}


def test_a_thinner_net_only_removes_lanes_and_keeps_all_other_values():
    for seed in range(20):
        thin, full = _net(seed, 3, 3, 8, 40, 50, 90), _net(seed, 3, 3, 8, 100, 50, 90)
        assert set(thin.arcs) <= set(full.arcs) and len(thin.arcs) < len(full.arcs)


def test_teaching_nets_and_build_ignore_the_random_settings():
    assert not sc.assignment_cost(5).logistic and sc.build("assignment", 6, 6, 12, 100, 100, 160, 1) == sc.assignment_cost(5)
    assert sc.build("detour", 6, 6, 12, 100, 100, 160, 1) == sc.detour_cost()
    assert sc.build("random", *DEFAULT, 9) == _net(9)


def test_teaching_nets_have_the_documented_shape():
    d = sc.detour_cost()
    assert d.n == 4 and d.m == 4 and [a[2] for a in d.arcs] == [1] * 4 and [a[3] for a in d.arcs] == [0, 9, 1, 1]
    a = sc.assignment_cost(5)
    assert a.n == 12 and a.m == 35 and all(x[2] == 1 for x in a.arcs) and {x[3] for x in a.arcs if 2 <= x[0] < 7} <= set(range(1, 10))


def test_scale_capacities_multiplies_capacities_only():
    net = _net()
    big = sc.scale_capacities(net, 7)
    assert [(a[0], a[1], a[3], a[4]) for a in big.arcs] == [(a[0], a[1], a[3], a[4]) for a in net.arcs] and [a[2] for a in big.arcs] == [7 * a[2] for a in net.arcs]


def test_verdict_codes():
    lvl, code, d = ev.verdict(ev.analyse(_net(1, 3, 3, 8, 100, 50, 40), "klein", "bfs"))
    assert (lvl, code) == ("success", "optimal") and d["value"] == d["demand"]
    lvl, code, d = ev.verdict(ev.analyse(_net(1, 3, 3, 8, 60, 50, 160), "klein", "bfs"))
    assert (lvl, code) == ("success", "optimal") and d["value"] < d["demand"] and set(d["stage_caps"]) & set(ev.STAGE_KINDS)
    lvl, code, d = ev.verdict(ev.analyse(_net(167), "from_s", "bfs"))
    assert (lvl, code) == ("warning", "wrong") and d["total"] > d["optimal_total"] and d["end_gap_pct"] == 30.5
    lvl, code, d = ev.verdict(ev.analyse(sc.generate(2, 6, 3, 20, 50, 90, 8), "klein", "bfs"))
    assert (lvl, code) == ("warning", "disconnected") and d["value"] == 0
    # schon optimaler Startfluss: ein Netz, in dem Edmonds-Karp zufällig billigst ist
    seed = next(s for s in C.DIST_SEEDS if ev.verdict(ev.analyse(_net(s), "klein", "bfs"))[1] == "nothing")
    assert ev.verdict(ev.analyse(_net(seed), "klein", "bfs"))[:2] == ("info", "nothing")


def test_verdict_data_is_consistent():
    a = ev.analyse(_net())
    _, _, d = ev.verdict(a)
    assert d["cycles"] == len(a.result.iterations) == len(d["savings"]) and d["scanned"] == a.result.scanned_total
    assert d["start_total"] == ssp.flow_cost(a.net, a.start_flow) and d["start_total"] - d["total"] == d["total_saving"] == d["bound"] - (d["total"] - d["optimal_total"])
    assert d["ssp_rounds"] == len(ssp.ssp(a.net, keep_trace=False).rounds) and d["ek_rounds"] == len(ek.max_flow(a.net, "bfs", keep_flows=False).rounds)
    assert d["back_arcs"] == sum(1 for i in a.result.iterations for e in i.cycle if e % 2) and d["longest"] == max(len(i.cycle) for i in a.result.iterations)


def test_curve_points_lie_on_the_ssp_curve_and_the_descent_is_vertical():
    a = ev.analyse(_net())
    curve, start, end = ev.curve_points(a)
    assert curve[0] == (0, 0) and curve[-1] == (a.max_value, a.optimum.total)
    assert curve[-1] == end and start[0] == end[0] == a.max_value and start[1] > end[1]


def test_distribution_is_consistent_with_single_runs():
    seeds = tuple(range(5))
    dist = ev.distribution(*DEFAULT, seeds=seeds)
    for i, seed in enumerate(seeds):
        net = sc.generate(*DEFAULT, seed)
        f0 = ek.max_flow(net, "bfs").flows[-1]
        for sel in cy.SELECTIONS:
            r = cy.cancel(net, f0, sel, keep_trace=False)
            assert dist["cols"][f"cycles_{sel}"][i] == r.n_cycles and dist["cols"][f"scans_{sel}"][i] == r.scanned_total
    assert dist["n_seeds"] == 5 and 0 <= dist["share_all_served"] <= 1 and all(g >= 0 for g in dist["cols"]["gap_pct"])


def test_rule_table_scaling_and_capacity_rows():
    rows, corr = ev.rule_table(*DEFAULT, seeds=C.SWEEP_SEEDS[:8])
    assert [r["rule"] for r in rows] == list(ek.SEARCHES) and all(r["all_optimal"] and r["cycles_mean"] > 0 for r in rows) and -1 <= corr <= 1
    sc_rows = ev.scaling(sizes=C.SCALE_SIZES[:3], seeds=C.SCALE_SEEDS[:3])
    assert [r["size"] for r in sc_rows] == list(C.SCALE_SIZES[:3]) and all(r["klein"] > r["ssp"] > 0 for r in sc_rows)
    assert all(0.5 < s < 3.5 for s in ev.slopes(ev.scaling()).values())
    cap = ev.capacity_table(*DEFAULT, factors=(1, 10), seeds=C.SCALE_SEEDS[:3])
    assert [r["k"] for r in cap] == [1, 10] and cap[0]["cycles_klein"] == cap[1]["cycles_klein"] and cap[1]["gap"] == pytest.approx(10 * cap[0]["gap"])


def test_proof_helper_counts_and_detects_violations():
    net = sc.detour_cost()
    r = cy.cancel(net, ek.max_flow(net, "bfs").flows[-1], "klein")
    pi, ok = ssp.certificate(net, r.flow)
    p = ev.proof(net, r.flow, pi)
    assert ok and p["valid"] and p["violations"] == 0 and p["flow_arcs"] == 3
    assert not ev.proof(net, r.flow, tuple(0 for _ in range(net.n)))["valid"]                       # Potenziale 0 sind hier ungültig
