"""Kern: Cycle-Canceling gegen Handfälle und unabhängige Gegenproben (networkx, scipy, Brute Force), Invarianten je Iteration aus dem Trace (zulässiger Fluss, gleiche Menge, echter negativer Kreis,
Ersparnis = Engpass × |Kreiskosten|), Minimum-Mean-Kreis gegen die Aufzählung aller einfachen Kreise, μ nicht fallend (Goldberg-Tarjan), Klein-Schranke, Zertifikat, Negativkontrolle."""

import itertools
import random
from fractions import Fraction

import networkx as nx
import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment, linprog

import cyc_algorithm as cy
import cyc_constants as C
import cyc_edmonds_karp as ek
import cyc_scenario as sc
import cyc_ssp as ssp
from cyc_scenario import SplitMix64


def _nets(count, sizes=((2, 2, 3), (3, 3, 6), (3, 3, 8), (4, 3, 5), (2, 4, 9), (6, 6, 12))):
    """Zufällige Distributionsnetze unterschiedlicher Größe, Dichte, Streuung und Auslastung."""
    rng = random.Random(13)
    for i in range(count):
        p, d, s = sizes[i % len(sizes)]
        yield sc.generate(p, d, s, rng.choice((20, 40, 60, 80, 100)), rng.choice((0, 25, 50, 75, 100)), rng.choice((40, 90, 120, 160)), 3000 + i)


def _start(net, rule="bfs"):
    return ek.max_flow(net, rule).flows[-1]


def _optimum(net):
    g = nx.DiGraph()
    g.add_nodes_from(range(net.n))
    for u, v, c, k, _ in net.arcs:
        g.add_edge(u, v, capacity=c, weight=k)
    flow = nx.max_flow_min_cost(g, net.s, net.t)
    return sum(flow[net.s].values()), nx.cost_of_flow(g, flow)


def _balance(net, flow):
    bal = [0] * net.n
    for i, (u, v, _, _, _) in enumerate(net.arcs):
        bal[u] -= flow[i]
        bal[v] += flow[i]
    return bal


def _is_flow(net, flow):
    bal = _balance(net, flow)
    return all(0 <= flow[i] <= net.arcs[i][2] for i in range(net.m)) and all(bal[v] == 0 for v in range(net.n) if v not in (net.s, net.t)) and bal[net.t] == -bal[net.s]


def _residual(net, flow):
    """Restkanten (Index -> (u, v, Rest, Kosten))."""
    out = {}
    for i, (u, v, c, k, _) in enumerate(net.arcs):
        out[2 * i] = (u, v, c - flow[i], k)
        out[2 * i + 1] = (v, u, flow[i], -k)
    return out


def test_splitmix64_reference_vector():
    rng = SplitMix64(0)
    assert [rng.next() for _ in range(2)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4]


def test_the_predecessor_copies_reproduce_their_numbers():
    """Wachen: Edmonds-Karp 52 475 durchsuchte Kanten (Mittel 524,75), SSP 53 907 (Mittel 539,07) über die 100 festen Netze; SSP-Kosten = networkx."""
    scans, ssp_scans = 0, 0
    for seed in C.DIST_SEEDS:
        net = sc.generate(3, 3, 8, 60, 50, 90, seed)
        scans += ek.max_flow(net, "bfs", keep_flows=False).scanned_total
        r = ssp.ssp(net, keep_trace=False)
        ssp_scans += r.scanned_total
        if seed < C.DIST_SEEDS[0] + 20:
            assert (r.value, r.total) == _optimum(net)
    assert scans == 52475 and ssp_scans == 53907


def test_detour_one_cycle_does_it_and_the_search_from_s_finds_nothing():
    """Umweg: Edmonds-Karp nimmt S-X-T für 9; der Kreis X->A->T->X hat Kosten 1 + 1 - 9 = -7; danach 2. Von S aus ist nichts erreichbar (S ist gesättigt): 0 Kreise, Kosten bleiben 9."""
    net = sc.detour_cost()
    f0 = _start(net)
    assert f0 == (1, 1, 0, 0) and ssp.flow_cost(net, f0) == 9
    for sel in ("klein", "klein_random", "min_mean"):
        r = cy.cancel(net, f0, sel)
        assert r.n_cycles == 1 and r.total == 2 and r.iterations[0].cost == -7 and r.iterations[0].saving == 7 and r.flow == (1, 0, 1, 1)
    r = cy.cancel(net, f0, "from_s")
    assert r.n_cycles == 0 and r.total == 9


def test_brute_force_on_the_detour():
    net = sc.detour_cost()
    best = min(sum(f[i] * net.arcs[i][3] for i in range(net.m)) for f in itertools.product((0, 1), repeat=net.m) if _is_flow(net, f) and _balance(net, f)[net.t] == 1)
    assert best == 2 == cy.cancel(net, _start(net)).total


