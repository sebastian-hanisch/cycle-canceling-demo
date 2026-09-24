"""Jede Zahl, die README und Hilfetexte nennen, ist hier belegt (Standardeinstellungen, 100 feste Netze, Seeds 100000-100099)."""

import pytest

import cyc_algorithm as cy
import cyc_constants as C
import cyc_edmonds_karp as ek
import cyc_evaluation as ev
import cyc_scenario as sc
import cyc_ssp as ssp

S = (C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD)


@pytest.fixture(scope="module")
def dist():
    return ev.distribution(*S)


def test_the_start_flow_is_dearer_by_the_predecessor_numbers(dist):
    """Wache aus der SSP-Demo: Mittel 12,7 %, Median 11,1 %, höchstens 57 %; nur 2 von 100 Netzen zufällig billigst."""
    assert dist["n_seeds"] == 100 and round(dist["gap_pct_mean"], 1) == 12.7 and round(dist["gap_pct_median"], 1) == 11.1 and dist["gap_pct_max"] == 57.0
    assert dist["share_nothing"] == 0.02 and round(dist["gap_mean"], 1) == 106.0


def test_every_valid_selection_ends_in_the_optimum_in_every_net(dist):
    assert all(dist["share_optimal"][k] == 1.0 for k in ("klein", "klein_random", "min_mean"))


def test_number_of_cycles_by_selection(dist):
    """Klein 4,86 Kreise im Mittel (Median 5, höchstens 13), zufällige Reihenfolge 4,76 (höchstens 12), Minimum-Mean 4,07 (höchstens 11)."""
    assert [round(dist[f"cycles_{k}_mean"], 2) for k in ("klein", "klein_random", "min_mean")] == [4.86, 4.76, 4.07]
    assert [dist[f"cycles_{k}_median"] for k in ("klein", "klein_random", "min_mean")] == [5, 4, 4]
    assert [dist[f"cycles_{k}_max"] for k in ("klein", "klein_random", "min_mean")] == [13, 12, 11]
    c = dist["cols"]
    assert (sum(a < b for a, b in zip(c["cycles_min_mean"], c["cycles_klein"])), sum(a == b for a, b in zip(c["cycles_min_mean"], c["cycles_klein"])), sum(a > b for a, b in zip(c["cycles_min_mean"], c["cycles_klein"]))) == (42, 56, 2)


def test_first_cycle_share_of_the_saving(dist):
    """Der erste Kreis bringt bei Minimum-Mean 49 % der Ersparnis, bei Klein 35 %, bei zufälliger Reihenfolge 38 %."""
    assert [round(100 * dist[f"first_{k}_mean"]) for k in ("klein", "klein_random", "min_mean")] == [35, 38, 49]


def test_search_effort_against_ssp(dist):
    """Durchsuchte Kanten: Klein 1509, zufällig 1283, Minimum-Mean 6717, SSP 539; Klein löscht in 97 von 100 Netzen weniger Kreise, als SSP Runden braucht (4,86 gegen 11,57)."""
    assert [round(dist[f"scans_{k}_mean"]) for k in ("klein", "klein_random", "min_mean")] == [1509, 1283, 6717] and round(dist["ssp_scanned_mean"]) == 539
    assert round(dist["ssp_rounds_mean"], 2) == 11.57 and sum(a < b for a, b in zip(dist["cols"]["cycles_klein"], dist["cols"]["ssp_rounds"])) == 97


def test_the_search_from_s_alone(dist):
    """Nur von S aus: in 36 von 100 Netzen nicht kostenminimal (dort im Mittel 7,3 % zu teuer, höchstens 26,3 %), in 26 Netzen gar kein Kreis gefunden; kostenminimal in 64 %."""
    wrong = [g for g in dist["cols"]["excess_from_s"] if g > 0]
    assert len(wrong) == 36 and dist["share_optimal"]["from_s"] == 0.64 and round(sum(wrong) / len(wrong), 1) == 7.3 and max(wrong) == 26.3
    assert sum(x == 0 for x in dist["cols"]["cycles_from_s"]) == 26


def test_bound_is_far_from_reality(dist):
    """Kreise ÷ (Startkosten − Optimum): im Mittel 6,8 %, höchstens 50 %."""
    assert round(100 * dist["bound_ratio_mean"], 1) == 6.8 and dist["bound_ratio_max"] == 0.5


def test_start_flow_rules():
    """40 Netze: Startlücke Breitensuche 14,1 %, Tiefensuche 14,1 %, breitester Weg 12,0 %; Kreise (Klein) 5,3 / 4,9 / 5,9, höchstens 11 / 13 / 13; Korrelation Lücke-Kreise 0,50; alle enden im Optimum."""
    rows, corr = ev.rule_table(*S)
    assert [(r["rule"], round(r["gap_mean"], 1), round(r["cycles_mean"], 1), r["cycles_max"], r["all_optimal"]) for r in rows] == [("bfs", 14.1, 5.3, 11, True), ("dfs", 14.1, 4.9, 13, True), ("widest", 12.0, 5.9, 13, True)]
    assert round(corr, 2) == 0.50


