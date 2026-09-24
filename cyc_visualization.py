"""Plotly-Abbildungen: Netz mit Fluss und dem gelöschten Kreis, Ersparnis je Kreis, Kostenabstieg, Menge-Kosten-Ebene, Verteilungen, Aufwand.
Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht zoomen. Kanten haben über unsichtbare Marker einen Hover-Text
(Plotly-Linien reagieren nur an ihren Stützpunkten)."""

from math import atan2, degrees, hypot

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import cyc_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.08), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def _layout(fig, net, height):
    xs = [p[0] for p in net.pos]
    ys = [p[1] for p in net.pos]
    pad = 9
    fig.update_xaxes(visible=False, range=[min(xs) - pad, max(xs) + pad], scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, range=[min(ys) - pad, max(ys) + pad])
    return _base(fig, height)


def _curve(p0, p1, bulge, steps=8):
    """Punkte von p0 nach p1; mit `bulge` > 0 als flacher Bogen nach rechts (so trennen sich Vorwärts- und Rückkante). Dazu der Pfeilwinkel bei 65 %."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = hypot(dx, dy) or 1.0
    cx, cy = (x0 + x1) / 2 + bulge * length * dy / length, (y0 + y1) / 2 - bulge * length * dx / length
    ts = [k / steps for k in range(steps + 1)]
    xs = [(1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1 for t in ts]
    ys = [(1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1 for t in ts]
    t = 0.65
    tx = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx)
    ty = 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
    ax = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
    ay = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
    return xs, ys, (ax, ay, degrees(atan2(tx, ty))), (xs[steps // 2], ys[steps // 2])


def _segments(curves):
    x, y = [], []
    for xs, ys, _, _ in curves:
        x += xs + [None]
        y += ys + [None]
    return x, y


def _lines(fig, curves, color, width, name, dash=None, showlegend=True):
    if not curves:
        return
    x, y = _segments(curves)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width, dash=dash), hoverinfo="skip", name=name, showlegend=showlegend))


def _arrows(fig, curves, color, size=9):
    if not curves:
        return
    fig.add_trace(go.Scatter(x=[c[2][0] for c in curves], y=[c[2][1] for c in curves], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="arrow", size=size, color=color, angle=[c[2][2] for c in curves])))


def _hover_points(fig, net, entries):
    """Unsichtbare Marker entlang jeder Kante, damit der Hover-Text überall auf der Kante erscheint. entries: [(Kurve, Text)]"""
    x, y, text = [], [], []
    for curve, label in entries:
        xs, ys = curve[0], curve[1]
        for k in range(1, len(xs) - 1):
            x.append(xs[k]); y.append(ys[k]); text.append(label)
    if x:
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers", marker=dict(size=9, opacity=0), hovertext=text, hoverinfo="text", showlegend=False))


def _labels(fig, points):
    """points: [(x, y, Text)] - als Annotationen mit heller Hinterlegung, damit sie Kanten, Pfeile und Knotenbeschriftungen nicht unlesbar machen."""
    for x, y, text in points:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", font=dict(size=11, color="#111"), bgcolor="rgba(255,255,255,0.88)", borderpad=1)


def _arc_name(net, i):
    u, v = net.arcs[i][0], net.arcs[i][1]
    return f"{net.names[u]} → {net.names[v]}"


def _nodes(fig, net, reach=None):
    """Knoten: S und T als Quadrate, alle anderen als Kreise; mit `reach` grün (von S erreichbar) oder grau eingefärbt."""
    text_pos = {0: "top center", 1: "bottom center"}
    for kind, idx in (("Quelle/Senke", [net.s, net.t]), ("Knoten", [v for v in range(net.n) if v not in (net.s, net.t)])):
        colors = [C.COLORS["node"] if reach is None else (C.COLORS["reach"] if reach[v] else C.COLORS["unreach"]) for v in idx]
        pos = [text_pos.get(v, "top center" if net.pos[v][1] > 70 else ("bottom center" if net.pos[v][1] < 30 else "middle left")) for v in idx]
        if net.logistic and kind == "Knoten":
            pos = ["top center" if net.names[v].startswith("Werk") else "bottom center" if net.names[v].startswith("Filiale") else "middle left" for v in idx]
        fig.add_trace(go.Scatter(
            x=[net.pos[v][0] for v in idx], y=[net.pos[v][1] for v in idx], mode="markers+text", showlegend=False,
            text=[net.labels[v] for v in idx], textposition=pos, hovertext=[net.names[v] for v in idx], hoverinfo="text",
            marker=dict(symbol="square" if kind == "Quelle/Senke" else "circle", size=13 if kind == "Quelle/Senke" else 10, color=colors, line=dict(width=1.5, color="#333"))))


def _wscale(net):
    return max(c for _, _, c, _, _ in net.arcs)


def _width(amount, top, lo=1.0, hi=6.0):
    return lo + (hi - lo) * amount / top if top else lo


def _node_text_positions(net, idx):
    if net.logistic:
        return ["top center" if (v == 0 or net.names[v].startswith("Werk")) else "bottom center" if (v == 1 or net.names[v].startswith("Filiale")) else "middle left" for v in idx]
    return ["top center" if v == net.s else "bottom center" if v == net.t else "middle left" for v in idx]


def _colorbar(lo, hi):
    return dict(title=dict(text="Schattenpreis π", side="top"), orientation="h", thickness=9, len=0.6, x=0.5, xanchor="center", y=-0.02, yanchor="top", tickmode="linear", tick0=lo, dtick=max(1, -(-(hi - lo) // 4)))


def build_network(net, flow, pi=None, path=None, height=460):
    """Netz mit Fluss: Breite ~ Fluss (dunkelblau = Kante voll, blass = ungenutzt), Knotenfarbe ~ Schattenpreis π (falls gegeben).
    `path`: [(Netzkante, vorwärts?, Menge)] des gelöschten Kreises - grün (vorwärts, +Menge) bzw. orange gestrichelt (Rückkante, −Menge), beschriftet mit den Kosten je Einheit.
    Bei kleinen Lehrnetzen trägt jede Kante Fluss/Kapazität und Kosten."""
    fig = go.Figure()
    top = _wscale(net)
    path_map = {i: (fwd, amount) for i, fwd, amount in (path or ())}
    groups = {"idle": [], "part": [], "full": []}
    fwd_path, back_path, hover, labels = [], [], [], []
    for i, (u, v, cap, cost, _) in enumerate(net.arcs):
        curve = _curve(net.pos[u], net.pos[v], 0.0)
        rc = "" if pi is None else f", reduzierte Kosten {cost + pi[u] - pi[v]}"
        hover.append((curve, f"{_arc_name(net, i)}: Fluss {flow[i]} von {cap}, Kosten {cost} je Einheit{rc}"))
        if i in path_map:
            fwd, amount = path_map[i]
            (fwd_path if fwd else back_path).append(curve)
            labels.append((curve[0][3] + 1.5, curve[1][3], f"{'+' if fwd else '−'}{amount} × {cost if fwd else -cost}"))
        else:
            groups["idle" if flow[i] == 0 else "full" if flow[i] == cap else "part"].append((curve, flow[i]))
            if net.m <= 12:
                labels.append((curve[0][3] + 1.5, curve[1][3], f"{flow[i]}/{cap} · {cost}"))
    _lines(fig, [c for c, _ in groups["idle"]], C.COLORS["faint"], 1.2, "ungenutzt")
    for group, color, name in (("part", "rgba(31,119,180,0.85)", "Fluss (nicht voll)"), ("full", "#0b3d91", "Fluss (Kante voll)")):
        by_width = {}
        for c, f in groups[group]:
            by_width.setdefault(round(_width(f, top)), []).append(c)      # ganze Breiten: wenige Spuren statt einer je Kante
        for w, curves in by_width.items():
            _lines(fig, curves, color, w, name, showlegend=False)
        if groups[group]:
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=color, width=4), name=name))
    _lines(fig, fwd_path, C.COLORS["path"], 5.5, "Kreis: Kante vorwärts (+Menge × Kosten je Einheit)")
    _lines(fig, back_path, C.COLORS["back"], 5.5, "Kreis: Rückkante (nimmt Fluss zurück, spart die Kosten)", dash="dash")
    if net.m <= 80:
        _arrows(fig, [c for c, _ in groups["idle"]] + [c for c, _ in groups["part"]] + [c for c, _ in groups["full"]], "rgba(60,60,60,0.7)", 8)
    _arrows(fig, fwd_path + back_path, "rgba(30,30,30,0.9)", 11)
    _hover_points(fig, net, hover)
    _labels(fig, labels)
    idx = list(range(net.n))
    marker = dict(symbol=["square" if v in (net.s, net.t) else "circle" for v in idx], size=[13 if v in (net.s, net.t) else 11 for v in idx], line=dict(width=1.5, color="#333"))
    if pi is None:
        marker["color"] = C.COLORS["node"]
        hover_nodes = [net.names[v] for v in idx]
    else:
        lo_pi, hi_pi = min(0, min(pi)), max(1, max(pi))
        marker.update(color=list(pi), colorscale=C.COLORS["levels"], cmin=lo_pi, cmax=hi_pi, showscale=True, colorbar=_colorbar(lo_pi, hi_pi))
        hover_nodes = [f"{net.names[v]}: Schattenpreis π = {pi[v]}" for v in idx]
    fig.add_trace(go.Scatter(x=[net.pos[v][0] for v in idx], y=[net.pos[v][1] for v in idx], mode="markers+text", showlegend=False, text=[net.labels[v] for v in idx],
                             textposition=_node_text_positions(net, idx), hovertext=hover_nodes, hoverinfo="text", marker=marker))
    fig = _layout(fig, net, height)
    if pi is not None:
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=90), legend=dict(orientation="h", y=-0.3))
    return fig


def build_savings(iterations, k, height=230):
    """Ersparnis je Kreis (Engpass × |Kreiskosten|): ein Balken je Iteration, bis k voll gefärbt (orange = der Kreis nutzt Rückkanten), spätere blass."""
    fig = go.Figure()
    for i, it in enumerate(iterations):
        back = sum(1 for e in it.cycle if e % 2)
        fig.add_trace(go.Bar(x=[i + 1], y=[it.saving], marker=dict(color=C.COLORS["path"], line=dict(width=1, color="#fff")), opacity=0.9 if i < k else 0.18, showlegend=False,
                             hovertext=f"Kreis {i + 1}: {len(it.cycle)} Kanten ({back} Rückkanten), Kosten je Einheit {it.cost}, Engpass {it.bottleneck} → spart {it.saving}", hoverinfo="text"))
    fig.update_xaxes(title="Kreis", dtick=1 if len(iterations) <= 20 else None, range=[0.4, max(1, len(iterations)) + 0.6])
    fig.update_yaxes(title="Ersparnis", rangemode="tozero")
    fig = _base(fig, height)
    fig.update_layout(bargap=0.15, margin=dict(l=10, r=10, t=10, b=40))
    return fig


def build_descent(start_total, iterations, k, optimum, height=230):
    """Gesamtkosten nach jedem Kreis vom Startfluss (Bild 0) bis zum Ende; gestrichelt das SSP-Optimum. Bisherige Kreise voll, kommende blass."""
    fig = go.Figure()
    totals = [start_total] + [it.total for it in iterations]
    k = min(k, len(iterations))
    if k < len(iterations):
        fig.add_trace(go.Scatter(x=list(range(k, len(totals))), y=totals[k:], mode="lines", line=dict(color=C.COLORS["faint"], width=3), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=list(range(k + 1)), y=totals[:k + 1], mode="lines+markers", line=dict(color=C.COLORS["flow"], width=3), marker=dict(size=6),
                             hovertext=[f"nach {i} Kreisen: Gesamtkosten {y}" for i, y in enumerate(totals[:k + 1])], hoverinfo="text", showlegend=False))
    fig.add_trace(go.Scatter(x=[k], y=[totals[k]], mode="markers", marker=dict(size=12, color=C.COLORS["optimal"], symbol="circle-open", line=dict(width=3)), hoverinfo="skip", showlegend=False))
    fig.add_hline(y=optimum, line=dict(color="#555", dash="dash"), annotation_text=f"Optimum (SSP) {optimum}", annotation_position="top left")
    fig.update_xaxes(title="Kreise gelöscht", dtick=1 if len(totals) <= 21 else None, range=[-0.3, max(1, len(iterations)) + 0.3])
    fig.update_yaxes(title="Gesamtkosten", range=[min(optimum, min(totals)) * 0.97, start_total * 1.02])
    fig = _base(fig, height)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=40))
    return fig


def build_plane(ssp_curve, start_point, end_point, current=None, height=300):
    """Menge-Kosten-Ebene: die konvexe Kostenkurve von SSP (Menge wächst, jeder Punkt kostenminimal) und der senkrechte Abstieg von Cycle-Canceling bei fester Menge
    vom kostenblinden Startfluss (rotes Kreuz) zum Optimum; `current` = (Menge, Kosten) des Flusses im gezeigten Bild."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[p[0] for p in ssp_curve], y=[p[1] for p in ssp_curve], mode="lines+markers", name="SSP: kostenminimal für jede Menge", line=dict(color=C.COLORS["flow"], width=3), marker=dict(size=5),
                             hovertext=[f"Menge {x}: Gesamtkosten {y}" for x, y in ssp_curve], hoverinfo="text"))
    fig.add_trace(go.Scatter(x=[start_point[0], end_point[0]], y=[start_point[1], end_point[1]], mode="lines", name="Cycle-Canceling: bei fester Menge nach unten", line=dict(color=C.COLORS["path"], width=3, dash="dot"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[start_point[0]], y=[start_point[1]], mode="markers", name="Startfluss (Edmonds-Karp)", marker=dict(size=11, color=C.COLORS["cut"], symbol="x"),
                             hovertext=f"Startfluss: Menge {start_point[0]}, Kosten {start_point[1]}", hoverinfo="text"))
    if current is not None:
        fig.add_trace(go.Scatter(x=[current[0]], y=[current[1]], mode="markers", name="Fluss im Bild", marker=dict(size=13, color=C.COLORS["optimal"], symbol="circle-open", line=dict(width=3)), hoverinfo="skip"))
    fig.update_xaxes(title="Menge", range=[0, max(1, ssp_curve[-1][0]) * 1.05])
    fig.update_yaxes(title="Gesamtkosten", rangemode="tozero")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.4), height=height + 60)
    return fig


