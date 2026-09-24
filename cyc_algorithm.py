"""Cycle-Canceling: ein zulässiger Fluss wird kostenminimal, indem negative Kreise im Restgraphen ausgelöscht werden.

Gegeben ein zulässiger Fluss (hier: ein maximaler Fluss von Edmonds-Karp, kostenblind). Ein Kreis im Restgraphen mit negativen Gesamtkosten ist eine Umleitung, die Geld spart und die Menge nicht ändert: der Fluss wird um den Engpass des Kreises
verschoben, die Kosten sinken um Engpass x |Kreiskosten|. Gibt es keinen negativen Kreis mehr, ist der Fluss kostenminimal für seine Menge (Satz vom negativen Kreis). Das ist das Gegenstück zu Successive Shortest Paths: SSP hält
Optimalität und baut die Menge auf, Cycle-Canceling hält die Menge (Zulässigkeit) und baut Optimalität auf.

Restkanten wie in den Vorgänger-Demos: Kante 2i ist die Vorwärtskante der Netzkante i (Rest = Kapazität - Fluss, Kosten c), Kante 2i+1 die Rückkante (Rest = Fluss, Kosten -c).

Vier Kreiswahlen:
- **klein**: Bellman-Ford von einem gedachten Start mit Entfernung 0 zu allen Knoten, Kanten in fester Reihenfolge; der erste gefundene negative Kreis wird gelöscht (Klein 1967, "beliebiger" Kreis).
- **klein_random**: dieselbe Suche, Kanten je Iteration in zufälliger Reihenfolge - zeigt, wie stark "beliebig" streut.
- **min_mean**: der Kreis mit dem kleinsten Mittelwert der Kosten je Kante (Karp 1978; Goldberg und Tarjan 1989: stark polynomiale Schranke).
- **from_s**: Bellman-Ford nur von S aus - übersieht negative Kreise in Bereichen, die S im Restgraphen nicht erreicht. Negativkontrolle, kein zulässiges Verfahren.

Aufwand wird in durchsuchten Kanten gezählt (jede in einem Durchlauf angesehene Restkante, auch solche ohne Rest), nie in Sekunden.
"""

from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from cyc_edmonds_karp import _adjacency
from cyc_scenario import SplitMix64

INF = float("inf")
SELECTIONS = ("klein", "klein_random", "min_mean", "from_s")


@dataclass(frozen=True)
class Iteration:
    cycle: tuple           # Restkanten-Indizes des Kreises in Laufrichtung (gerade = Vorwärts-, ungerade = Rückkante)
    nodes: tuple           # Knotenfolge, Start = Ende
    bottleneck: int
    cost: int              # Kosten je Einheit um den Kreis (negativ)
    mean: tuple            # Mittelwert der Kosten je Kante als (Zähler, Nenner), gekürzt
    saving: int            # Engpass x |Kosten|
    total: int             # Gesamtkosten nach dem Löschen
    scanned: int
    flow_after: tuple      # Fluss je Netzkante nach dem Löschen (leer ohne Trace)


@dataclass(frozen=True)
class Result:
    iterations: tuple
    flow: tuple
    value: int
    start_total: int
    total: int
    final_scanned: int     # letzter, ergebnisloser Durchlauf
    scanned_total: int
    selection: str

    @property
    def n_cycles(self):
        return len(self.iterations)


def _costs(net):
    cost = [0] * (2 * net.m)
    for i, arc in enumerate(net.arcs):
        cost[2 * i] = arc[3]
        cost[2 * i + 1] = -arc[3]
    return cost


