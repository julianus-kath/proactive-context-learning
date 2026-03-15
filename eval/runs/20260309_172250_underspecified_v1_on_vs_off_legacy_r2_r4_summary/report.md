# Underspecified v1 Aggregate (r2-r4)

## Runs
- r2: ON `20260309_145932_underspecified_v1_process_query_scout_on_r2` vs OFF legacy `20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2`
- r3: ON `20260309_161345_underspecified_v1_process_query_scout_on_r3` vs OFF legacy `20260309_161530_underspecified_v1_process_query_scout_off_legacy_r3`
- r4: ON `20260309_161731_underspecified_v1_process_query_scout_on_r4` vs OFF legacy `20260309_161941_underspecified_v1_process_query_scout_off_legacy_r4`

## Aggregate Metrics (36 paired queries)

| Metric | Scout ON | Scout OFF legacy | Delta (ON-OFF) |
|---|---:|---:|---:|
| strict_equal | 5/36 (13.9%) | 5/36 (13.9%) | +0 |
| positional_set_equal | 5/36 (13.9%) | 5/36 (13.9%) | +0 |
| required_tables_ok | 2/36 (5.6%) | 10/36 (27.8%) | -8 |
| sql_present | 16/36 (44.4%) | 24/36 (66.7%) | -8 |

## By Intent

### CL10 (n=9)
- strict_equal: ON 5/9, OFF 5/9
- required_tables_ok: ON 2/9, OFF 4/9
- sql_present: ON 7/9, OFF 8/9
- example deltas:
  - US_CL10_U1: ON(strict=True, req=True, sql=True) vs OFF(strict=True, req=False, sql=True)
    Q: Welche Kundengruppen bringen den meisten Nettoerlös?
  - US_CL10_U2: ON(strict=True, req=False, sql=True) vs OFF(strict=False, req=False, sql=True)
    Q: Wer sind unsere wertvollsten Segmente nach Rabatten?
  - US_CL10_U3: ON(strict=None, req=False, sql=False) vs OFF(strict=True, req=True, sql=True)
    Q: Welche Zielgruppen liefern den größten Beitrag zum Umsatz nach Abzügen?

### CL2 (n=9)
- strict_equal: ON 0/9, OFF 0/9
- required_tables_ok: ON 0/9, OFF 3/9
- sql_present: ON 9/9, OFF 7/9
- example deltas:
  - US_CL2_U1: ON(strict=False, req=False, sql=True) vs OFF(strict=None, req=False, sql=False)
    Q: Woher kommt unser Nettoumsatz?
  - US_CL2_U2: ON(strict=False, req=False, sql=True) vs OFF(strict=False, req=True, sql=True)
    Q: Welche Märkte tragen am meisten zum Erlös bei?
  - US_CL2_U2: ON(strict=False, req=False, sql=True) vs OFF(strict=False, req=True, sql=True)
    Q: Welche Märkte tragen am meisten zum Erlös bei?

### CL3 (n=9)
- strict_equal: ON 0/9, OFF 0/9
- required_tables_ok: ON 0/9, OFF 0/9
- sql_present: ON 0/9, OFF 6/9
- example deltas:
  - US_CL3_U2: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=False, sql=True)
    Q: Über wen kommt es am häufigsten zu Verzögerungen?
  - US_CL3_U3: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=False, sql=True)
    Q: Bei welchem Versandkanal ist die Terminlage am schwächsten?
  - US_CL3_U2: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=False, sql=True)
    Q: Über wen kommt es am häufigsten zu Verzögerungen?

### CL6 (n=9)
- strict_equal: ON 0/9, OFF 0/9
- required_tables_ok: ON 0/9, OFF 3/9
- sql_present: ON 0/9, OFF 3/9
- example deltas:
  - US_CL6_U1: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=True, sql=True)
    Q: Wie läuft es monatlich mit Aufträgen und Pünktlichkeit?
  - US_CL6_U1: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=True, sql=True)
    Q: Wie läuft es monatlich mit Aufträgen und Pünktlichkeit?
  - US_CL6_U1: ON(strict=None, req=False, sql=False) vs OFF(strict=False, req=True, sql=True)
    Q: Wie läuft es monatlich mit Aufträgen und Pünktlichkeit?
