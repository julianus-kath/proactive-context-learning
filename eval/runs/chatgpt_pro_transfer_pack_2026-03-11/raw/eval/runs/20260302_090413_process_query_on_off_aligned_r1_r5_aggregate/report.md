# Process Query ON/OFF Aggregate (R1-R5)

- Generated at (UTC): `2026-03-02T08:04:13.008738+00:00`
- OFF control: `SchemaCatalog + aligned TableRanker`
- ON backend: `ScoutRunner`
- Excluded invalid runs (MCP downtime):
  - `20260302_074648_complex_hard_v1_process_query_scout_off_aligned_r4`
  - `20260302_074810_complex_hard_v1_process_query_scout_on_r5`
  - `20260302_074916_complex_hard_v1_process_query_scout_off_aligned_r5`

## crosslingual_hard_v1

- Pairs: `5`
- Dataset: `eval/datasets/northwind_queries_crosslingual_hard_v1.jsonl`

| Metric | ON mean | OFF mean | Delta (ON-OFF) |
|---|---:|---:|---:|
| Success rate (%) | 100.00 | 100.00 | 0.00 |
| Avg latency (ms) | 5395.94 | 4925.10 | 470.84 |
| P95 latency (ms) | 9733.80 | 7699.80 | 2034.00 |
| Expert strict equal (count) | 1.60 | 1.20 | 0.40 |
| Expert required tables ok (count) | 6.40 | 5.60 | 0.80 |
| Expert strict equal rate | 0.133 | 0.100 | 0.033 |
| Expert required tables ok rate | 0.533 | 0.467 | 0.067 |

Top ON-advantage queries (required tables / strict):
- `CL2` d_req=2, d_strict=0 :: Welche Kundenländer bringen den größten Gesamtumsatz nach Abzügen? 
- `CL6` d_req=2, d_strict=0 :: Wie entwickeln sich pro Monat erfasste Aufträge und verspätete Auslieferungen? 
- `CL10` d_req=1, d_strict=2 :: Welche Kundensegmente erzeugen den höchsten Erlös nach Rabatt? 

Top OFF-advantage queries (required tables / strict):
- `CL8` d_req=-1, d_strict=0 :: Welche Kunden bestellen häufig, aber mit eher kleinem Warenkorbwert? 
- `CL1` d_req=0, d_strict=0 :: Welche Lieferanten erzielen den höchsten Umsatz nach Rabatten über ihre Artikel? 
- `CL11` d_req=0, d_strict=0 :: Welche Mitarbeitenden verkaufen häufig in andere Zielländer als ihr Heimatland? 

## complex_hard_v1

- Pairs: `5`
- Dataset: `eval/datasets/northwind_queries_complex_hard_v1.jsonl`

| Metric | ON mean | OFF mean | Delta (ON-OFF) |
|---|---:|---:|---:|
| Success rate (%) | 100.00 | 98.67 | 1.33 |
| Avg latency (ms) | 7645.20 | 9360.74 | -1715.54 |
| P95 latency (ms) | 17038.20 | 27642.60 | -10604.40 |
| Expert strict equal (count) | 2.00 | 2.00 | 0.00 |
| Expert required tables ok (count) | 5.60 | 6.00 | -0.40 |
| Expert strict equal rate | 0.133 | 0.133 | 0.000 |
| Expert required tables ok rate | 0.373 | 0.400 | -0.027 |

Top ON-advantage queries (required tables / strict):
- `HX10` d_req=0, d_strict=0 :: Welche Kundensegmente haben hohen Umsatz, aber geringe Wiederkaufrate (Bestellungen pro Kunde)? 
- `HX12` d_req=0, d_strict=0 :: Welche Kategorien haben nach Rabatt die hoechste Umsatzvolatilitaet zwischen Monaten? 
- `HX14` d_req=0, d_strict=0 :: Welche Kunden bestellen haeufig verschiedene Produktfamilien, aber mit unterdurchschnittlichem Warenkorbwert? 

Top OFF-advantage queries (required tables / strict):
- `HX1` d_req=-1, d_strict=0 :: Welche Kundenkonten haben ihren Monatsumsatz vom ersten zum letzten aktiven Monat am staerksten gesteigert (mindestens 5 Bestellungen insgesamt)? 
- `HX6` d_req=-1, d_strict=0 :: Welche Mitarbeitenden haben viele grenzueberschreitende Auftraege, aber unterdurchschnittlichen Umsatz je Auftrag? 
- `HX10` d_req=0, d_strict=0 :: Welche Kundensegmente haben hohen Umsatz, aber geringe Wiederkaufrate (Bestellungen pro Kunde)? 
