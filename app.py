"""Cycle-Canceling - negative Kreise löschen - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo EIN Verfahren - Cycle-Canceling: ein zulässiger, aber teurer Fluss wird durch das Löschen negativer Kreise im Restgraphen billiger - und lässt stattdessen das Beispiel wachsen.
Fünftes Stück der Netzwerkfluss-Linie der "Konzepte"-Reihe, Gegenstück zu "Successive Shortest Paths": SSP hält Optimalität und baut die Menge auf, Cycle-Canceling hält die Menge und baut Optimalität auf. Siehe README für die Einordnung.

Lauffähig mit: streamlit run app.py
"""

import time

import streamlit as st

import cyc_algorithm as cy
import cyc_constants as C
import cyc_evaluation as ev
import cyc_scenario as sc
import cyc_ssp as ssp
from cyc_presets import (
    KEPT,
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    seed_widget,
    sync_query_params,
)
from cyc_scenario import build
from cyc_visualization import (
    build_cycles_compare,
    build_descent,
    build_gap_hist,
    build_network,
    build_plane,
    build_savings,
    build_scaling,
)

st.set_page_config(page_title="Cycle-Canceling – Sebastian Hanisch", layout="wide")

SEL_SHORT = {"klein": "Klein: beliebig", "klein_random": "Klein: zufällig", "min_mean": "Minimum-Mean", "from_s": "nur von S aus"}
RULE_SHORT = {"bfs": "Breitensuche", "dfs": "Tiefensuche", "widest": "breitester Weg"}


def _pct(x, digits=1):
    return "–" if x is None else f"{x:.{digits}f} %".replace(".", ",")


def _share(x):
    """Anteil (0..1) als 'nn %'."""
    return f"{100 * x:.0f} %"


def _f(x, digits=1):
    return "–" if x is None else f"{x:.{digits}f}".replace(".", ",")


def _int(x):
    return f"{int(round(x)):,}".replace(",", " ")


def _stage_text(stage_caps):
    parts = [f"{sc.KIND_LABELS[k]} {v}" for k, v in stage_caps.items() if k in ev.STAGE_KINDS]
    return ", ".join(parts)


@st.cache_resource(show_spinner=False, max_entries=32)
def _analysis(params, selection, rule):
    return ev.analyse(build(*params), selection, rule)


st.title("♻️ Cycle-Canceling – negative Kreise löschen")
st.markdown(
    """
Die drei ersten Stücke der Linie liefern den **größten** Fluss und ignorieren die Kosten; **Successive Shortest Paths** baut den billigsten Fluss von Grund auf. **Cycle-Canceling** geht den umgekehrten Weg: es beginnt mit einem **zulässigen, aber teuren** Fluss - hier dem von Edmonds-Karp, im Mittel 12,7 % teurer als nötig - und räumt auf.
Ein **Kreis mit negativen Kosten im Restgraphen** ist eine Umleitung, die Geld spart und die Menge nicht ändert: der Fluss wird um den Engpass des Kreises verschoben (Rückkanten nehmen Fluss zurück), die Kosten sinken. Gibt es keinen negativen Kreis mehr, ist der Fluss **kostenminimal** - das ist der ganze Beweis.
Diese Demo zeigt Kreis für Kreis, wie der Fluss billiger wird, wie sich **beliebige** Kreise (Klein 1967) von dem Kreis mit dem **kleinsten Mittelwert** (Goldberg und Tarjan 1989) unterscheiden, und was die Suche kostet - im Vergleich zu SSP.
"""
)
st.caption(
    "Anders als die Fall-Demos im Portfolio, die an einem Anwendungsfall mehrere Verfahren vergleichen, zeigt diese Demo - fünftes Stück der Netzwerkfluss-Linie der \"Konzepte\"-Reihe, Gegenstück zu \"Successive Shortest Paths\" - **ein** Verfahren an einem wachsenden Beispiel. "
    "Der **Netzwerksimplex** (Fall-Demo \"Distributionsnetzwerk-Optimierung\") ist verwandt: jeder seiner Pivots löscht einen Fundamentalkreis, aber mit einer Baumstruktur statt einer neuen Suche. **Cost Scaling** (gebaut) verallgemeinert die Bedingung „kein negativer Kreis“ zu ε-Optimalität."
)

with st.expander("So funktioniert Cycle-Canceling", expanded=True):
    st.markdown(
        r"""
1. **Startfluss:** irgendein zulässiger Fluss der gewünschten Menge - hier ein größter Fluss von Edmonds-Karp (Breitensuche, Tiefensuche oder breitester Weg). Er ist zulässig, aber kostenblind.
2. **Restgraph:** jede Kante mit freier Kapazität ist eine **Vorwärtskante** mit Kosten $c$, jede Kante mit Fluss hat eine **Rückkante** mit Kosten $-c$.
3. **Negativer Kreis:** suche im Restgraphen einen geschlossenen Weg mit negativen Gesamtkosten (Bellman-Ford, gedachter Start mit Entfernung 0 zu allen Knoten). Schiebe entlang des Kreises den **Engpass**: die Menge bleibt gleich, die Kosten sinken um Engpass × |Kreiskosten|.
4. **Ende:** findet die Suche keinen negativen Kreis mehr, ist der Fluss kostenminimal für seine Menge. Zu jedem negativen Kreis gibt es umgekehrt eine Verbesserung - deshalb ist „kein negativer Kreis“ genau die Optimalitätsbedingung.
5. **Welcher Kreis?** Klein (1967) nimmt den erstbesten. Da die Kosten ganzzahlig sind, sinken sie um mindestens 1 je Kreis - höchstens (Startkosten − Optimum) Kreise, aber das ist eine Schranke, die von den Kapazitäten abhängt. Der Kreis mit dem **kleinsten Mittelwert** (Kosten je Kante, nach Karp berechnet) gibt eine stark polynomiale Schranke.
6. **Potenziale am Ende:** aus den Entfernungen im Restgraphen entstehen Schattenpreise $\pi$ mit reduzierten Kosten $c+\pi(u)-\pi(v)\ge 0$ auf allen Restkanten - dasselbe Zertifikat wie bei SSP.
        """
    )