def test_assignment_network_is_the_hungarian_method():
    net = sc.assignment_cost(5)
    cost = np.zeros((5, 5), dtype=int)
    for u, v, _, k, _ in net.arcs:
        if 2 <= u < 7 and 7 <= v < 12:
            cost[u - 2, v - 7] = k
    rows, cols = linear_sum_assignment(cost)
    f0 = _start(net)
    assert ssp.flow_cost(net, f0) == 25
    for sel in ("klein", "klein_random", "min_mean"):
        r = cy.cancel(net, f0, sel)
        assert r.total == cost[rows, cols].sum() == 10 and _is_flow(net, r.flow)


@pytest.mark.parametrize("selection", ["klein", "klein_random", "min_mean"])
def test_cost_equals_networkx_on_the_hundred_fixed_nets(selection):
    for seed in C.DIST_SEEDS:
        net = sc.generate(3, 3, 8, 60, 50, 90, seed)
        r = cy.cancel(net, _start(net), selection, keep_trace=False)
        assert (r.value, r.total) == _optimum(net), (selection, seed)


@pytest.mark.parametrize("rule", ["bfs", "dfs", "widest"])
def test_every_start_flow_ends_in_the_optimum(rule):
    for net in _nets(30):
        for selection in ("klein", "min_mean"):
            r = cy.cancel(net, _start(net, rule), selection, keep_trace=False)
            assert (r.value, r.total) == _optimum(net) and _is_flow(net, r.flow)


def test_scipy_linear_program_agrees():
    for net in list(_nets(10)):
        r = cy.cancel(net, _start(net), "klein")
        m = net.m
        a_eq, b_eq = [], []
        for v in range(net.n):
            row = np.zeros(m)
            for i, (u, w, _, _, _) in enumerate(net.arcs):
                row[i] += (w == v) - (u == v)
            if v not in (net.s, net.t):
                a_eq.append(row)
                b_eq.append(0)
        a_eq.append(np.array([1.0 if net.arcs[i][0] == net.s else 0.0 for i in range(m)]))
        b_eq.append(r.value)
        lp = linprog([a[3] for a in net.arcs], A_eq=np.array(a_eq), b_eq=b_eq, bounds=[(0, a[2]) for a in net.arcs], method="highs")
        assert lp.status == 0 and round(lp.fun) == r.total


@pytest.mark.parametrize("selection", ["klein", "klein_random", "min_mean"])
def test_iteration_invariants_from_the_trace(selection):
    """Je Iteration: der Kreis ist ein geschlossener einfacher Weg im Restgraphen des vorigen Flusses mit negativen Kosten, der Engpass ist der kleinste Rest, die Menge bleibt gleich,
    der neue Fluss ist zulässig, die Ersparnis ist Engpass × |Kosten| >= 1 und die Gesamtkosten fallen strikt."""
    for net in _nets(40):
        f0 = _start(net)
        r = cy.cancel(net, f0, selection)
        prev, prev_total = f0, ssp.flow_cost(net, f0)
        value = _balance(net, f0)[net.t]
        assert prev_total == r.start_total
        for it in r.iterations:
            res = _residual(net, prev)
            assert all(res[e][2] > 0 for e in it.cycle)
            assert it.bottleneck == min(res[e][2] for e in it.cycle) >= 1
            assert it.cost == sum(res[e][3] for e in it.cycle) < 0
            nodes = [res[e][0] for e in it.cycle]
            assert all(res[it.cycle[i]][1] == res[it.cycle[(i + 1) % len(it.cycle)]][0] for i in range(len(it.cycle)))       # geschlossen
            assert len(set(nodes)) == len(nodes) and it.nodes == tuple(nodes) + (nodes[0],)                                  # einfach
            assert it.saving == it.bottleneck * -it.cost >= 1 and it.total == prev_total - it.saving
            assert _is_flow(net, it.flow_after) and _balance(net, it.flow_after)[net.t] == value and ssp.flow_cost(net, it.flow_after) == it.total
            prev, prev_total = it.flow_after, it.total
        assert prev == r.flow and prev_total == r.total


def test_final_certificate_no_negative_cycle_and_complementary_slackness():
    import cyc_evaluation as ev
    for net in _nets(40):
        r = cy.cancel(net, _start(net), "klein")
        pi, ok = ssp.certificate(net, r.flow)
        assert ok and ev.proof(net, r.flow, pi)["valid"]
        g = nx.DiGraph()
        for i, (u, v, c, k, _) in enumerate(net.arcs):
            if c - r.flow[i] > 0:
                g.add_edge(u, v, weight=k)
            if r.flow[i] > 0:
                g.add_edge(v, u, weight=-k)
        assert not nx.negative_edge_cycle(g)


