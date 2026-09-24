"""Presets: vollständig, in den Grenzen, und jedes Beispielnetz zeigt, was sein Hilfetext behauptet."""

import pytest

import cyc_constants as C
import cyc_evaluation as ev
import cyc_presets as P
import cyc_scenario as sc

KEYS = set(P.PRESET_KEYS)


def _net(p):
    return sc.build(p["net"], p["p"], p["d"], p["s"], p["density"], p["spread"], p["load"], p["seed"])


def _analyse(p):
    return ev.analyse(_net(p), p["selection"], p["rule"])


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP) and len(C.PRESETS) == 8
    assert all(C.PRESET_HELP[name].strip() for name in C.PRESETS)
    for name, p in C.PRESETS.items():
        assert set(p) == KEYS, name


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_values_are_inside_the_bounds_and_on_the_step_grid(name):
    p = C.PRESETS[name]
    assert p["net"] in C.NETS and p["selection"] in C.SELECTION_LABELS and p["rule"] in C.RULE_LABELS
    for key, state_key in P.PRESET_KEYS.items():
        spec = P.SETTING_SPECS[state_key]
        if spec.lo is not None:
            assert spec.lo <= p[key] <= spec.hi, (name, key)
    assert (p["density"] - C.DENSITY_MIN) % 10 == 0 and p["spread"] % 25 == 0 and (p["load"] - C.LOAD_MIN) % 10 == 0


def test_setting_specs_have_room_to_move():
    """Ein Regler mit lo == hi würde Streamlit abstürzen lassen."""
    assert all(spec.lo < spec.hi for spec in P.SETTING_SPECS.values() if spec.lo is not None)


def test_presets_use_seeds_outside_the_distribution_set():
    for name, p in C.PRESETS.items():
        assert p["seed"] not in C.DIST_SEEDS, name


def test_defaults_equal_the_random_net_preset():
    p = C.PRESETS["🚚 Zufallsnetz"]
    assert (p["net"], p["selection"], p["rule"], p["p"], p["d"], p["s"], p["density"], p["spread"], p["load"], p["seed"]) == (
        C.DEFAULT_NET, C.DEFAULT_SELECTION, C.DEFAULT_RULE, C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD, C.DEFAULT_SEED)


def test_the_variant_presets_share_the_default_net():
    base = C.PRESETS["🚚 Zufallsnetz"]
    for name, changed in (("🌲 Tiefensuche als Start", "rule"), ("📏 Breitester Weg als Start", "rule"), ("🏭 Werke knapp", "load")):
        assert all(C.PRESETS[name][k] == base[k] for k in base if k != changed), name
    assert C.PRESETS["🌲 Tiefensuche als Start"]["rule"] == "dfs" and C.PRESETS["📏 Breitester Weg als Start"]["rule"] == "widest"


def test_fixed_presets_hide_the_random_controls():
    assert {n for n, p in C.PRESETS.items() if p["net"] in C.FIXED_NETS} == {"🔀 Umweg", "💑 Zuordnung mit Kosten"}


def test_default_net_is_a_typical_draw():
    """Das Beispielnetz liegt bei der Startlücke nahe am Median (±3 Prozentpunkte), liefert die ganze Nachfrage, löscht 5 bis 9 Kreise und ist dasselbe Netz wie das Standardnetz der SSP-Demo."""
    p = C.PRESETS["🚚 Zufallsnetz"]
    dist = ev.distribution(p["p"], p["d"], p["s"], p["density"], p["spread"], p["load"])
    _, code, d = ev.verdict(_analyse(p))
    assert code == "optimal" and abs(d["start_gap_pct"] - dist["gap_pct_median"]) <= 3 and d["value"] == d["demand"] and 5 <= d["cycles"] <= 9 and p["seed"] == 155


def test_each_preset_shows_what_its_help_text_says():
    a = {name: _analyse(p) for name, p in C.PRESETS.items()}
    v = {name: ev.verdict(x) for name, x in a.items()}
    d = v["🚚 Zufallsnetz"][2]
    assert (d["start_total"], d["total"], d["cycles"], d["ssp_rounds"]) == (1339, 1197, 7, 14) and v["🚚 Zufallsnetz"][1] == "optimal"
    mm = v["🎯 Minimum-Mean"][2]
    assert (mm["cycles"], mm["scanned"]) == (5, 8436) and (ev.verdict(ev.analyse(_net(C.PRESETS["🎯 Minimum-Mean"]), "klein"))[2]["cycles"], ev.verdict(ev.analyse(_net(C.PRESETS["🎯 Minimum-Mean"]), "klein"))[2]["scanned"]) == (13, 3996)
    t = v["🌲 Tiefensuche als Start"][2]
    assert (t["start_gap_pct"], t["cycles"]) == (17.0, 14) and d["start_gap_pct"] == 11.9
    w = v["📏 Breitester Weg als Start"][2]
    assert (w["start_gap_pct"], w["cycles"]) == (16.6, 11)
    f = v["⚠️ Nur von S aus"]
    assert f[1] == "wrong" and f[2]["end_gap_pct"] == 30.5 and f[2]["cycles"] == 0
    k = v["🏭 Werke knapp"][2]
    assert (k["value"], k["demand"], k["cycles"], k["start_total"], k["total"]) == (89, 118, 14, 1526, 1403)
    u = v["🔀 Umweg"][2]
    assert (u["start_total"], u["total"], u["cycles"]) == (9, 2, 1) and u["savings"] == [7]
    z = v["💑 Zuordnung mit Kosten"][2]
    assert (z["start_total"], z["total"], z["cycles"], z["ssp_rounds"]) == (25, 10, 4, 5)


def test_the_presets_show_both_good_and_bad_news():
    """Gute Nachricht: der teure Startfluss wird kostenminimal; schlechte: ohne Suche nach allen Kreisen bleibt er zu teuer, Minimum-Mean braucht ein Vielfaches an durchsuchten Kanten, SSP ist billiger."""
    a = {name: ev.verdict(_analyse(p)) for name, p in C.PRESETS.items()}
    assert a["🚚 Zufallsnetz"][1] == "optimal" and a["🚚 Zufallsnetz"][2]["start_total"] > a["🚚 Zufallsnetz"][2]["total"]
    assert a["⚠️ Nur von S aus"][0] == "warning"
    assert a["🎯 Minimum-Mean"][2]["scanned"] > 2 * a["🎯 Minimum-Mean"][2]["ssp_scanned"] and a["🚚 Zufallsnetz"][2]["scanned"] > a["🚚 Zufallsnetz"][2]["ssp_scanned"]