st.caption("🎯 Schnellstart – ein Beispielnetz laden:")
names = list(C.PRESETS.keys())
for row in range(0, len(names), 4):
    preset_cols = st.columns(4)
    for col, name in zip(preset_cols, names[row:row + 4]):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    net_key = st.selectbox(
        "Netz", list(C.NETS), key="net_select", format_func=lambda k: C.NETS[k],
        help="Ein zufälliges Distributionsnetz mit Kosten je Einheit, oder eines der festen Lehrnetze: der Umweg (ein einziger Kreis genügt) und die Zuordnung mit Kosten (kostenblinder Fluss 25, billigster 10).",
    )
    selection = st.radio(
        "Welcher negative Kreis?", list(C.SELECTION_LABELS), key="selection_radio", format_func=lambda k: C.SELECTION_LABELS[k],
        help="Klein: der erste Kreis, den Bellman-Ford findet. Zufällig: dieselbe Suche mit gemischter Kantenreihenfolge. Minimum-Mean: der Kreis mit den kleinsten Kosten je Kante (Karp) - im Standardnetz-Mittel 4,1 statt 4,9 Kreise, aber 6717 statt 1509 durchsuchte Kanten. "
             "Nur von S aus ist eine Negativkontrolle: nach dem größten Fluss erreicht S im Restgraphen kaum etwas, die Suche übersieht Kreise und meldet zu früh „fertig“.",
    )
    rule = st.radio(
        "Startfluss", list(C.RULE_LABELS), key="rule_radio", format_func=lambda k: C.RULE_LABELS[k],
        help="Welcher größte Fluss zu Beginn: Breitensuche (Edmonds-Karp), Tiefensuche (Ford-Fulkerson) oder breitester Weg. Alle drei sind kostenblind. Über 40 Netze haben Breitensuche und Tiefensuche dieselbe Startlücke (14,1 %), der breiteste Weg die kleinste (12,0 %) - aber die meisten Kreise.",
    )
    if net_key == "random":
        seed_widget("p_slider")
        p = st.slider("Werke", *bounds("p_slider"), key="p_slider", help="Anzahl der Werke (oben im Netz); Kosten je Einheit 1 bis 5.")
        st.session_state[KEPT["p_slider"]] = p
        seed_widget("d_slider")
        d = st.slider("Verteilzentren", *bounds("d_slider"), key="d_slider", help="Anzahl der Verteilzentren; Umschlagkosten 1 bis 3 je Einheit, Durchsatz 30 bis 60 % der gesamten Werkskapazität.")
        st.session_state[KEPT["d_slider"]] = d
        seed_widget("s_slider")
        s = st.slider("Filialen", *bounds("s_slider"), key="s_slider", help="Anzahl der Filialen (unten im Netz).")
        st.session_state[KEPT["s_slider"]] = s
        seed_widget("density_slider")
        density = st.slider("Netzdichte [%]", *bounds("density_slider"), key="density_slider", step=10, help="Anteil der möglichen Lanes (Werk → Verteilzentrum, Verteilzentrum → Filiale), die es gibt; Kosten je Lane 1 bis 9.")
        st.session_state[KEPT["density_slider"]] = density
        seed_widget("spread_slider")
        spread = st.slider("Streuung der Lane-Breiten [%]", *bounds("spread_slider"), key="spread_slider", step=25, help="0 = alle Lanes einer Stufe gleich breit, 100 = Kapazitäten gleichverteilt von 1 bis zum Doppelten der Grundbreite.")
        st.session_state[KEPT["spread_slider"]] = spread
        seed_widget("load_slider")
        load = st.slider("Auslastung [% der Werkskapazität]", *bounds("load_slider"), key="load_slider", step=10, help="Gesamtnachfrage der Filialen in Prozent der Werkskapazität. Über 100 % kann das Netz die Nachfrage nicht mehr decken.")
        st.session_state[KEPT["load_slider"]] = load
        seed_widget("seed_input")
        seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)
        st.session_state[KEPT["seed_input"]] = seed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Zufalls-Seed. Die Verteilungen über 100 feste Netze weiter unten ändern sich dabei nicht - nur die Marke „Ihre Ziehung“ wandert.")
    else:
        p = int(st.session_state.get(KEPT["p_slider"], C.DEFAULT_P))
        d = int(st.session_state.get(KEPT["d_slider"], C.DEFAULT_D))
        s = int(st.session_state.get(KEPT["s_slider"], C.DEFAULT_S))
        density = int(st.session_state.get(KEPT["density_slider"], C.DEFAULT_DENSITY))
        spread = int(st.session_state.get(KEPT["spread_slider"], C.DEFAULT_SPREAD))
        load = int(st.session_state.get(KEPT["load_slider"], C.DEFAULT_LOAD))
        seed = int(st.session_state.get(KEPT["seed_input"], C.DEFAULT_SEED))
        st.caption("Dieses Netz ist fest - es gibt nichts zu erzeugen. Zahl der Werke, Verteilzentren und Filialen, Netzdichte, Streuung, Auslastung und Seed gehören zum zufälligen Netz.")

sync_query_params({"net_select": net_key, "selection_radio": selection, "rule_radio": rule, "p_slider": int(p), "d_slider": int(d), "s_slider": int(s),
                   "density_slider": int(density), "spread_slider": int(spread), "load_slider": int(load), "seed_input": int(seed)})

