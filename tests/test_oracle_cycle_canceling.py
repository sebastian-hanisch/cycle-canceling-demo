"""Unabhängiges Orakel: Cycle-Canceling auf zufälligen Kleinstnetzen (Parallel- und Gegenkanten, Kapazität 0, Gleichstände, auch negative Kosten) mit zufälligen zulässigen Startflüssen
(Ecke eines linearen Programms mit zufälligem Ziel, nicht nur ein größter Fluss). Die Kosten stimmen mit scipy.optimize.linprog überein, am Ende bleibt kein negativer Kreis
(networkx.negative_edge_cycle), und der Kreis von `min_mean` hat in jeder Iteration den kleinsten Mittelwert aller einfachen Kreise des Restgraphen (networkx.simple_cycles)."""

import random
from fractions import Fraction

import numpy as np
import pytest

import cyc_algorithm as cy
import cyc_scenario as sc

nx = pytest.importorskip("networkx")
linprog = pytest.importorskip("scipy.optimize").linprog


def _instance(rng):
    n = rng.randint(3, 7)
    arcs = []
    for _ in range(rng.randint(n, 3 * n)):
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v:
            arcs.append((u, v, rng.choice([0, 1, 1, 2, 3, 4, 5, 7]), rng.choice([rng.randint(-4, 9), rng.randint(0, 9), rng.choice([1, 2])])))
    net = sc.Net(tuple(f"n{i}" for i in range(n)), tuple(f"n{i}" for i in range(n)), tuple((i, 0) for i in range(n)), tuple((u, v, c, k, sc.K_OTHER) for u, v, c, k in arcs), 0, 1, False)
    return n, arcs, net


def _lp(n, arcs, value, cost):
    a = np.zeros((n, len(arcs)))
    for i, (u, v, _c, _k) in enumerate(arcs):
        a[u, i] += 1
        a[v, i] -= 1
    b = np.zeros(n)
    b[0], b[1] = value, -value
    return linprog(cost, A_eq=a, b_eq=b, bounds=[(0, c) for _u, _v, c, _k in arcs], method="highs")


def _residual_graph(n, arcs, flow):
    g = nx.DiGraph()
    g.add_nodes_from(range(n))
    for (u, v, c, k), f in zip(arcs, flow):
        for a, b, w, ok in ((u, v, k, f < c), (v, u, -k, f > 0)):
            if ok and (not g.has_edge(a, b) or w < g[a][b]["w"]):
                g.add_edge(a, b, w=w)
    return g


def _smallest_mean(n, arcs, flow):
    g = _residual_graph(n, arcs, flow)
    means = [Fraction(sum(g[c[i]][c[(i + 1) % len(c)]]["w"] for i in range(len(c))), len(c)) for c in nx.simple_cycles(g)]
    return min(means, default=None)


@pytest.mark.parametrize("selection", ["klein", "klein_random", "min_mean"])
def test_random_small_nets_with_random_start_flows(selection):
    rng = random.Random(20261004)
    checked = cycles = 0
    for _ in range(60):
        n, arcs, net = _instance(rng)
        if not arcs:
            continue
        a_max = _lp(n, arcs, 1, [0] * len(arcs))
        if a_max.status != 0:
            continue
        value = 1
        start = _lp(n, arcs, value, [rng.randint(-5, 5) for _ in arcs])
        optimum = _lp(n, arcs, value, [k for *_x, k in arcs])
        f0 = tuple(int(round(x)) for x in start.x)
        res = cy.cancel(net, f0, selection)
        checked += 1
        assert res.value == value and res.total == round(optimum.fun)
        assert not nx.negative_edge_cycle(_residual_graph(n, arcs, res.flow), weight="w")
        if selection == "min_mean":
            flow = list(f0)
            for it in res.iterations:
                assert Fraction(*it.mean) == _smallest_mean(n, arcs, flow)
                for e in it.cycle:
                    flow[e // 2] += it.bottleneck if e % 2 == 0 else -it.bottleneck
                cycles += 1
            assert tuple(flow) == res.flow
    assert checked >= 20 and (selection != "min_mean" or cycles >= 10)