def _parent_cycle(parent, head, n):
    """Kreis im Vorgänger-Graphen (jeder solche Kreis hat negative Kosten), sonst None. O(n)."""
    state = [0] * n                                   # 0 = unbesucht, 1 = auf dem aktuellen Weg, 2 = fertig
    for start in range(n):
        if state[start]:
            continue
        path, v = [], start
        while v != -1 and state[v] == 0:
            state[v] = 1
            path.append(v)
            v = head[parent[v] ^ 1] if parent[v] != -1 else -1
        if v != -1 and state[v] == 1:
            cycle, node = [], v
            while True:
                e = parent[node]
                cycle.append(e)
                node = head[e ^ 1]
                if node == v:
                    break
            cycle.reverse()
            return tuple(cycle)
        for u in path:
            state[u] = 2
    return None


def _find_bellman_ford(head, res, cost, n, order, source):
    """Bellman-Ford mit Kanten in der Reihenfolge `order`. `source` None = gedachter Start zu allen Knoten (Entfernung 0), sonst nur von `source`.
    Nach jedem Durchlauf mit Verbesserung wird der Vorgänger-Graph auf einen Kreis geprüft (jeder Kreis dort ist negativ); ein Durchlauf ohne Verbesserung heißt: kein negativer Kreis.
    Rückgabe (Kreis oder None, durchsuchte Kanten)."""
    dist = [0] * n if source is None else [INF] * n
    if source is not None:
        dist[source] = 0
    parent = [-1] * n
    scanned = 0
    for _ in range(n):
        changed = False
        for e in order:
            scanned += 1
            if res[e] > 0:
                u, v = head[e ^ 1], head[e]
                if dist[u] + cost[e] < dist[v]:
                    dist[v] = dist[u] + cost[e]
                    parent[v] = e
                    changed = True
        if not changed:
            return None, scanned
        cycle = _parent_cycle(parent, head, n)
        if cycle is not None:
            return cycle, scanned
    return None, scanned


def _find_min_mean(head, res, cost, n):
    """Karp: D_k(v) = kleinste Kosten eines Weges mit genau k Kanten, der irgendwo beginnt und in v endet. Kleinster Kreis-Mittelwert = min_v max_k (D_n(v) - D_k(v)) / (n - k).
    Der Weg mit n Kanten zum besten v enthält den Kreis mit diesem Mittelwert. Rückgabe (Kreis oder None, Mittelwert als Fraction, durchsuchte Kanten).
    Die Tabelle D wird mit numpy gerechnet (Ganzzahlen exakt in float64); der Vergleich der Mittelwerte ist exakt (Fraction) für alle Kandidaten, die in float nicht klar schlechter sind."""
    edges = [e for e in range(len(res)) if res[e] > 0]
    scanned = n * len(res)
    if not edges:
        return None, None, scanned
    order = sorted(edges, key=lambda e: head[e])                    # stabil: innerhalb eines Zielknotens aufsteigende Kantennummern
    u_arr = np.array([head[e ^ 1] for e in order])
    v_arr = np.array([head[e] for e in order])
    c_arr = np.array([cost[e] for e in order], dtype=float)
    starts = np.flatnonzero(np.r_[True, v_arr[1:] != v_arr[:-1]])
    targets = v_arr[starts]
    d = np.full((n + 1, n), np.inf)
    d[0] = 0.0
    for k in range(1, n + 1):
        d[k, targets] = np.minimum.reduceat(d[k - 1, u_arr] + c_arr, starts)
    last = d[n]
    finite = np.isfinite(last)
    if not finite.any():
        return None, None, scanned
    denom = (n - np.arange(n))[:, None]
    with np.errstate(invalid="ignore"):
        diff = last[None, :] - d[:n]                                 # (n, n): Zeile k, Spalte v
        ratio = np.where(np.isfinite(d[:n]), diff / denom, -np.inf)
    worst = np.where(finite, ratio.max(axis=0), np.inf)
    approx_best = worst.min()
    best, best_v = None, -1
    for v in np.flatnonzero(worst <= approx_best + 1e-9):
        exact = max(Fraction(int(last[v] - d[k, v]), n - k) for k in np.flatnonzero(ratio[:, v] >= worst[v] - 1e-9))
        if best is None or exact < best:
            best, best_v = exact, int(v)
    if best >= 0:
        return None, best, scanned
    walk, v = [], best_v
    for k in range(n, 0, -1):
        e = next(e for e in order if head[e] == v and d[k - 1, head[e ^ 1]] + cost[e] == d[k, v])
        walk.append(e)
        v = head[e ^ 1]
    walk.reverse()                                     # Kanten des Weges in Laufrichtung, Startknoten = head[walk[0] ^ 1]
    # der Weg mit n Kanten besucht einen Knoten doppelt: in einfache Kreise zerlegen, den mit dem kleinsten Mittelwert nehmen
    stack_nodes, stack_edges, cycles = [head[walk[0] ^ 1]], [], []
    for e in walk:
        stack_edges.append(e)
        stack_nodes.append(head[e])
        if stack_nodes.index(head[e]) != len(stack_nodes) - 1:
            i = stack_nodes.index(head[e])
            cycles.append(tuple(stack_edges[i:]))
            del stack_edges[i:]
            del stack_nodes[i + 1:]
    cycle = min(cycles, key=lambda c: Fraction(sum(cost[e] for e in c), len(c)))
    return cycle, best, scanned