# feste Netze ignorieren die Zufallsregler: sonst würden gleiche Netze unter verschiedenen Schlüsseln mehrfach berechnet
params = (net_key, int(p), int(d), int(s), int(density), int(spread), int(load), int(seed))
if net_key in C.FIXED_NETS:
    params = (net_key, C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD, C.DEFAULT_SEED)
with st.spinner("Rechne..."):
    a = _analysis(params, selection, rule)
net, res = a.net, a.result
level, code, dat = ev.verdict(a)
settings = (int(p), int(d), int(s), int(density), int(spread), int(load))
its = res.iterations
n_frames = len(its) + 2                       # Bild 0 = Startfluss, dann ein Kreis je Bild, zuletzt der Beweis
is_fixed = net_key in C.FIXED_NETS

# --- Kreise in Aktion --------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Kreise in Aktion")
owner = (params, selection, rule)
if st.session_state.get("cyc_step_owner") != owner:
    st.session_state["cyc_step"] = n_frames - 1
    st.session_state["cyc_step_owner"] = owner
step_col, play_col = st.columns([5, 2])
with step_col:
    step = st.slider("Bild", 0, n_frames - 1, key="cyc_step", help="Bild 0 ist der Startfluss; jedes weitere Bild löscht einen negativen Kreis; ganz rechts der fertige Fluss und der Optimalitätsbeweis.")
with play_col:
    auto_play = st.button("▶️ Abspielen", width="stretch")
view_slot = st.empty()

cert_pi, cert_ok = ssp.certificate(net, res.flow)
final_pi = tuple(x - cert_pi[net.s] for x in cert_pi) if cert_ok else None
proof_data = ev.proof(net, res.flow, final_pi) if final_pi is not None else None
ssp_curve, start_point, end_point = ev.curve_points(a)


def _cycle_text(it):
    return " → ".join(net.names[v] for v in it.nodes)


