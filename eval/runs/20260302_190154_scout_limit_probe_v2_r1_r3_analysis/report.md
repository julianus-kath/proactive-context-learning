# Scout Limit Probe v2 (r1-r3)

## Setup
- r1: ON `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_184710_scout_limit_probe_v2_process_query_scout_on_r1` vs OFF `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_184403_scout_limit_probe_v2_process_query_scout_off_aligned_r1_recover`
- r2: ON `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_185226_scout_limit_probe_v2_process_query_scout_on_r2` vs OFF `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_184950_scout_limit_probe_v2_process_query_scout_off_aligned_r2`
- r3: ON `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_185811_scout_limit_probe_v2_process_query_scout_on_r3` vs OFF `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260302_185506_scout_limit_probe_v2_process_query_scout_off_aligned_r3`

## Overall (54 paired query-cases)
| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| strict_equal true | 6 | 9 | -3 |
| positional_set_equal true | 18 | 18 | 0 |
| required_tables_ok true | 11 | 17 | -6 |
| sql_present true | 28 | 32 | -4 |

## By Level
| Level | Cases | Strict ON | Strict OFF | ΔStrict | Pos ON | Pos OFF | ΔPos | Req ON | Req OFF | ΔReq | SQL ON | SQL OFF | ΔSQL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| L1 | 9 | 0 | 2 | -2 | 3 | 4 | -1 | 2 | 5 | -3 | 5 | 7 | -2 |
| L2 | 9 | 1 | 1 | 0 | 4 | 4 | 0 | 2 | 3 | -1 | 5 | 6 | -1 |
| L3 | 9 | 2 | 3 | -1 | 4 | 5 | -1 | 2 | 3 | -1 | 4 | 5 | -1 |
| L4 | 9 | 0 | 0 | 0 | 3 | 2 | 1 | 0 | 0 | 0 | 5 | 4 | 1 |
| L5 | 9 | 3 | 3 | 0 | 3 | 3 | 0 | 4 | 3 | 1 | 5 | 5 | 0 |
| L6 | 9 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 3 | -2 | 4 | 5 | -1 |

## By Intent Cluster
| Cluster | Cases | Strict ON | Strict OFF | ΔStrict | Pos ON | Pos OFF | ΔPos | Req ON | Req OFF | ΔReq | SQL ON | SQL OFF | ΔSQL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CL10 | 18 | 6 | 8 | -2 | 6 | 8 | -2 | 6 | 8 | -2 | 11 | 12 | -1 |
| CL2 | 18 | 0 | 1 | -1 | 12 | 10 | 2 | 3 | 3 | 0 | 15 | 14 | 1 |
| CL6 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 6 | -4 | 2 | 6 | -4 |

## Expressive Examples
### ON Semantic Wins (strict)
- `P_CL10_L2` (CL10/L2, r3): "Welche Kundensegmente erzeugen den hoechsten Erloes nach Rabatt?"
  ON strict=True, OFF strict=False, ON sql=True, OFF sql=True

### OFF Semantic Wins (strict)
- `P_CL10_L1` (CL10/L1, r1): "Zeige den Umsatz nach Rabatt je Kundensegment."
  ON strict=None, OFF strict=True, ON sql=False, OFF sql=True
- `P_CL2_L1` (CL2/L1, r1): "Zeige den Umsatz nach Rabatt pro Kundenland."
  ON strict=False, OFF strict=True, ON sql=True, OFF sql=True
- `P_CL10_L2` (CL10/L2, r2): "Welche Kundensegmente erzeugen den hoechsten Erloes nach Rabatt?"
  ON strict=None, OFF strict=True, ON sql=False, OFF sql=True
- `P_CL10_L3` (CL10/L3, r3): "Welche Abnehmergruppen sind die wichtigsten Ertragsbringer nach Nachlaessen?"
  ON strict=None, OFF strict=True, ON sql=False, OFF sql=True

### ON SQL-Presence Wins
- `P_CL10_L4` (CL10/L4, r1): "Welche Profilgruppen im Kundenstamm monetarisieren am staerksten nach Preiszugestaendnissen?"
  ON strict=None, OFF strict=None, ON sql=True, OFF sql=False
- `P_CL2_L3` (CL2/L3, r1): "Aus welchen Absatzmaerkten stammt der hoechste Nettoerloes nach Nachlaessen?"
  ON strict=False, OFF strict=None, ON sql=True, OFF sql=False
- `P_CL10_L6` (CL10/L6, r2): "Welche Kundencluster tragen am meisten zum Nettoertrag nach Zugestaendnissen bei?"
  ON strict=False, OFF strict=None, ON sql=True, OFF sql=False
- `P_CL2_L5` (CL2/L5, r2): "In welchen Vertriebsraeumen entsteht der groesste Beitrag zum Nettoverkauf nach Preiszugestaendnissen?"
  ON strict=False, OFF strict=None, ON sql=True, OFF sql=False
- `P_CL2_L6` (CL2/L6, r2): "Welche Absatzraeume finanzieren den hoechsten Anteil am nachlass-bereinigten Erloes?"
  ON strict=False, OFF strict=None, ON sql=True, OFF sql=False

### OFF SQL-Presence Wins
- `P_CL10_L1` (CL10/L1, r1): "Zeige den Umsatz nach Rabatt je Kundensegment."
  ON strict=None, OFF strict=True, ON sql=False, OFF sql=True
- `P_CL2_L5` (CL2/L5, r1): "In welchen Vertriebsraeumen entsteht der groesste Beitrag zum Nettoverkauf nach Preiszugestaendnissen?"
  ON strict=None, OFF strict=False, ON sql=False, OFF sql=True
- `P_CL2_L6` (CL2/L6, r1): "Welche Absatzraeume finanzieren den hoechsten Anteil am nachlass-bereinigten Erloes?"
  ON strict=None, OFF strict=False, ON sql=False, OFF sql=True
- `P_CL6_L6` (CL6/L6, r1): "In welcher zeitlichen Entwicklung koppeln sich Bestellaufkommen und Verzug in der Auslieferung?"
  ON strict=None, OFF strict=False, ON sql=False, OFF sql=True
- `P_CL10_L2` (CL10/L2, r2): "Welche Kundensegmente erzeugen den hoechsten Erloes nach Rabatt?"
  ON strict=None, OFF strict=True, ON sql=False, OFF sql=True
- `P_CL6_L1` (CL6/L1, r2): "Zeige pro Monat die Anzahl der Auftraege und der verspaeteten Auslieferungen."
  ON strict=None, OFF strict=False, ON sql=False, OFF sql=True