def cancel(net, start_flow, selection="klein", keep_trace=True, max_iterations=None):
    """Löscht negative Kreise, bis keiner mehr gefunden wird. `start_flow`: zulässiger Fluss je Netzkante."""
    if selection not in SELECTIONS:
        raise ValueError(selection)
    adj, head = _adjacency(net)
    cost = _costs(net)
    n, m = net.n, net.m
    res = [0] * (2 * m)
    for i, (_, _, cap, _, _) in enumerate(net.arcs):
        res[2 * i] = cap - start_flow[i]
        res[2 * i + 1] = start_flow[i]
    total = start_total = sum(start_flow[i] * net.arcs[i][3] for i in range(m))
    value = sum(start_flow[i] for i, arc in enumerate(net.arcs) if arc[0] == net.s) - sum(start_flow[i] for i, arc in enumerate(net.arcs) if arc[1] == net.s)
    rng = SplitMix64(0xC1C1E5)
    order = list(range(2 * m))
    iterations = []
    scanned_total = final_scanned = 0
    while max_iterations is None or len(iterations) < max_iterations:
        mean = None
        if selection == "klein":
            cycle, scanned = _find_bellman_ford(head, res, cost, n, order, None)
        elif selection == "klein_random":
            for i in range(len(order) - 1, 0, -1):
                j = rng.below(i + 1)
                order[i], order[j] = order[j], order[i]
            cycle, scanned = _find_bellman_ford(head, res, cost, n, order, None)
        elif selection == "from_s":
            cycle, scanned = _find_bellman_ford(head, res, cost, n, order, net.s)
        else:
            cycle, mean, scanned = _find_min_mean(head, res, cost, n)
        scanned_total += scanned
        if cycle is None:
            final_scanned = scanned
            break
        bottleneck = min(res[e] for e in cycle)
        cycle_cost = sum(cost[e] for e in cycle)
        for e in cycle:
            res[e] -= bottleneck
            res[e ^ 1] += bottleneck
        total += bottleneck * cycle_cost
        frac = Fraction(cycle_cost, len(cycle))
        iterations.append(Iteration(cycle, tuple(head[e ^ 1] for e in cycle) + (head[cycle[-1]],), bottleneck, cycle_cost, (frac.numerator, frac.denominator), -bottleneck * cycle_cost, total, scanned,
                                    tuple(res[2 * i + 1] for i in range(m)) if keep_trace else ()))
    flow = tuple(res[2 * i + 1] for i in range(m))
    return Result(tuple(iterations), flow, value, start_total, total, final_scanned, scanned_total, selection)


def flow_cost(net, flow):
    return sum(flow[i] * net.arcs[i][3] for i in range(net.m))