def test_start_flow_rules_over_the_hundred_nets():
    """Über alle 100 Netze: Startlücke 12,7 / 13,0 / 11,5 %; Kreise (Klein) 4,86 / 4,73 / 5,72."""
    got = [(round(ev.distribution(*S, rule=r)["gap_pct_mean"], 1), round(ev.distribution(*S, rule=r)["cycles_klein_mean"], 2)) for r in ("bfs", "dfs", "widest")]
    assert got == [(12.7, 4.86), (13.0, 4.73), (11.5, 5.72)]


def test_scaling_slopes_and_ratios():
    rows = ev.scaling()
    slopes = ev.slopes(rows)
    assert (round(slopes["klein"], 2), round(slopes["min_mean"], 2), round(slopes["ssp"], 2)) == (1.93, 2.52, 1.69)
    klein_ratio = [r["klein"] / r["ssp"] for r in rows]
    assert round(min(klein_ratio), 1) == 2.4 and round(max(klein_ratio), 1) == 6.4 and round(rows[-1]["min_mean"] / rows[-1]["ssp"]) == 254
    assert round(rows[-1]["min_mean"] / 1e6, 1) == 44.7 and round(rows[-1]["ssp"], -3) == 176000
    assert [round(r["cycles_klein"]) for r in rows] == [2, 4, 14, 38, 74, 160] and [round(r["cycles_min_mean"]) for r in rows] == [1, 4, 11, 28, 55, 114] and round(rows[-1]["ssp_rounds"]) == 141
    assert [round(r["m"]) for r in rows] == [16, 34, 73, 185, 431, 1168]


def test_capacity_scaling_leaves_the_cycles_alone():
    rows = ev.capacity_table(*S)
    assert [r["cycles_klein"] for r in rows] == [4.3] * 4 and [r["cycles_min_mean"] for r in rows] == [3.9] * 4 and [r["scans_klein"] for r in rows] == [1327] * 4
    assert [r["gap"] for r in rows] == pytest.approx([74.5, 745, 7450, 74500])


def test_default_net_numbers():
    a = ev.analyse(sc.generate(*S, C.DEFAULT_SEED))
    _, code, d = ev.verdict(a)
    assert code == "optimal" and (d["value"], d["demand"], d["start_total"], d["total"], d["start_gap_pct"]) == (76, 76, 1339, 1197, 11.9)
    assert (d["cycles"], d["scanned"], d["ssp_rounds"], d["ssp_scanned"], d["bound"]) == (7, 2052, 14, 824, 142)
    mm = ev.verdict(ev.analyse(sc.generate(*S, C.DEFAULT_SEED), "min_mean"))[2]
    assert (mm["cycles"], mm["scanned"]) == (5, 8664)


def test_seed_53_and_the_start_flow_presets():
    """Seed 53: Klein 13 Kreise (3996 durchsuchte Kanten), Minimum-Mean 5 (8436). Standardnetz mit Tiefensuche: +17,0 %, 14 Kreise; breitester Weg: +16,6 %, 11 Kreise."""
    net = sc.generate(*S, 53)
    assert [(ev.verdict(ev.analyse(net, s))[2]["cycles"], ev.verdict(ev.analyse(net, s))[2]["scanned"]) for s in ("klein", "min_mean")] == [(13, 3996), (5, 8436)]
    base = sc.generate(*S, C.DEFAULT_SEED)
    dfs, widest = ev.verdict(ev.analyse(base, "klein", "dfs"))[2], ev.verdict(ev.analyse(base, "klein", "widest"))[2]
    assert (dfs["start_gap_pct"], dfs["cycles"], widest["start_gap_pct"], widest["cycles"]) == (17.0, 14, 16.6, 11)


def test_only_from_s_seed_167_stays_30_percent_too_dear():
    d = ev.verdict(ev.analyse(sc.generate(*S, 167), "from_s"))[2]
    assert (d["cycles"], d["total"], d["optimal_total"], d["end_gap_pct"]) == (0, 1372, 1051, 30.5)


def test_tight_supply_teaching_nets():
    k = ev.verdict(ev.analyse(sc.generate(3, 3, 8, 60, 50, 140, C.DEFAULT_SEED)))[2]
    assert (k["value"], k["demand"], k["start_total"], k["total"], k["cycles"]) == (89, 118, 1526, 1403, 14)
    a = ev.verdict(ev.analyse(sc.assignment_cost(5)))[2]
    assert (a["start_total"], a["total"], a["cycles"], a["ssp_rounds"]) == (25, 10, 4, 5)
    u = ev.verdict(ev.analyse(sc.detour_cost()))[2]
    assert (u["start_total"], u["total"], u["cycles"], u["savings"]) == (9, 2, 1, [7])
    assert ev.verdict(ev.analyse(sc.detour_cost(), "from_s"))[1] == "wrong"


def test_extremes_of_the_input_ranges_end_in_the_optimum():
    import networkx as nx
    for args in ((2, 2, 3, 20, 0, 40), (6, 6, 12, 100, 100, 160), (2, 6, 12, 20, 100, 160), (6, 2, 3, 100, 0, 40)):
        net = sc.generate(*args, 5)
        g = nx.DiGraph()
        for u, v, c, k, _ in net.arcs:
            g.add_edge(u, v, capacity=c, weight=k)
        flow = nx.max_flow_min_cost(g, net.s, net.t)
        for sel in ("klein", "min_mean"):
            assert cy.cancel(net, ek.max_flow(net, "bfs").flows[-1], sel, keep_trace=False).total == nx.cost_of_flow(g, flow)