def _render(k):
    """Bild k: links das Netz mit dem gelöschten Kreis, rechts Ersparnis und Kostenabstieg; am Ende der Beweis und die Menge-Kosten-Ebene."""
    with view_slot.container():
        c1, c2 = st.columns(2)
        if k >= len(its) + 1:
            c1.markdown(f"**Fertiger Fluss** - Menge {res.value}, Gesamtkosten {res.total}")
            c1.plotly_chart(build_network(net, res.flow, pi=final_pi), width="stretch", key=f"result_map_{k}")
            c2.markdown("**Beweis:** Menge-Kosten-Ebene und Kostenabstieg")
            c2.plotly_chart(build_plane(ssp_curve, start_point, end_point, current=end_point), width="stretch", key=f"proof_plane_{k}")
            c2.plotly_chart(build_descent(res.start_total, its, len(its), a.optimum.total), width="stretch", key=f"proof_descent_{k}")
            if final_pi is None:
                st.caption(f"**Der Restgraph enthält noch einen negativen Kreis:** die Suche „{SEL_SHORT[selection]}“ hat ihn übersehen, der Fluss (Gesamtkosten {res.total}) ist nicht kostenminimal, der billigste Fluss dieser Menge kostet {dat['optimal_total']} ({_pct(dat['end_gap_pct'])} weniger). "
                           "Ein gedachter Start zu allen Knoten findet ihn, ein Start nur bei S nicht.")
            else:
                st.caption(f"Es gibt keinen negativen Kreis mehr: die Schattenpreise π (Knotenfarbe) beweisen es - für **alle {proof_data['checked']} Restkanten** sind die reduzierten Kosten c + π(u) − π(v) ≥ 0 (Vorwärtsrest) bzw. ≤ 0 (Kante mit Fluss); "
                           f"{proof_data['tight']} der {proof_data['flow_arcs']} Flusskanten haben reduzierte Kosten genau 0 (jede nicht volle gehört dazu), die übrigen sind voll. **Kein Fluss dieser Menge ist billiger.** "
                           f"Rechts: Successive Shortest Paths läuft entlang der Kostenkurve nach rechts (jeder Punkt kostenminimal), Cycle-Canceling fällt bei fester Menge {res.value} vom Startfluss (rotes Kreuz, {res.start_total}) auf {res.total}.")
            return
        if k == 0:
            c1.markdown(f"**Start:** der {RULE_SHORT[rule]}-Fluss, Menge {res.value}, Kosten {res.start_total}")
            c2.markdown("**Ersparnis und Kostenabstieg** - noch kein Kreis gelöscht")
            flow_k, path_k = a.start_flow, None
            cap = (f"Der Startfluss ist zulässig und maximal, aber kostenblind: er kostet {res.start_total}, der billigste Fluss dieser Menge {dat['optimal_total']} ({_pct(dat['start_gap_pct'])} weniger)."
                   + (" Er ist schon billigst - es gibt nichts zu tun." if not its and code == "nothing" else " Der erste Schritt sucht im Restgraphen einen Kreis mit negativen Kosten."))
        else:
            it = its[k - 1]
            flow_k = it.flow_after
            path_k = [(e // 2, e % 2 == 0, it.bottleneck) for e in it.cycle]
            back = sum(1 for e in it.cycle if e % 2)
            c1.markdown(f"**Kreis {k}:** {it.bottleneck} Einheiten um einen Kreis mit Kosten {it.cost}")
            c2.markdown(f"**Ersparnis und Kostenabstieg** - Gesamtkosten {it.total}")
            cap = (f"Negativer Kreis: {_cycle_text(it)} - {len(it.cycle)} Kanten ({back} Rückkanten), Kosten je Einheit {it.cost}, Engpass {it.bottleneck}: das spart {it.saving} und senkt die Gesamtkosten auf {it.total}. "
                   f"Durchsucht wurden {it.scanned} Kanten.")
            if selection == "min_mean":
                cap += f" Der Mittelwert der Kosten je Kante ist {it.mean[0] if it.mean[1] == 1 else str(it.mean[0]) + '/' + str(it.mean[1])} - kleiner geht es in diesem Restgraphen nicht."
        c1.plotly_chart(build_network(net, flow_k, path=path_k), width="stretch", key=f"path_map_{k}")
        c2.plotly_chart(build_savings(its, k), width="stretch", key=f"savings_bars_{k}")
        c2.plotly_chart(build_descent(res.start_total, its, k, a.optimum.total), width="stretch", key=f"descent_curve_{k}")
        st.caption(cap)


if auto_play:
    for k in range(n_frames):
        _render(k)
        time.sleep(min(0.6, 8.0 / max(n_frames, 1)))
    step = n_frames - 1
else:
    _render(step)

st.caption("Links: Breite ~ Fluss (dunkelblau = Kante voll); grün = Kanten des gelöschten Kreises (+Menge × Kosten je Einheit), orange gestrichelt = Rückkante (nimmt Fluss zurück, Kosten negativ). "
           "Rechts oben: Balken = Ersparnis je Kreis (Engpass × |Kreiskosten|); rechts unten: Gesamtkosten nach jedem Kreis, gestrichelt das Optimum von Successive Shortest Paths - die Kosten fallen bei fester Menge.")

st.markdown("---")

# --- Kernfrage ---------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Vom teuren zum billigen Fluss")
st.caption("**Kreise** = wie viele negative Kreise gelöscht werden; **durchsuchte Kanten** = Aufwand (jede in einem Bellman-Ford- oder Karp-Durchlauf angesehene Restkante, auch die des letzten, ergebnislosen Durchlaufs), nie Sekunden. Zum Vergleich: SSP baut denselben Fluss in Runden auf.")
m1, m2, m3, m4 = st.columns(4)
if net.logistic:
    m1.metric("Menge", f"{dat['value']} von {dat['demand']}", delta=f"{_pct(dat['share'])} der Nachfrage", delta_color="off", help="Menge des Startflusses - Cycle-Canceling ändert sie nicht.")
else:
    m1.metric("Menge", f"{dat['value']}", help="Menge von S nach T; sie bleibt während des ganzen Verfahrens gleich.")
m2.metric("Gesamtkosten", f"{dat['total']}", delta=f"Start {dat['start_total']}" + (f" (−{_pct(ev.pct(dat['start_total'] - dat['total'], dat['start_total']))})" if dat["start_total"] != dat["total"] else ""), delta_color="off",
          help="Kosten des Flusses am Ende, im Delta die des Startflusses und die Ersparnis in % der Startkosten.")
m3.metric("Kreise", f"{dat['cycles']}", delta=f"SSP: {dat['ssp_rounds']} Runden", delta_color="off", help=f"Gelöschte negative Kreise; der längste hat {dat['longest']} Kanten, insgesamt {dat['back_arcs']} Rückkanten. Obere Schranke bei ganzzahligen Kosten: {dat['bound']} (Startkosten − Optimum).")
m4.metric("Durchsuchte Kanten", f"{dat['scanned']}", delta=f"SSP: {dat['ssp_scanned']}", delta_color="off", help="Successive Shortest Paths braucht für denselben Fluss (von Grund auf) so viele durchsuchte Kanten.")

if code == "optimal":
    served = ""
    if net.logistic:
        served = " Die gesamte Nachfrage wird geliefert." if dat["value"] == dat["demand"] else f" Das Netz schafft höchstens {dat['value']} von {dat['demand']} Einheiten ({_f(dat['share'], 0)} %); Engpass: **{_stage_text(dat['stage_caps'])}**."
    st.success(f"✅ Kostenminimal: {'1 negativer Kreis senkt' if dat['cycles'] == 1 else str(dat['cycles']) + ' negative Kreise senken'} die Kosten von {dat['start_total']} auf {dat['total']} ({_pct(dat['start_gap_pct'])} Aufschlag beseitigt); der erste Kreis bringt {dat['first_share']:.0f} % der Ersparnis.{served} "
               f"Die Suche dafür ({SEL_SHORT[selection]}) kostet {dat['scanned']} durchsuchte Kanten - SSP braucht {dat['ssp_scanned']}.")
elif code == "nothing":
    st.info(f"ℹ️ Der Startfluss ({RULE_SHORT[rule]}) ist schon kostenminimal (Kosten {dat['start_total']}): es gibt keinen negativen Kreis, nichts zu tun. Das passiert selten - über 100 Netze in 2 von 100.")
elif code == "wrong":
    st.warning(f"⚠️ **Nicht kostenminimal:** {SEL_SHORT[selection]} löscht {dat['cycles']} Kreise und meldet dann „fertig“, der Fluss kostet {dat['total']}, der billigste dieser Menge {dat['optimal_total']} - {_pct(dat['end_gap_pct'])} mehr als nötig. "
               "Die Suche sieht nur, was von S aus im Restgraphen erreichbar ist; ein negativer Kreis muss dort nicht liegen.")
else:
    st.warning("⚠️ Es kommt gar nichts an: kein Weg führt von einem Werk über ein Verteilzentrum zu einer Filiale. Die Menge ist 0, es gibt keinen Fluss und keinen Kreis.")

if is_fixed:
    st.info("Festes Netz: es gibt nur diese eine Ziehung. Für die Verteilungen über viele Netze ein zufälliges Distributionsnetz wählen.")
    dist = None
else:
    dist = ev.distribution(*settings, rule)
    st.markdown(f"**Nicht nur dieses eine Netz:** {len(C.DIST_SEEDS)} feste Netze mit denselben Einstellungen (Werke {p}, Verteilzentren {d}, Filialen {s}, Netzdichte {density} %, Streuung {spread} %, Auslastung {load} %), getrennt vom Seed oben; Startfluss: {RULE_SHORT[rule]}.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Kreise", _f(dist[f"cycles_{selection}_mean"], 1), delta=f"Median {_f(dist[f'cycles_{selection}_median'], 0)}, höchstens {dist[f'cycles_{selection}_max']}", delta_color="off", help=f"Mittel über die Netze ({SEL_SHORT[selection]}); SSP braucht {_f(dist['ssp_rounds_mean'], 1)} Runden.")
    p2.metric("Startlücke", _pct(dist["gap_pct_mean"]), delta=f"Median {_pct(dist['gap_pct_median'])}", delta_color="off", help="Mittel über die Netze: Mehrkosten des Startflusses gegen den billigsten Fluss derselben Menge.")
    p3.metric("Durchsuchte Kanten", _f(dist[f"scans_{selection}_mean"], 0), delta=f"SSP {_f(dist['ssp_scanned_mean'], 0)}", delta_color="off", help="Mittel über die Netze: Cycle-Canceling gegen SSP.")
    p4.metric("Am Ende kostenminimal", _share(dist["share_optimal"][selection]), delta=SEL_SHORT[selection], delta_color="off", help="Anteil der Netze, in denen kein negativer Kreis übrig bleibt.")
    st.plotly_chart(build_gap_hist(dist["cols"]["gap_pct"], current=dat["start_gap_pct"] if net.logistic else None), width="stretch", key="gap_chart")
    st.caption(f"Über {len(C.DIST_SEEDS)} feste Netze: der Startfluss kostet im Mittel {_pct(dist['gap_pct_mean'])} mehr als nötig (Median {_pct(dist['gap_pct_median'])}, höchstens {_pct(dist['gap_pct_max'])}); nur in {_share(dist['share_nothing'])} der Netze ist er zufällig schon billigst.")

st.markdown("---")

# --- Vergleich -----------------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – die Kreiswahlen im Vergleich"):
    st.markdown("**Was jede Kreiswahl für das Netz oben findet** (derselbe Startfluss)")
    rows = []
    for name in cy.SELECTIONS:
        r = cy.cancel(net, a.start_flow, name, keep_trace=False)
        rows.append((SEL_SHORT[name], r.n_cycles, r.total, r.scanned_total, "ja" if r.total == a.optimum.total else f"nein (+{_pct(ev.pct(r.total - a.optimum.total, a.optimum.total))})"))
    st.table({"Kreiswahl": [r[0] for r in rows], "Kreise": [r[1] for r in rows], "Gesamtkosten": [r[2] for r in rows], "durchsuchte Kanten": [r[3] for r in rows], "kostenminimal": [r[4] for r in rows]})
    st.caption("Klein und die zufällige Reihenfolge sowie Minimum-Mean landen bei denselben Kosten (der Weg dorthin darf sich unterscheiden). „Nur von S aus“ ist nur eine Negativkontrolle.")
    st.markdown("**Protokoll der Kreise** (aktuelle Einstellung)")
    if its:
        st.dataframe({"Kreis": list(range(1, len(its) + 1)), "Knoten": [_cycle_text(i) for i in its], "Kanten": [len(i.cycle) for i in its], "Rückkanten": [sum(1 for e in i.cycle if e % 2) for i in its],
                      "Kosten je Einheit": [i.cost for i in its], "Engpass": [i.bottleneck for i in its], "Ersparnis": [i.saving for i in its], "Gesamtkosten": [i.total for i in its], "durchsuchte Kanten": [i.scanned for i in its]},
                     hide_index=True, width="stretch")
    else:
        st.caption("Kein Kreis gelöscht.")

st.markdown("---")

# --- Experimente -------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Beliebiger Kreis oder Minimum-Mean?")
st.caption("Klein löscht den ersten Kreis, den Bellman-Ford findet - in fester oder zufälliger Kantenreihenfolge. Goldberg und Tarjan nehmen den Kreis mit den kleinsten Kosten je Kante und bekommen dafür eine stark polynomiale Schranke. Was bringt das in der Praxis?")
if dist is None:
    st.info("Für die Verteilung über viele Netze ein zufälliges Distributionsnetz wählen. Für das feste Netz oben zeigt der Vergleich im Expander alle Kreiswahlen.")
else:
    c = dist["cols"]
    fewer = sum(x < y for x, y in zip(c["cycles_min_mean"], c["cycles_klein"]))
    same = sum(x == y for x, y in zip(c["cycles_min_mean"], c["cycles_klein"]))
    more = sum(x > y for x, y in zip(c["cycles_min_mean"], c["cycles_klein"]))
    st.plotly_chart(build_cycles_compare(c["cycles_klein"], c["cycles_klein_random"], c["cycles_min_mean"], current=dat["cycles"] if (net.logistic and selection != "from_s") else None), width="stretch", key="cycles_chart")
    st.table({"Kreiswahl": ["Klein: beliebig", "Klein: zufällige Reihenfolge", "Minimum-Mean"], "Kreise (Mittel)": [_f(dist[f"cycles_{k}_mean"], 2) for k in ("klein", "klein_random", "min_mean")],
              "Kreise (Median)": [_f(dist[f"cycles_{k}_median"], 0) for k in ("klein", "klein_random", "min_mean")], "größter Wert": [dist[f"cycles_{k}_max"] for k in ("klein", "klein_random", "min_mean")],
              "durchsuchte Kanten (Mittel)": [_f(dist[f"scans_{k}_mean"], 0) for k in ("klein", "klein_random", "min_mean")], "Anteil der Ersparnis im ersten Kreis": [_share(dist[f"first_{k}_mean"]) for k in ("klein", "klein_random", "min_mean")],
              "kostenminimal": [_share(dist["share_optimal"][k]) for k in ("klein", "klein_random", "min_mean")]})
    st.caption(f"Über {len(C.DIST_SEEDS)} feste Netze: Minimum-Mean braucht in {fewer} Netzen weniger Kreise als Klein, in {same} gleich viele und in {more} mehr - im Mittel {_f(dist['cycles_min_mean_mean'], 2)} statt {_f(dist['cycles_klein_mean'], 2)}. "
               f"Sein erster Kreis bringt {_share(dist['first_min_mean_mean'])} der Ersparnis (Klein: {_share(dist['first_klein_mean'])}). Dafür kostet jede Suche - Karp rechnet n Durchläufe über alle Restkanten, Bellman-Ford hört bei einem Kreis früh auf - im Mittel {_f(dist['scans_min_mean_mean'], 0)} statt {_f(dist['scans_klein_mean'], 0)} durchsuchte Kanten. "
               "Alle Kreiswahlen enden im Optimum.")

st.subheader("🔬 Startfluss: wie teuer muss er sein?")
st.caption("Je teurer der Startfluss, desto mehr gibt es zu räumen - aber führt ein größerer Abstand auch zu mehr Kreisen? Breitensuche, Tiefensuche und breitester Weg liefern drei verschiedene größte Flüsse.")
if is_fixed:
    st.info("Für dieses Experiment ein zufälliges Distributionsnetz wählen.")
else:
    rule_rows, corr = ev.rule_table(*settings)
    st.table({"Startfluss": [RULE_SHORT[r["rule"]] for r in rule_rows], "Startlücke (Mittel)": [_pct(r["gap_mean"]) for r in rule_rows], "Startlücke (Median)": [_pct(r["gap_median"]) for r in rule_rows],
              "Kreise (Mittel, Klein)": [_f(r["cycles_mean"], 2) for r in rule_rows], "größter Wert": [r["cycles_max"] for r in rule_rows], "immer kostenminimal": ["ja" if r["all_optimal"] else "nein" for r in rule_rows]})
    st.caption(f"Mittel über 40 feste Netze je Startfluss. Der breiteste Weg liefert die kleinste Startlücke, braucht aber die meisten Kreise; über alle 120 Läufe ist die Korrelation von Lücke und Kreiszahl nur {_f(corr, 2)}. "
               "Ein größerer Abstand geht also mit mehr Kreisen einher, aber nur lose.")

st.subheader("🔬 Schranke gegen Realität – und Kapazitäten × 1000")
st.caption("Bei ganzzahligen Kosten sinken die Kosten mit jedem Kreis um mindestens 1: es gibt höchstens (Startkosten − Optimum) Kreise. Diese Schranke hängt an den Kapazitäten, nicht an der Netzgröße (**pseudopolynomial**). Wie weit ist sie von der Wirklichkeit weg?")
if dist is None:
    st.info("Für die Verteilung über viele Netze ein zufälliges Distributionsnetz wählen. Für das feste Netz zeigt die Kennzahl „Kreise“ oben die Schranke im Hilfetext.")
else:
    b1, b2, b3 = st.columns(3)
    b1.metric("Kreise ÷ Schranke", _pct(100 * dist["bound_ratio_mean"]), delta=f"höchstens {_pct(100 * dist['bound_ratio_max'])}", delta_color="off", help="Gelöschte Kreise (Klein) im Verhältnis zu Startkosten − Optimum, Mittel und Maximum über die Netze.")
    b2.metric("Schranke", _f(dist["gap_mean"], 0), delta=f"Median {_f(dist['gap_median'], 0)}", delta_color="off", help="Startkosten − Optimum, Mittel über die Netze.")
    b3.metric("Kreise (Klein)", _f(dist["cycles_klein_mean"], 2), delta=f"höchstens {dist['cycles_klein_max']}", delta_color="off", help="Mittel über die Netze.")
    if st.button("Kapazitäten mit 1, 10, 100 und 1000 multiplizieren (10 Netze)", key="capacity_start"):
        st.session_state["capacity_on"] = settings
    if st.session_state.get("capacity_on") == settings:
        cap_rows = ev.capacity_table(*settings)
        st.table({"Kapazitäten ×": [str(r["k"]) for r in cap_rows], "Kreise (Klein)": [_f(r["cycles_klein"], 1) for r in cap_rows], "Kreise (Minimum-Mean)": [_f(r["cycles_min_mean"], 1) for r in cap_rows],
                  "durchsuchte Kanten (Klein)": [_int(r["scans_klein"]) for r in cap_rows], "Schranke (Startkosten − Optimum)": [_int(r["gap"]) for r in cap_rows], "Flusswert": [_int(r["value"]) for r in cap_rows]})
        st.caption("Mittel über 10 feste Netze. Die Kreiszahl und die durchsuchten Kanten bleiben gleich (Startfluss und Kreise skalieren mit), die Schranke wächst mit dem Faktor. "
                   "Die Schranke ist ein Worst-Case-Satz; konstruierte Netze mit sehr vielen kleinen Kreisen gibt es, hier kommen sie nicht vor.")

st.subheader("🔬 Cycle-Canceling gegen Successive Shortest Paths")
st.caption("Beide enden im selben, kostenminimalen Fluss. Cycle-Canceling braucht dafür weniger Iterationen als SSP Runden - aber wie steht es um den Aufwand je Iteration?")
if dist is None:
    st.info("Für die Verteilung über viele Netze ein zufälliges Distributionsnetz wählen. Für das feste Netz oben zeigen die Kennzahlen „Kreise“ und „Durchsuchte Kanten“ den Vergleich.")
else:
    fewer_ssp = sum(x < y for x, y in zip(dist["cols"]["cycles_klein"], dist["cols"]["ssp_rounds"]))
    st.caption(f"Über {len(C.DIST_SEEDS)} feste Netze: Klein löscht in {fewer_ssp} Netzen weniger Kreise, als SSP Runden braucht ({_f(dist['cycles_klein_mean'], 2)} gegen {_f(dist['ssp_rounds_mean'], 2)} im Mittel). Die durchsuchten Kanten: Klein {_f(dist['scans_klein_mean'], 0)}, Minimum-Mean {_f(dist['scans_min_mean_mean'], 0)}, SSP {_f(dist['ssp_scanned_mean'], 0)} - "
               "Ein Grund: SSP sucht mit Dijkstra auf reduzierten Kosten und beendet jede Suche beim Erreichen von T, Cycle-Canceling muss das ganze Netz nach einem Kreis durchsuchen.")
    if st.button("Netze von 12 bis 166 Knoten durchrechnen (dauert einige Sekunden)", key="scaling_start"):
        st.session_state["scaling_on"] = True
    if st.session_state.get("scaling_on"):
        with st.spinner("Rechne 6 Netzgrößen × 10 Netze × 3 Verfahren..."):
            sc_rows = ev.scaling()
        slopes = ev.slopes(sc_rows)
        st.plotly_chart(build_scaling(sc_rows), width="stretch", key="scaling_chart")
        st.table({"Werke / DCs / Filialen": [f"{r['size'][0]} / {r['size'][1]} / {r['size'][2]}" for r in sc_rows], "Knoten": [_f(r["n"], 0) for r in sc_rows], "Kanten": [_f(r["m"], 0) for r in sc_rows],
                  "Kreise (Klein)": [_f(r["cycles_klein"], 1) for r in sc_rows], "Kreise (Minimum-Mean)": [_f(r["cycles_min_mean"], 1) for r in sc_rows], "SSP-Runden": [_f(r["ssp_rounds"], 1) for r in sc_rows],
                  "Klein": [_int(r["klein"]) for r in sc_rows], "Minimum-Mean": [_int(r["min_mean"]) for r in sc_rows], "SSP": [_int(r["ssp"]) for r in sc_rows], "Klein ÷ SSP": [_f(r["klein"] / r["ssp"], 1) for r in sc_rows]})
        st.caption(f"Mittel über 10 feste Netze je Größe (Netzdichte 60 %, Streuung und Auslastung auf den Standardwerten, Startfluss Breitensuche). Steigung im doppelt logarithmischen Diagramm: Klein {_f(slopes['klein'], 2)}, Minimum-Mean {_f(slopes['min_mean'], 2)}, SSP {_f(slopes['ssp'], 2)}. "
                   f"Klein liegt in jeder Größe über SSP ({_f(min(r['klein'] / r['ssp'] for r in sc_rows), 1)}- bis {_f(max(r['klein'] / r['ssp'] for r in sc_rows), 1)}-fach), Minimum-Mean bei {_f(sc_rows[-1]['min_mean'] / sc_rows[-1]['ssp'], 0)}-fach im größten Netz. "
                   "Jede Iteration sucht im ganzen Restgraphen; die Zahl der Iterationen wächst dabei etwa mit der Kantenzahl.")

st.subheader("🔬 Nur von S aus suchen")
st.caption("Man könnte meinen, negative Kreise müssten von S erreichbar sein. Nach einem größten Fluss ist S aber vollständig gesättigt: im Restgraphen führt fast keine Kante mehr von S weg. Was passiert, wenn Bellman-Ford nur dort sucht?")
if dist is None:
    st.info("Für die Verteilung über viele Netze ein zufälliges Distributionsnetz wählen. Das Preset „Umweg“ zeigt den Fall im Kleinen: die Suche von S aus findet nichts, der Fluss bleibt bei 9 statt 2.")
else:
    zero = sum(x == 0 for x in dist["cols"]["cycles_from_s"])
    wrong = [g for g in dist["cols"]["excess_from_s"] if g > 0]
    g1, g2, g3 = st.columns(3)
    g1.metric("Am Ende kostenminimal", _share(dist["share_optimal"]["from_s"]), help="Anteil der Netze, in denen die Suche nur von S aus alle negativen Kreise findet.")
    g2.metric("Netze ohne einen einzigen Kreis", f"{zero}", help="Die Suche von S aus findet gar nichts und meldet sofort „fertig“.")
    g3.metric("Mehrkosten dort (Mittel)", _pct(sum(wrong) / len(wrong) if wrong else 0.0), delta=f"höchstens {_pct(max(wrong) if wrong else 0.0)}", delta_color="off", help="Nur die Netze, in denen die Suche von S aus etwas übersieht.")
    st.caption(f"Über {len(C.DIST_SEEDS)} feste Netze übersieht die Suche von S aus in {100 - round(100 * dist['share_optimal']['from_s'])} Netzen negative Kreise - meist ganz, ohne jede Warnung; der Fluss ist dann im Mittel {_pct(sum(wrong) / len(wrong) if wrong else 0.0)} zu teuer. "
               "Richtig ist der gedachte Start zu **allen** Knoten mit Entfernung 0: er findet einen negativen Kreis überall im Restgraphen. Im Endbild schlägt der Beweis fehl.")

st.markdown("---")

# --- Grenzen -----------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist - und wer setzt an |
|---|---|
| **Es gibt einen zulässigen Startfluss** | Cycle-Canceling braucht die Menge schon: erst ein größter Fluss (Edmonds-Karp), dann die Kosten. Wo die Menge erst aufgebaut wird, ist SSP die natürliche Wahl. **Ansatzpunkt: Successive Shortest Paths** (Stück 4). |
| **Die Suche kostet wenig** | Jede Iteration durchsucht das ganze Netz nach einem Kreis: Bellman-Ford O(nm), Karp O(nm) mit O(n²) Speicher. Auf diesen Netzen ist SSP um ein Vielfaches billiger, auch wenn es mehr Runden braucht. **Ansatzpunkt: Netzwerksimplex** (Demo „network-flow-demo“): eine Baumstruktur statt einer neuen Suche je Kreis. |
| **Ganzzahlige Kosten, kleine Kapazitäten** | Klein braucht höchstens (Startkosten − Optimum) Kreise - pseudopolynomial. Minimum-Mean bringt eine stark polynomiale Schranke, in der Praxis aber nur wenige Kreise weniger. **Ansatzpunkt: Cost Scaling** (Stück 6, gebaut): ε-Optimalität statt exakter Kreise. |
| **Ein Gut, teilbar** | Alle Waren sind gleich und beliebig teilbar. Mehrere Güter auf gemeinsamen Kanten machen den Fluss im Allgemeinen gebrochen. **Ansatzpunkt: Mehrgüterfluss** (gebaut: multicommodity-demo). |
| **Keine Zeit** | Ein Fluss ist eine Momentaufnahme; Wartezeiten und Fahrpläne fehlen. **Ansatzpunkt:** Zeit-Raum-Netz in der Demo „leercontainer-demo“. |
"""
)
st.caption("Die Netzwerkfluss-Linie ist als Ganzes geplant: Edmonds-Karp, Dinic, Push-Relabel, Successive Shortest Paths, Cycle-Canceling (dieses Stück), Cost Scaling (gebaut), Mehrgüterfluss (gebaut), Column Generation (gebaut), Garg-Könemann (gebaut), Fixkosten-Netzwerkdesign, Benders-Zerlegung und Slope Scaling - bisher sind die ersten neun gebaut.")

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Modell (Min-Cost-Flow).** Gerichteter Graph $G=(V,E)$ mit Quelle $s$, Senke $t$, ganzzahligen Kapazitäten $u_e$ und Kosten $c_e\ge 0$ je Einheit. Gesucht ist ein Fluss $f$ der Menge $F$ mit minimalen Kosten $\sum_e c_e f_e$.

**Restgraph.** Zu jeder Kante $e=(u,v)$ gibt es die Vorwärtskante $(u,v)$ mit Rest $u_e-f_e$ und Kosten $c_e$ und die Rückkante $(v,u)$ mit Rest $f_e$ und Kosten $-c_e$.

**Satz (kein negativer Kreis).** Ein Fluss $f$ ist kostenminimal unter allen Flüssen seines Wertes genau dann, wenn $G_f$ keinen Kreis mit negativen Gesamtkosten enthält. *Beweis:* ist $C$ ein negativer Kreis, verbessert das Verschieben von $\delta=\min_{e\in C}r_e$ Einheiten um $C$ den Fluss um $\delta\,c(C)<0$ - er war nicht optimal. Ist $f^\ast$ ein billigerer Fluss gleichen Wertes, ist $f^\ast-f$ eine Zirkulation im Restgraphen, zerlegbar in Kreise; einer davon ist negativ.

**Cycle-Canceling.** Wiederhole: finde einen negativen Kreis $C$ in $G_f$, verschiebe den Engpass $\delta$. Die Menge bleibt gleich, die Kosten sinken um $\delta\,|c(C)|\ge 1$. Bei ganzzahligen Kosten endet das nach höchstens $c(f_0)-c(f^\ast)$ Iterationen (**Klein 1967**, pseudopolynomial).

**Bellman-Ford mit gedachtem Start.** Setze $d(v)=0$ für alle $v$ (ein gedachter Start mit Kanten der Kosten 0 zu allen Knoten) und relaxiere; ein negativer Kreis liegt im Vorgänger-Graphen, sobald $d$ nach $n$ Durchläufen noch sinkt. Ein Start nur bei $s$ findet nur Kreise, die von $s$ erreichbar sind.

**Minimum-Mean-Cycle (Karp 1978).** $\mu^\ast=\min_C \frac{c(C)}{|C|}$. Mit $D_k(v)$ = Kosten des billigsten Weges mit genau $k$ Kanten, der irgendwo beginnt und in $v$ endet, gilt $\mu^\ast=\min_v\max_{0\le k<n}\frac{D_n(v)-D_k(v)}{n-k}$; der Weg mit $n$ Kanten zum besten $v$ enthält einen Kreis mit Mittelwert $\mu^\ast$. Laufzeit $O(nm)$.

**Goldberg und Tarjan (1989).** Löscht man stets den Kreis mit kleinstem Mittelwert, ist $\mu^\ast$ nicht fallend (die Beträge $|\mu^\ast|$ sinken), und die Zahl der Iterationen ist stark polynomial: $O(nm\log(nC))$ bzw. $O(n\,m^2\log n)$ ohne Abhängigkeit von den Kosten.

**Zertifikat.** Am Ende gibt es Potenziale $\pi$ (Entfernungen im Restgraphen von einem gedachten Start) mit $c(u,v)+\pi(u)-\pi(v)\ge 0$ für alle Restkanten - dieselben Schattenpreise wie bei SSP. **Netzwerksimplex:** jeder Pivot löscht einen Fundamentalkreis eines aufspannenden Baums.

Implementiert in `cyc_scenario.py` (Netze, eigener Zufallsgenerator), `cyc_algorithm.py` (Bellman-Ford mit Kreiserkennung im Vorgänger-Graphen, Karp, Löschen mit Engpass), `cyc_edmonds_karp.py` und `cyc_ssp.py` (Kopien der Vorgänger-Demos als Startfluss und Vergleichsbasis), `cyc_evaluation.py` (Kennzahlen, Verteilungen, Experimente).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
