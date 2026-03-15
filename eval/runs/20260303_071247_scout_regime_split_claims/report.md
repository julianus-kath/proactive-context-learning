# Scout Regime Split (Thesis Claim Framing)

## Regime Definitions
- `schema_grounded_paraphrase`: Business paraphrases still anchored to concrete Northwind entities/joins.
- `schema_weak_abstraction`: Prompts invoke conceptual groupings not cleanly represented as explicit schema fields.
- `temporal_dialect_sensitive`: Temporal KPI composition prompts with higher SQL dialect/operator sensitivity.

## Dataset x Regime Metrics (ON vs OFF)
| Dataset | Regime | Cases | Strict ON | Strict OFF | ΔStrict | Required ON | Required OFF | ΔRequired | SQL ON | SQL OFF | ΔSQL | Positional ON | Positional OFF | ΔPositional |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| crosslingual_hard_v1_segment | schema_grounded_paraphrase | 6 | 0 | 0 | 0 | 5 | 3 | 2 | 6 | 6 | 0 | None | None | None |
| crosslingual_hard_v1_segment | schema_weak_abstraction | 6 | 3 | 2 | 1 | 2 | 2 | 0 | 3 | 2 | 1 | None | None | None |
| crosslingual_hard_v1_segment | temporal_dialect_sensitive | 6 | 0 | 0 | 0 | 5 | 2 | 3 | 5 | 2 | 3 | None | None | None |
| scout_limit_probe_v2 | schema_grounded_paraphrase | 18 | 0 | 1 | -1 | 3 | 3 | 0 | 15 | 14 | 1 | 12 | 10 | 2 |
| scout_limit_probe_v2 | schema_weak_abstraction | 18 | 6 | 8 | -2 | 6 | 8 | -2 | 11 | 12 | -1 | 6 | 8 | -2 |
| scout_limit_probe_v2 | temporal_dialect_sensitive | 18 | 0 | 0 | 0 | 2 | 6 | -4 | 2 | 6 | -4 | 0 | 0 | 0 |

## Global Regime Summary (combined evidence)
| Regime | Cases | Strict ON | Strict OFF | ΔStrict | Required ON | Required OFF | ΔRequired | SQL ON | SQL OFF | ΔSQL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| schema_grounded_paraphrase | 24 | 0 | 1 | -1 | 8 | 6 | 2 | 21 | 20 | 1 |
| schema_weak_abstraction | 24 | 9 | 10 | -1 | 8 | 10 | -2 | 14 | 14 | 0 |
| temporal_dialect_sensitive | 24 | 0 | 0 | 0 | 7 | 8 | -1 | 7 | 8 | -1 |

## Query-Set Mapping (verbatim)
### crosslingual_hard_v1_segment
- `CL2` -> `schema_grounded_paraphrase`: "Welche Kundenländer bringen den größten Gesamtumsatz nach Abzügen?"
- `CL6` -> `temporal_dialect_sensitive`: "Wie entwickeln sich pro Monat erfasste Aufträge und verspätete Auslieferungen?"
- `CL10` -> `schema_weak_abstraction`: "Welche Kundensegmente erzeugen den höchsten Erlös nach Rabatt?"

### scout_limit_probe_v2
- `P_CL10_L1` -> `schema_weak_abstraction`: "Zeige den Umsatz nach Rabatt je Kundensegment."
- `P_CL10_L2` -> `schema_weak_abstraction`: "Welche Kundensegmente erzeugen den hoechsten Erloes nach Rabatt?"
- `P_CL10_L3` -> `schema_weak_abstraction`: "Welche Abnehmergruppen sind die wichtigsten Ertragsbringer nach Nachlaessen?"
- `P_CL10_L4` -> `schema_weak_abstraction`: "Welche Profilgruppen im Kundenstamm monetarisieren am staerksten nach Preiszugestaendnissen?"
- `P_CL10_L5` -> `schema_weak_abstraction`: "Welche Portfoliotypen auf Kundenseite liefern den groessten Beitrag zum bereinigten Umsatz?"
- `P_CL10_L6` -> `schema_weak_abstraction`: "Welche Kundencluster tragen am meisten zum Nettoertrag nach Zugestaendnissen bei?"
- `P_CL2_L1` -> `schema_grounded_paraphrase`: "Zeige den Umsatz nach Rabatt pro Kundenland."
- `P_CL2_L2` -> `schema_grounded_paraphrase`: "Welche Kundenlaender liefern den groessten rabattbereinigten Umsatz?"
- `P_CL2_L3` -> `schema_grounded_paraphrase`: "Aus welchen Absatzmaerkten stammt der hoechste Nettoerloes nach Nachlaessen?"
- `P_CL2_L4` -> `schema_grounded_paraphrase`: "Welche geographischen Zielmaerkte tragen am meisten zum bereinigten Verkaufsertrag bei?"
- `P_CL2_L5` -> `schema_grounded_paraphrase`: "In welchen Vertriebsraeumen entsteht der groesste Beitrag zum Nettoverkauf nach Preiszugestaendnissen?"
- `P_CL2_L6` -> `schema_grounded_paraphrase`: "Welche Absatzraeume finanzieren den hoechsten Anteil am nachlass-bereinigten Erloes?"
- `P_CL6_L1` -> `temporal_dialect_sensitive`: "Zeige pro Monat die Anzahl der Auftraege und der verspaeteten Auslieferungen."
- `P_CL6_L2` -> `temporal_dialect_sensitive`: "Wie entwickeln sich monatlich Auftragseingaenge und Lieferverzoegerungen?"
- `P_CL6_L3` -> `temporal_dialect_sensitive`: "Wie verhalten sich Nachfrage und Lieferverzug im Monatsverlauf?"
- `P_CL6_L4` -> `temporal_dialect_sensitive`: "Wie laufen Intake und Ueberfaelligkeit der Zustellung im monatlichen Takt zusammen?"
- `P_CL6_L5` -> `temporal_dialect_sensitive`: "Welche Monatsreihe zeigt gleichzeitig Auftragsfluss und verspaetete Zustellquote?"
- `P_CL6_L6` -> `temporal_dialect_sensitive`: "In welcher zeitlichen Entwicklung koppeln sich Bestellaufkommen und Verzug in der Auslieferung?"

## Claim Framing Recommendation
- Scout ON improves retrieval/coverage for schema-grounded paraphrase questions (strongest on crosslingual hard segment, positive deltas on required tables and SQL presence).
- Scout ON is not uniformly better; performance degrades on schema-weak abstraction and on temporal/dialect-sensitive prompts, where SQL execution/coverage failures increase.
- Use a regime-conditional claim (where Scout helps vs where it does not) instead of a global superiority claim.