def test_minimum_mean_cycle_is_the_minimum_over_all_simple_cycles():
    """Karp gegen die Aufzählung aller einfachen Kreise (networkx) auf kleinen Netzen, in jeder Iteration."""
    checked = 0
    for net in _nets(30, sizes=((2, 2, 3), (2, 3, 3), (3, 2, 4))):
        f0 = _start(net)
        r = cy.cancel(net, f0, "min_mean")
        prev = f0
        for it in r.iterations:
            g = nx.DiGraph()
            for e, (u, v, rest, k) in _residual(net, prev).items():
                if rest > 0:
                    g.add_edge(u, v, weight=k)
            best = min(Fraction(sum(g[c[i]][c[(i + 1) % len(c)]]["weight"] for i in range(len(c))), len(c)) for c in nx.simple_cycles(g))
            assert Fraction(*it.mean) == best, (it.mean, best)
            prev = it.flow_after
            checked += 1
    assert checked >= 20


def test_minimum_mean_is_non_decreasing_goldberg_tarjan():
    """Goldberg und Tarjan: löscht man stets den Kreis mit kleinstem Mittelwert, sinkt der Betrag des Mittelwerts nie (mu nicht fallend)."""
    for net in _nets(40):
        means = [Fraction(*it.mean) for it in cy.cancel(net, _start(net), "min_mean").iterations]
        assert all(a <= b for a, b in zip(means, means[1:]))
        assert all(m < 0 for m in means)


def test_klein_bound_cycles_at_most_start_minus_optimum():
    for net in _nets(40):
        f0 = _start(net)
        opt = _optimum(net)[1]
        for selection in ("klein", "klein_random", "min_mean"):
            assert cy.cancel(net, f0, selection, keep_trace=False).n_cycles <= ssp.flow_cost(net, f0) - opt


def test_random_order_is_reproducible():
    net = sc.generate(3, 3, 8, 60, 50, 90, 155)
    f0 = _start(net)
    a, b = cy.cancel(net, f0, "klein_random"), cy.cancel(net, f0, "klein_random")
    assert [i.cycle for i in a.iterations] == [i.cycle for i in b.iterations] and a.scanned_total == b.scanned_total


def test_the_search_from_s_alone_is_wrong_and_never_better_than_the_optimum():
    """Negativkontrolle: nur von S aus gesucht wird ein Teil der negativen Kreise übersehen; nie besser als das Optimum, aber ein zulässiger Fluss."""
    wrong = 0
    for net in _nets(60):
        r = cy.cancel(net, _start(net), "from_s", keep_trace=False)
        assert r.total >= _optimum(net)[1] and _is_flow(net, r.flow)
        wrong += r.total > _optimum(net)[1]
    assert wrong >= 1
    net = sc.generate(3, 3, 8, 60, 50, 90, 167)
    r = cy.cancel(net, _start(net), "from_s")
    assert r.n_cycles == 0 and r.total == 1372 and _optimum(net)[1] == 1051 and ssp.certificate(net, r.flow)[1] is False


def test_capacity_scaling_keeps_the_number_of_cycles():
    for net in _nets(20):
        base = {sel: cy.cancel(net, _start(net), sel, keep_trace=False) for sel in ("klein", "min_mean")}
        for k in (10, 1000):
            big = sc.scale_capacities(net, k)
            for sel, r0 in base.items():
                r = cy.cancel(big, _start(big), sel, keep_trace=False)
                assert r.n_cycles == r0.n_cycles and r.total == k * r0.total and r.scanned_total == r0.scanned_total


def test_an_already_optimal_start_needs_no_cycle_and_costs_one_search():
    net = sc.generate(3, 3, 8, 60, 50, 90, 155)
    opt = ssp.ssp(net)
    for sel in ("klein", "min_mean"):
        r = cy.cancel(net, opt.flow, sel)
        assert r.n_cycles == 0 and r.total == opt.total and r.scanned_total == r.final_scanned > 0


def test_unreachable_net_has_value_zero_and_no_cycle():
    net = sc.generate(2, 6, 3, 20, 50, 90, 8)
    f0 = _start(net)
    r = cy.cancel(net, f0, "klein")
    assert r.value == 0 and r.n_cycles == 0 and r.total == 0


def test_unknown_selection_is_rejected():
    with pytest.raises(ValueError):
        cy.cancel(sc.detour_cost(), (0, 0, 0, 0), "steilster")


def test_scanned_counts_add_up():
    net = sc.generate(3, 3, 8, 60, 50, 90, 155)
    r = cy.cancel(net, _start(net), "klein")
    assert r.scanned_total == sum(i.scanned for i in r.iterations) + r.final_scanned