def build_gap_hist(gaps, current=None, height=300):
    """Aufschlag des Startflusses gegen den billigsten Fluss gleicher Menge, in % der Kosten, je Netz."""
    fig = go.Figure(go.Histogram(x=gaps, xbins=dict(size=5), marker_color=C.COLORS["flow"], opacity=0.8, name="Netze"))
    if current is not None:
        fig.add_vline(x=current, line=dict(color=C.COLORS["optimal"], dash="dash"), annotation_text="Ihre Ziehung", annotation_position="top")
    fig.update_xaxes(title="Mehrkosten des Startflusses [%]")
    fig.update_yaxes(title="Netze")
    fig = _base(fig, height)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30 if current is not None else 10, b=10))
    return fig


def build_cycles_compare(klein, klein_random, min_mean, current=None, height=300):
    """Zahl der Kreise je Netz für die drei zulässigen Kreiswahlen, übereinandergelegt."""
    fig = go.Figure()
    for values, name, color in ((klein, "Klein: beliebig", "#1f77b4"), (klein_random, "Klein: zufällige Reihenfolge", "#ff7f0e"), (min_mean, "Minimum-Mean", "#2ca02c")):
        fig.add_trace(go.Histogram(x=values, xbins=dict(size=1), name=name, marker_color=color, opacity=0.6))
    fig.update_layout(barmode="overlay")
    if current is not None:
        fig.add_vline(x=current, line=dict(color=C.COLORS["optimal"], dash="dash"), annotation_text="Ihre Ziehung", annotation_position="top")
    fig.update_xaxes(title="gelöschte Kreise")
    fig.update_yaxes(title="Netze")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.35), height=height + 50, margin=dict(l=10, r=10, t=30 if current is not None else 10, b=10))
    return fig


def build_scaling(rows, height=340):
    """Durchsuchte Kanten gegen die Kantenzahl (doppelt logarithmisch): Cycle-Canceling (Klein, Minimum-Mean) und SSP; dazu die Kantenzahl."""
    fig = go.Figure()
    m = [r["m"] for r in rows]
    for key, label, color in (("klein", "Cycle-Canceling: Klein", "#1f77b4"), ("min_mean", "Cycle-Canceling: Minimum-Mean", "#d62728"), ("ssp", "Successive Shortest Paths", "#2ca02c")):
        fig.add_trace(go.Scatter(x=m, y=[r[key] for r in rows], mode="lines+markers", name=label, line=dict(color=color)))
    fig.add_trace(go.Scatter(x=m, y=m, mode="lines", name="Kanten des Netzes", line=dict(color="#555", dash="dashdot")))
    fig.update_xaxes(title="Kanten des Netzes", type="log")
    fig.update_yaxes(title="durchsuchte Kanten", type="log")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.4), height=height + 70)
    return fig
