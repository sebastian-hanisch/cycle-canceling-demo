# Cycle-Canceling – negative Kreise löschen – Streamlit-Demo

*(noch nicht deployed)*

Fünftes Stück der **Netzwerkfluss-Linie** der "Konzepte"-Reihe für die Website "Sebastian Hanisch – Operations Research und Machine Learning", Gegenstück zu [Successive Shortest Paths](https://github.com/sebastian-hanisch/ssp-demo) und Fortsetzung von [Edmonds-Karp](https://github.com/sebastian-hanisch/edmonds-karp-demo), [Dinic](https://github.com/sebastian-hanisch/dinic-demo) und [Push-Relabel](https://github.com/sebastian-hanisch/push-relabel-demo):
anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo **ein** Verfahren – **Cycle-Canceling** (Klein 1967; Goldberg und Tarjan 1989) – an einem wachsenden Beispiel.
SSP hält Optimalität und baut die Menge auf. Cycle-Canceling geht den umgekehrten Weg: es beginnt mit einem **zulässigen, aber teuren** Fluss (hier dem von Edmonds-Karp) und löscht **negative Kreise im Restgraphen**: ein Kreis mit negativen Gesamtkosten ist eine Umleitung, die Geld spart und die Menge nicht ändert.
Gibt es keinen mehr, ist der Fluss kostenminimal. Verglichen werden **beliebige** Kreise (Klein), Kreise in **zufälliger** Reihenfolge und der Kreis mit dem **kleinsten Mittelwert** (Karp; Goldberg–Tarjan); dazu die Kosten der Suche gegen SSP. Vehikel wie in den Vorgänger-Demos: ein Distributionsnetz (Werke → Verteilzentren → Filialen) mit Kosten je Einheit, dazu zwei Lehrnetze.

**Einordnung in die Reihe (die Kanten des Graphen):** Gegenstück zu SSP (Stück 4): dasselbe Ziel, umgekehrte Invariante. Der **Netzwerksimplex** (Fall-Demo `network-flow-demo`) ist verwandt – jeder Pivot löscht einen Fundamentalkreis –, arbeitet aber mit einer Baumstruktur statt mit einer neuen Suche je Kreis.
**Cost Scaling** (gebaut: [cost-scaling-demo](https://github.com/sebastian-hanisch/cost-scaling-demo)) verallgemeinert die Bedingung „kein negativer Kreis“ zu ε-Optimalität. Bisher gebaut: die ersten elf Stücke.
```
edmonds-karp-demo (Wurzel: Restgraph, Rückkanten, Max-Flow = Min-Cut)                  [gebaut]
  ├─ dinic-demo (viele kürzeste Wege je Phase: Niveaugraph, blockierender Fluss)        [gebaut]
  ├─ push-relabel-demo (kein Weg: Überschüsse schieben, Höhen anheben)                 [gebaut]
  └─ ssp-demo (Kosten: der billigste Weg im Restgraphen, Potenziale)                    [gebaut]
       ├─ cycle-canceling-demo (negative Kreise löschen) → Netzwerksimplex               [dieses Stück]
       │    (network-flow-demo)                                                          [gebaut als Fall-Demo]
       ├─ cost-scaling-demo (Push-Relabel + ε-Skalierung, das nutzt OR-Tools)           [gebaut]
       └─ multicommodity-demo (mehrere Güter teilen Kapazität: Kanten-LP, Preise)       [gebaut]
            ├─ mcf-column-generation-demo (Pfade als Spalten, Pricing = Dijkstra)       [gebaut]
            ├─ garg-koenemann-demo (Näherung mit Preisen, ohne LP-Löser)                [gebaut]
            └─ fixkosten-netzdesign-demo (Fixkosten: Schranke und Schnitte)             [gebaut]
                 ├─ benders-demo (Entwurf im Master, Fluss im Teilproblem)              [gebaut]
                 └─ Slope Scaling (Heuristik für große Netze)                           [geplant]
```

## Ergebnis (Zahlen aus den Tests)

Jede hier genannte Zahl ist in `tests/test_claims.py` belegt: die Lehrnetze von Hand, die Beispielnetze über ihre Seeds, die Verteilungen über 100 feste Netze (Seeds 100000–100099, dieselben wie in den Vorgänger-Demos). Standard: 3 Werke, 3 Verteilzentren, 8 Filialen, Netzdichte 60 %, Streuung 50 %, Auslastung 90 %, Startfluss Breitensuche (Edmonds-Karp), Klein mit Bellman-Ford. Kosten je Einheit: Werk 1–5, Lane 1–9, Verteilzentrum 1–3, Filialnachfrage 0.
Edmonds-Karp und SSP sind aus den Vorgänger-Demos kopiert; Wache-Tests: 52 475 (Edmonds-Karp) bzw. 53 907 (SSP) durchsuchte Kanten über die 100 Netze, SSP-Kosten gleich dem Optimum von `networkx`.

| Frage | Ergebnis |
|---|---|
| Ist der Fluss am Ende kostenminimal? | ✅ Ja, in allen 100 Netzen für Klein, zufällige Reihenfolge und Minimum-Mean, jeweils gleich dem Optimum von `networkx` (`max_flow_min_cost`); auch mit Tiefensuche und breitestem Weg als Startfluss, gegen ein lineares Programm (`scipy`, HiGHS) und gegen `linear_sum_assignment` (Zuordnung: 25 → 10). Am Ende kein negativer Kreis (`networkx.negative_edge_cycle`) und gültige Potenziale. |
| Stimmen die Invarianten? | ✅ Je Iteration aus dem Trace: der Kreis ist ein geschlossener, einfacher Weg im Restgraphen des vorigen Flusses mit negativen Kosten, der Engpass ist der kleinste Rest, die Menge bleibt gleich, der neue Fluss ist zulässig, Ersparnis = Engpass × \|Kosten\| ≥ 1, die Kosten fallen strikt. |
| Ist der Minimum-Mean-Kreis wirklich der kleinste? | ✅ Karp gegen die Aufzählung aller einfachen Kreise (`networkx.simple_cycles`) auf Kleinstnetzen in jeder Iteration, und der Mittelwert ist über die Iterationen nicht fallend (Goldberg–Tarjan). Kreise ≤ Startkosten − Optimum (Klein-Schranke) gilt in allen Läufen. |
| Wie viel gibt es zu räumen? | Der Startfluss ist im Mittel **12,7 % teurer** als nötig (Median 11,1 %, höchstens 57 %; nur in 2 von 100 Netzen zufällig billigst). Beispielnetz (Seed 155, dasselbe wie in der SSP-Demo): 1339 → 1197 in 7 Kreisen. |
| Wie viele Kreise? | ✅ Wenige: **Klein 4,86** im Mittel (Median 5, höchstens 13), zufällige Reihenfolge 4,76 (höchstens 12), **Minimum-Mean 4,07** (höchstens 11). Klein löscht in 97 von 100 Netzen weniger Kreise, als SSP Runden braucht (11,57 im Mittel). |
| Bringt Minimum-Mean viel? | ⚠️ Wenig: in 42 Netzen weniger Kreise als Klein, in 56 gleich viele, in 2 mehr; der erste Kreis bringt 49 % der Ersparnis (Klein 35 %, zufällig 38 %). Dafür kostet jede Suche ein Vielfaches: 6717 gegen 1509 durchsuchte Kanten. Größter Unterschied: Seed 53, 13 Kreise gegen 5 (3996 gegen 8436 Kanten). |
| Wie teuer ist die Suche gegen SSP? | ❌ Deutlich: Klein 1509, Minimum-Mean 6717 gegen **539** bei SSP. Von 12 auf 166 Knoten wächst der Abstand: Klein 2,4- bis 6,4-fach, Minimum-Mean im größten Netz 254-fach (44,7 Mio. gegen 176 000 Kanten); Steigung im doppelt logarithmischen Diagramm 1,93 (Klein), 2,52 (Minimum-Mean), 1,69 (SSP). |
| Hängt die Kreiszahl vom Startfluss ab? | ⚠️ Lose: Breitensuche 12,7 % Startlücke und 4,86 Kreise, Tiefensuche 13,0 % und 4,73, **breitester Weg 11,5 % und 5,72**: die kleinste Lücke hat die meisten Kreise. Korrelation Lücke–Kreise über 120 Läufe (40 Netze × 3 Startflüsse): 0,50. |
| Pseudopolynomial – in der Praxis? | ✅ Die Schranke (Startkosten − Optimum, im Mittel 106) ist weit weg: gemessen 6,8 % davon (höchstens 50 %). Kapazitäten × 1, 10, 100, 1000 lassen Kreise (4,3), durchsuchte Kanten (1327) und Kreiszahl von Minimum-Mean (3,9) unverändert; die Schranke wächst mit dem Faktor. |
| Was passiert bei einer Suche nur von S aus? | ❌ Nach einem größten Fluss ist S gesättigt, im Restgraphen erreicht es kaum etwas: in **36 von 100 Netzen** bleibt der Fluss zu teuer (dort im Mittel +7,3 %, höchstens +26,3 %), in 26 Netzen findet die Suche gar keinen Kreis. Seed 167: 1372 statt 1051 (+30,5 %); auf dem Umweg 9 statt 2. Der Beweis im letzten Bild schlägt fehl. |

## Was nicht funktioniert hat / Vorab-Hypothesen

Vor dem Schreiben der Texte wurde über die 100 Netze gemessen; einige Vermutungen aus dem Plan stimmten nicht oder nur teilweise:

- **„Cycle-Canceling braucht viele Kreise (pseudopolynomiale Schranke).“** Nein: im Mittel unter fünf (4,86), weniger als die Hälfte der SSP-Runden (11,57). Die Schranke ist ein Worst-Case-Satz.
- **„Minimum-Mean bringt spürbar weniger Kreise als Klein.“** Nur wenig: 4,07 gegen 4,86. In mehr als der Hälfte der Netze gleich viele; das erwartete Vielfache gibt es nur in einzelnen Netzen (Seed 53: 13 gegen 5).
- **„Cycle-Canceling ist gegen SSP konkurrenzfähig.“** Nicht in durchsuchten Kanten: SSP sucht von S aus mit Dijkstra, bricht bei T ab und braucht 539 Kanten; Cycle-Canceling muss das ganze Netz nach einem Kreis durchsuchen (Klein 1509, Minimum-Mean 6717).
- **„Je teurer der Startfluss, desto mehr Kreise.“** Nur lose (Korrelation 0,50): der breiteste Weg hat die kleinste Startlücke und die meisten Kreise.
- **„Bei größeren Kapazitäten braucht Cycle-Canceling mehr Kreise (pseudopolynomial).“** Nicht in dieser Messung: Kapazitäten × 1000 ändern die Kreiszahl nicht, weil Startfluss und Kreise mitskalieren; nur die Schranke wächst.
- **„Die Suche nur von S aus genügt.“** Falsch, und tückisch (siehe Tabelle): S ist nach einem größten Fluss gesättigt; die negativen Kreise liegen woanders.
- **Aufwand der Suche hängt an der Umsetzung:** die Bellman-Ford-Suche prüft nach jedem Durchlauf mit Verbesserung den Vorgänger-Graphen auf einen Kreis. Ohne diese Erkennung (Kreis erst im n-ten Durchlauf) durchsuchte Klein im Standardnetz-Mittel 6094 statt 1509 Kanten – gemessen, bevor die Erkennung eingebaut wurde; nicht als Test geführt, deshalb steht die Zahl nicht in der Ergebnistabelle.
- **Abweichungen vom Plan:** Port 8677; kein PDF-Export; Startfluss wählbar (Breitensuche, Tiefensuche, breitester Weg) statt nur Breitensuche.

## Was die Demo zeigt

- **Kreise in Aktion:** Schritt-Slider und ▶️ über die Bilder: **Start** (der Startfluss), je **Kreis** ein Bild (Kreis grün, Rückkanten orange gestrichelt, beschriftet mit Menge × Kosten je Einheit), am Schluss der fertige Fluss mit dem **Beweis** (Potenziale) und der **Menge-Kosten-Ebene**: SSP läuft entlang der konvexen Kostenkurve nach rechts, Cycle-Canceling fällt bei fester Menge senkrecht vom Startfluss zum Optimum. Rechts die Ersparnis je Kreis und der Kostenabstieg.
- **Vom teuren zum billigen Fluss:** Menge, Kosten (Start → Ende), Kreise, durchsuchte Kanten gegen SSP; Verteilung über 100 feste Netze (Histogramm mit der Marke „Ihre Ziehung“).
- **Experimente (🔬):** beliebiger Kreis oder Minimum-Mean, Startfluss, Schranke gegen Realität und Kapazitäten × 1000, Cycle-Canceling gegen SSP (Skalierung von 12 bis 166 Knoten), nur von S aus suchen.
- **Feste Netze** (Umweg mit einem einzigen Kreis, Zuordnung mit Kosten) und zufällige Distributionsnetze; **Wo die Annahmen enden:** welches Stück an welcher Schwäche ansetzt.

## Modell und Verfahren

- **Netz und Restgraph:** wie in der SSP-Demo (Quelle S, Werke, Verteilzentren als Eingang und Ausgang gespalten, Filialen, Senke T; Restkanten als Paar 2i/2i+1), Kosten je Einheit c ≥ 0, die Rückkante hat Kosten −c. Ganzzahlig, eigener Zufallsgenerator SplitMix64 statt `numpy.random`.
- **Cycle-Canceling:** wiederhole: suche einen Kreis mit negativen Kosten im Restgraphen, schiebe den Engpass um den Kreis. Menge unverändert, Kosten sinken um Engpass × \|Kreiskosten\|. Ohne negativen Kreis ist der Fluss kostenminimal für seine Menge.
- **Klein:** Bellman-Ford mit gedachtem Start (Entfernung 0 zu allen Knoten), Kanten in fester oder zufälliger Reihenfolge; nach jedem Durchlauf mit Verbesserung wird der Vorgänger-Graph auf einen Kreis geprüft (jeder Kreis dort ist negativ), ein Durchlauf ohne Verbesserung heißt: keiner mehr.
- **Minimum-Mean:** Karp, D_k(v) mit numpy berechnet, exakter Bruchvergleich für alle Kandidaten; der Weg mit n Kanten zum besten Knoten wird in einfache Kreise zerlegt, der mit dem kleinsten Mittelwert gelöscht. O(nm) je Iteration.
- **Nur von S aus:** Bellman-Ford mit Start nur bei S – Negativkontrolle.
- **Zertifikat:** Potenziale aus einer Bellman-Ford-Rechnung vom gedachten Start (Kopie aus der SSP-Demo); gültig genau dann, wenn kein negativer Kreis übrig ist.
- **Aufwand:** durchsuchte Kanten (jede in einem Durchlauf angesehene Restkante, auch die des letzten, ergebnislosen Durchlaufs), nie Sekunden.

## Dateien

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `cyc_constants.py` | Regler-Grenzen, Presets und Hilfetexte, feste Seed-Mengen |
| `cyc_presets.py` | Permalink, Preset- und Zufalls-Seed-Logik (Standardmuster des Portfolios) |
| `cyc_scenario.py` | Distributionsnetz mit Kosten, eigener Zufallsgenerator, Lehrnetze (Umweg, Zuordnung mit Kosten), Kapazitäts-Skalierung |
| `cyc_algorithm.py` | Cycle-Canceling mit vier Kreiswahlen (Klein, zufällig, Minimum-Mean nach Karp, nur von S), Trace je Iteration |
| `cyc_edmonds_karp.py`, `cyc_ssp.py` | Kopien der Vorgänger-Demos (Startfluss; Optimum, Zertifikat und Vergleichsbasis), ohne Import, durch Tests bewacht |
| `cyc_evaluation.py` | Urteil, Verteilungen, Startfluss-Tabelle, Skalierung, Kapazitäts-Tabelle, Optimalitätsprüfung |
| `cyc_visualization.py` | Plotly-Abbildungen (Achsen gesperrt für Touch-Geräte; Hover über unsichtbare Marker entlang der Kanten) |
| `tests/` | Algorithmus (Handfälle, `networkx`/`scipy`/Brute Force als Gegenprobe, Invarianten je Iteration, Karp gegen alle einfachen Kreise, Goldberg–Tarjan, Klein-Schranke, Negativkontrolle), Szenario und Auswertung, Presets, belegte Zahlen, AppTest-Rauchtests |

Alle Daten sind synthetisch; die Laufzeit braucht nur numpy, pandas, plotly und streamlit (scipy und networkx sind reine Testorakel).

## Lokal starten

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\streamlit run app.py
```

## Tests ausführen

```bash
venv\Scripts\pip install -r requirements-dev.txt
venv\Scripts\python -m pytest tests -v
```

Die Logik rechnet ausschließlich mit ganzen Zahlen (Mittelwerte als exakte Brüche); die im Text genannten Anteile und Mediane sind deshalb auf jeder Plattform identisch.
Die CI (`.github/workflows/tests.yml`) läuft auf Ubuntu mit Python 3.12, bei jedem Push und wöchentlich mit den jeweils neuesten Bibliotheksversionen.
