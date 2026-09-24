"""Rauchtests der Streamlit-Oberfläche per AppTest: Standard, jedes Preset, alle Kreiswahlen und Startflüsse, Randgrößen, Schritt-Zustand, ausgeblendete Regler, Permalink, Experimente auf Abruf, Schlüssel und Achsensperre."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import cyc_constants as C
import cyc_evaluation as ev
import cyc_scenario as sc
from cyc_presets import PRESET_KEYS

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"

# Anfang der Meldung zum gezeigten Netz (Streamlit legt das führende Emoji in `icon`, nicht in `value`)
EXPECTED = {
    "🚚 Zufallsnetz": "Kostenminimal: 7 negative Kreise senken die Kosten von 1339 auf 1197 (11,9 % Aufschlag beseitigt); der erste Kreis bringt 25 % der Ersparnis. Die gesamte Nachfrage wird geliefert. Die Suche dafür (Klein: beliebig) kostet 2052 durchsuchte Kanten - SSP braucht 824.",
    "🎯 Minimum-Mean": "Kostenminimal: 5 negative Kreise senken die Kosten von 1074 auf 904 (18,8 % Aufschlag beseitigt); der erste Kreis bringt 35 % der Ersparnis. Das Netz schafft höchstens 69 von 77 Einheiten (90 %); Engpass: **Lane DC → Filiale 8**. Die Suche dafür (Minimum-Mean) kostet 8436 durchsuchte Kanten - SSP braucht 702.",
    "🌲 Tiefensuche als Start": "Kostenminimal: 14 negative Kreise senken die Kosten von 1401 auf 1197 (17,0 % Aufschlag beseitigt)",
    "📏 Breitester Weg als Start": "Kostenminimal: 11 negative Kreise senken die Kosten von 1396 auf 1197 (16,6 % Aufschlag beseitigt)",
    "⚠️ Nur von S aus": "**Nicht kostenminimal:** nur von S aus löscht 0 Kreise und meldet dann „fertig“, der Fluss kostet 1372, der billigste dieser Menge 1051 - 30,5 % mehr als nötig.",
    "🏭 Werke knapp": "Kostenminimal: 14 negative Kreise senken die Kosten von 1526 auf 1403 (8,8 % Aufschlag beseitigt); der erste Kreis bringt 11 % der Ersparnis. Das Netz schafft höchstens 89 von 118 Einheiten (75 %); Engpass: **Werkskapazität 89**.",
    "🔀 Umweg": "Kostenminimal: 1 negativer Kreis senkt die Kosten von 9 auf 2 (350,0 % Aufschlag beseitigt); der erste Kreis bringt 100 % der Ersparnis.",
    "💑 Zuordnung mit Kosten": "Kostenminimal: 4 negative Kreise senken die Kosten von 25 auf 10 (150,0 % Aufschlag beseitigt); der erste Kreis bringt 20 % der Ersparnis.",
}


def _run(setup=None, timeout=600):
    at = AppTest.from_file(str(APP), default_timeout=timeout)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if setup is not None:
        setup(at)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    return at


def _apply(at, p):
    for key, state_key in PRESET_KEYS.items():
        at.session_state[state_key] = p[key]


def _labels(at):
    return {w.label for w in list(at.sidebar.slider) + list(at.sidebar.selectbox) + list(at.sidebar.number_input) + list(at.sidebar.radio)}


def _texts(at):
    return [e.value for e in list(at.success) + list(at.warning) + list(at.info)]


def _has(at, prefix):
    return any(t.startswith(prefix) for t in _texts(at))


def _step(at):
    found = [s for s in at.slider if s.key == "cyc_step"]
    return found[0] if found else None


def _metric(at, label):
    return [m.value for m in at.metric if m.label == label]


def _captions(at):
    return [c.value for c in at.caption]


def test_default_renders_without_exception():
    at = _run()
    assert any("Kreise in Aktion" in m.value for m in at.markdown)
    assert _has(at, EXPECTED["🚚 Zufallsnetz"]) and not at.error
    assert _metric(at, "Menge")[0] == "76 von 76" and _metric(at, "Gesamtkosten")[0] == "1197" and _metric(at, "Kreise")[0] == "7" and _metric(at, "Durchsuchte Kanten")[0] == "2052"


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_renders_with_its_verdicts(name):
    at = _run(lambda a: _apply(a, C.PRESETS[name]))
    assert _has(at, EXPECTED[name]), _texts(at)
    if C.PRESETS[name]["net"] in C.FIXED_NETS:
        assert any(t.startswith("Festes Netz") for t in _texts(at))
    else:
        assert any(t.startswith("**Nicht nur dieses eine Netz:**") for t in [m.value for m in at.markdown])


@pytest.mark.parametrize("rule", list(C.RULE_LABELS))
@pytest.mark.parametrize("selection", list(C.SELECTION_LABELS))
def test_every_selection_and_start_flow_renders_and_the_proof_frame_tells_optimal_from_wrong(selection, rule):
    def setup(at):
        at.session_state["selection_radio"] = selection
        at.session_state["rule_radio"] = rule
    at = _run(setup)
    assert not at.error
    proof = " ".join(_captions(at))
    if selection == "from_s" and ev.verdict(ev.analyse(sc.generate(3, 3, 8, 60, 50, 90, C.DEFAULT_SEED), selection, rule))[1] == "wrong":
        assert "Der Restgraph enthält noch einen negativen Kreis" in proof
    else:
        assert "Es gibt keinen negativen Kreis mehr" in proof


def test_the_wrong_search_shows_a_failed_proof():
    at = _run(lambda a: _apply(a, C.PRESETS["⚠️ Nur von S aus"]))
    assert "Der Restgraph enthält noch einen negativen Kreis" in " ".join(_captions(at)) and _has(at, "**Nicht kostenminimal:**")


def test_extreme_sizes_render():
    for p, d, s, dens, spread, load in ((C.P_MIN, C.D_MIN, C.S_MIN, C.DENSITY_MIN, C.SPREAD_MIN, C.LOAD_MIN), (C.P_MAX, C.D_MAX, C.S_MAX, C.DENSITY_MAX, C.SPREAD_MAX, C.LOAD_MAX),
                                        (C.P_MIN, C.D_MAX, C.S_MAX, C.DENSITY_MIN, C.SPREAD_MAX, C.LOAD_MAX), (C.P_MAX, C.D_MIN, C.S_MIN, C.DENSITY_MAX, C.SPREAD_MIN, C.LOAD_MIN)):
        def setup(at, vals=(p, d, s, dens, spread, load)):
            for key, value in zip(("p_slider", "d_slider", "s_slider", "density_slider", "spread_slider", "load_slider"), vals):
                at.session_state[key] = value
        at = _run(setup)
        step = _step(at)
        assert step is not None and step.value == step.max


def test_a_net_where_nothing_arrives_renders_and_says_so():
    """Zwei Werke, sechs Verteilzentren, drei Filialen, dünnes Netz: kein Weg von S nach T, es gibt keinen Fluss und keinen Kreis."""
    def setup(at):
        for key, value in (("p_slider", 2), ("d_slider", 6), ("s_slider", 3), ("density_slider", 20), ("spread_slider", 50), ("load_slider", 90), ("seed_input", 8)):
            at.session_state[key] = value
    at = _run(setup)
    assert _has(at, "Es kommt gar nichts an") and _metric(at, "Menge")[0].startswith("0 von ")
    assert _step(at).max == 1 and _step(at).value == 1                          # Startfluss und Beweis, kein Kreis


def test_a_net_whose_start_flow_is_already_cheapest_says_nothing_to_do():
    seed = next(s for s in C.DIST_SEEDS if ev.verdict(ev.analyse(sc.generate(3, 3, 8, 60, 50, 90, s)))[1] == "nothing")
    at = _run(lambda a: a.session_state.__setitem__("seed_input", seed))
    assert _has(at, "Der Startfluss (Breitensuche) ist schon kostenminimal") and _step(at).max == 1


def test_hidden_controls_follow_the_net():
    def labels_for(net):
        return _labels(_run(lambda a: a.session_state.__setitem__("net_select", net)))
    random_labels, fixed = labels_for("random"), labels_for("detour")
    assert {"Netz", "Welcher negative Kreis?", "Startfluss", "Werke", "Verteilzentren", "Filialen", "Netzdichte [%]", "Streuung der Lane-Breiten [%]", "Auslastung [% der Werkskapazität]", "Zufalls-Seed"} <= random_labels
    assert fixed == {"Netz", "Welcher negative Kreis?", "Startfluss"}                                # keine toten Regler bei festen Netzen


def test_hidden_slider_values_come_back_when_the_random_net_is_shown_again():
    at = _run(lambda a: a.session_state.__setitem__("density_slider", 80))
    at.session_state["net_select"] = "detour"
    at.run()
    at.session_state["net_select"] = "random"
    at.run()
    assert not at.exception and at.slider(key="density_slider").value == 80


def test_step_slider_returns_to_the_last_frame_when_the_net_changes():
    at = _run()
    assert _step(at).max == 8 and _step(at).value == 8                          # Startfluss + 7 Kreise + Beweis
    _step(at).set_value(4)
    at.run()
    assert _step(at).value == 4
    at.session_state["net_select"] = "detour"
    at.run()
    assert not at.exception and _step(at).value == 2 == _step(at).max


def test_step_captions_for_start_cycles_min_mean_and_proof():
    at = _run()
    for k, needle in ((0, "Der Startfluss ist zulässig und maximal, aber kostenblind"), (1, "Negativer Kreis:"), (1, "Durchsucht wurden"), (8, "Es gibt keinen negativen Kreis mehr")):
        _step(at).set_value(k)
        at.run()
        assert not at.exception and any(needle in c for c in _captions(at)), (k, needle)
    at = _run(lambda a: a.session_state.__setitem__("selection_radio", "min_mean"))
    _step(at).set_value(1)
    at.run()
    assert any("kleiner geht es in diesem Restgraphen nicht" in c for c in _captions(at))


def test_play_runs_through_all_frames_without_duplicate_chart_keys():
    """Beim Abspielen entstehen in einem Lauf mehrere Diagramme mit demselben Namen - die Schlüssel tragen deshalb den Schritt."""
    at = _run(lambda a: a.session_state.__setitem__("net_select", "assignment"))
    [b for b in at.button if b.label == "▶️ Abspielen"][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_permalink_parameters_are_clamped_and_snapped():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["density"] = "9999"
    at.query_params["spread"] = "abc"
    at.query_params["p"] = "-5"
    at.run()
    assert not at.exception
    assert at.slider(key="density_slider").value == C.DENSITY_MAX and at.slider(key="spread_slider").value == C.DEFAULT_SPREAD and at.slider(key="p_slider").value == C.P_MIN
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["density"] = "63"
    at.query_params["spread"] = "60"
    at.query_params["load"] = "94"
    at.run()
    assert at.slider(key="density_slider").value == 60 and at.slider(key="spread_slider").value == 50 and at.slider(key="load_slider").value == 90


def test_unknown_values_in_the_permalink_fall_back_to_the_defaults():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["net"] = "ring"
    at.query_params["selection"] = "steilster"
    at.query_params["rule"] = "astar"
    at.run()
    assert not at.exception and at.selectbox(key="net_select").value == C.DEFAULT_NET
    assert at.radio(key="selection_radio").value == C.DEFAULT_SELECTION and at.radio(key="rule_radio").value == C.DEFAULT_RULE


def test_randomize_moves_the_seed_but_not_the_distribution():
    at = _run()
    pick = lambda a: ([m.value for m in a.metric if m.label == "Kreise"][1], [m.value for m in a.metric if m.label == "Durchsuchte Kanten"][1], _metric(a, "Startlücke"))
    before = pick(at)
    seed_before = at.number_input(key="seed_input").value
    [b for b in at.sidebar.button if "Neues Netz" in b.label][0].click()
    at.run()
    assert not at.exception and at.number_input(key="seed_input").value != seed_before and pick(at) == before


def test_experiments_run_on_demand():
    at = _run()
    assert not any("Mittel über 10 feste Netze je Größe" in c for c in _captions(at))
    assert not any("Die Kreiszahl und die durchsuchten Kanten bleiben gleich" in c for c in _captions(at))
    for key in ("scaling_start", "capacity_start"):
        at.button(key=key).click()
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    text = " ".join(_captions(at))
    assert "Mittel über 10 feste Netze je Größe" in text and "Die Kreiszahl und die durchsuchten Kanten bleiben gleich" in text


def test_experiments_on_a_fixed_net_show_hints_instead_of_dead_controls():
    at = _run(lambda a: a.session_state.__setitem__("net_select", "detour"))
    assert not [b for b in at.button if b.key in ("scaling_start", "capacity_start")]
    assert sum("zufälliges Distributionsnetz wählen" in t for t in _texts(at)) >= 6


def _calls(src, name):
    """Der Text jedes Aufrufs `name(...)` einschließlich verschachtelter Klammern."""
    out = []
    for m in re.finditer(re.escape(name) + r"\(", src):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        out.append(src[m.start():i])
    return out


def test_every_plotly_chart_has_an_explicit_key_and_axes_are_locked():
    calls = _calls(APP.read_text(encoding="utf-8"), "plotly_chart")
    assert len(calls) == 9 and all(re.search(r'key=f?"[a-z_]+(_\{\w+\})?"', c) for c in calls), calls
    assert len({re.search(r'key=f?"([a-z_]+?)(?:_\{\w+\})?"', c).group(1) for c in calls}) == 9            # jeder Schlüssel nur einmal
    viz = (ROOT / "cyc_visualization.py").read_text(encoding="utf-8")
    bodies = [b for b in viz.split(chr(10) + "def ") if b.startswith("build_")]
    assert "fixedrange=True" in viz and len(bodies) == 7 and all("_base(" in b or "_layout(" in b for b in bodies)


def test_app_text_has_no_links_to_repository_files():
    assert not re.search(r"\]\(\w+\.py\)", APP.read_text(encoding="utf-8"))


def test_footer_is_verbatim():
    src = APP.read_text(encoding="utf-8")
    assert "https://sebastianhanisch.net/kontakt.html" in src and "Interesse an einer maßgeschneiderten Lösung für" in src and "Operations Research und Machine Learning" in src


def test_runtime_needs_only_numpy_pandas_plotly_streamlit():
    """Konvention der Konzepte-Wurzeln und -Stücke: Referenzbibliotheken (scipy, networkx) nur als Testorakel."""
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "scipy" not in req and "networkx" not in req
    for path in ROOT.glob("*.py"):
        assert not re.search(r"^\s*(import|from)\s+(scipy|networkx)\b", path.read_text(encoding="utf-8"), re.M), path.name
