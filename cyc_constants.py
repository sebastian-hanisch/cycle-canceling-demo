"""Konstanten, Regler-Grenzen, Presets und feste Seed-Mengen der Demo "Cycle-Canceling: negative Kreise löschen"."""

# --- Regler (wie in den Vorgänger-Demos) ----------------------------------------------------------------------------------------
P_MIN, P_MAX, DEFAULT_P = 2, 6, 3            # Werke
D_MIN, D_MAX, DEFAULT_D = 2, 6, 3            # Verteilzentren
S_MIN, S_MAX, DEFAULT_S = 3, 12, 8           # Filialen
DENSITY_MIN, DENSITY_MAX, DEFAULT_DENSITY = 20, 100, 60   # Anteil vorhandener Lanes in ganzen Prozent, Schritt 10
SPREAD_MIN, SPREAD_MAX, DEFAULT_SPREAD = 0, 100, 50       # Streuung der Lane-Breiten in ganzen Prozent, Schritt 25
LOAD_MIN, LOAD_MAX, DEFAULT_LOAD = 40, 160, 90            # Gesamtnachfrage in Prozent der Werkskapazität, Schritt 10
DEFAULT_SEED = 155
SEED_MAX = 2_000_000_000

NETS = {
    "random": "Zufälliges Distributionsnetz",
    "detour": "Umweg (der kurze Weg ist teuer)",
    "assignment": "Zuordnung mit Kosten (5 × 5, Ungarische Methode)",
}
DEFAULT_NET = "random"
FIXED_NETS = ("detour", "assignment")

SELECTION_LABELS = {"klein": "Klein: beliebiger Kreis (Bellman-Ford)", "klein_random": "Klein: zufällige Kantenreihenfolge", "min_mean": "Minimum-Mean-Kreis (Karp)", "from_s": "Nur von S aus suchen (falsch)"}
DEFAULT_SELECTION = "klein"
RULE_LABELS = {"bfs": "Breitensuche (Edmonds-Karp)", "dfs": "Tiefensuche (Ford-Fulkerson)", "widest": "Breitester Weg"}
DEFAULT_RULE = "bfs"

# --- feste Seed-Mengen (dieselben wie in der Edmonds-Karp-Demo; unabhängig vom Nutzer-Seed) -----------------------------------------
DIST_SEEDS = tuple(range(100000, 100100))
SWEEP_SEEDS = DIST_SEEDS[:40]
SCALE_SIZES = ((2, 2, 4), (3, 3, 8), (4, 4, 16), (6, 6, 32), (8, 8, 64), (12, 12, 128))   # (Werke, DCs, Filialen)
SCALE_SEEDS = DIST_SEEDS[:10]
CAPACITY_FACTORS = (1, 10, 100, 1000)

COLORS = {
    "flow": "#1f77b4", "path": "#2ca02c", "back": "#ff7f0e", "cut": "#d62728", "reach": "#2ca02c", "dead": "#9467bd",
    "unreach": "#8c8c8c", "faint": "rgba(150,150,150,0.45)", "node": "#111111", "optimal": "#d62728", "levels": "Viridis",
}

# --- Presets -----------------------------------------------------------------------------------------------------------------
_BASE = dict(net="random", selection=DEFAULT_SELECTION, rule=DEFAULT_RULE, p=DEFAULT_P, d=DEFAULT_D, s=DEFAULT_S, density=DEFAULT_DENSITY, spread=DEFAULT_SPREAD, load=DEFAULT_LOAD, seed=DEFAULT_SEED)
PRESETS = {
    "🚚 Zufallsnetz": {**_BASE},
    "🎯 Minimum-Mean": {**_BASE, "selection": "min_mean", "seed": 53},
    "🌲 Tiefensuche als Start": {**_BASE, "rule": "dfs"},
    "📏 Breitester Weg als Start": {**_BASE, "rule": "widest"},
    "⚠️ Nur von S aus": {**_BASE, "selection": "from_s", "seed": 167},
    "🏭 Werke knapp": {**_BASE, "load": 140},
    "🔀 Umweg": {**_BASE, "net": "detour"},
    "💑 Zuordnung mit Kosten": {**_BASE, "net": "assignment"},
}
PRESET_HELP = {
    "🚚 Zufallsnetz": "Das Netz der SSP-Demo (Seed 155): der kostenblinde Fluss von Edmonds-Karp kostet 1339, der billigste 1197. Sieben negative Kreise, und der Fluss ist am Ziel - SSP brauchte dafür 14 Runden.",
    "🎯 Minimum-Mean": "Seed 53: der beliebige Kreis (Klein) braucht 13 Kreise, der Kreis mit dem kleinsten Mittelwert nur 5 - aber jede Suche kostet ein Vielfaches an durchsuchten Kanten (8436 gegen 3996).",
    "🌲 Tiefensuche als Start": "Dasselbe Netz, aber der Startfluss kommt aus der Tiefensuche (Ford-Fulkerson): teurer (+17 % statt +11,9 %) und doppelt so viele Kreise (14 statt 7).",
    "📏 Breitester Weg als Start": "Startfluss über den breitesten Weg: hier +16,6 % Mehrkosten und 11 Kreise. Über 40 Netze hat der breiteste Weg zwar die kleinste Startlücke, aber die meisten Kreise.",
    "⚠️ Nur von S aus": "Bellman-Ford nur von S aus: nach dem größten Fluss erreicht S im Restgraphen kaum etwas, der negative Kreis liegt woanders - die Suche meldet „fertig“, und der Fluss bleibt 30,5 % zu teuer.",
    "🏭 Werke knapp": "Nachfrage 140 % der Werkskapazität: das Netz schafft nur 89 von 118 Einheiten; die Kreise räumen den Fluss trotzdem auf (14 Kreise, 1526 → 1403).",
    "🔀 Umweg": "Vier Knoten: Edmonds-Karp nimmt den kurzen Weg S-X-T für 9, der Umweg S-X-A-T kostet nur 2. Im Restgraphen entsteht der Kreis X → A → T → X mit Kosten 1 + 1 − 9 = −7 - ein einziger Kreis genügt.",
    "💑 Zuordnung mit Kosten": "5 Fahrzeuge, 5 Aufträge, Kosten 1 bis 9: der kostenblinde Fluss kostet 25, die Zuordnung 10. Vier Kreise räumen auf - SSP (die Ungarische Methode) baut sie von Grund auf in fünf Runden.",
}
