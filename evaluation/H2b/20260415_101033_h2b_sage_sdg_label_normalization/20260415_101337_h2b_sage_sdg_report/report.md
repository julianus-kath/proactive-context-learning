# H2b /process_query Grounding Report

## Experiment Definition

- Generated: `2026-04-15T10:13:37.185750Z`
- Endpoint(s): `http://localhost:5001`
- Dataset(s): `C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\eval\datasets\cockpit_partner_queries_v1.jsonl`
- Modes: `scout_structural, scout_enriched_ranked`
- Scoring logic: `required-table grounding with surfaced precedence final_sql > ranked > discovery`

## Label Normalization Summary

- Source: `C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\eval\runs\20260415_101033_h2b_sage_sdg_label_normalization\label_normalization.json`
- Exact: `8`
- Alias/prefix-normalized: `5`
- Manual-confirmed: `0`
- Unresolved: `0`

## Aggregate Metrics by Mode

| Mode | #Queries | Mean required recall | All-required surfaced | SQL present | SQL exec success | Median latency (ms) | Policy violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| scout_structural | 9 | 0.0 | 0 | 6 | 6 | 7330.0 | 0 |
| scout_enriched_ranked | 9 | 0.0 | 0 | 7 | 6 | 6876.0 | 0 |

## Per-Query Tables

### scout_structural

| Query ID | Required tables | Surfaced tables | Required recall | All-required-ok | SQL present | Execution success | Latency (ms) | Notes/mismatches |
|---|---|---|---:|---|---|---|---:|---|
| CP1 | khkartikel, khkartikellieferant, khkartikelvarianten | khkppsffmaterial, khkppsffmatbeigestellt, khkppsffretourenmat, khkppsgemeinkostensaetze, khkppsrueckmeldungenfibu, b | 0.0 | False | True | True | 7485 | missing_required=khkartikel,khkartikellieferant,khkartikelvarianten |
| CP2 | khkvkbelege, khkvkbelegepositionen | khkdispostapelpositionen, khkekbelege, khkekbelegepositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege, b | 0.0 | False | True | True | 7330 | missing_required=khkvkbelege,khkvkbelegepositionen |
| CP3 | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel | khkprojektezeiterfassung, bcspjmprojektevorgaengezeitenreise, khkmitarbeiter, khkppsressourcenkopf, khkprojekte, b | 0.0 | False | True | True | 4953 | missing_required=khkppsfabelege,khkppsfabelegeagpositionen,khkppsbdestempel |
| CP4 | osemzizzebuchungen | khkppsbdeap, khkppsrueckmeldungen, vwkhkppssammellohnschein, khkppsbdestempelbackup, bcspjmprojektevorgaengeleist | 0.0 | False | True | True | 18207 | missing_required=osemzizzebuchungen |
| CP5 | osemzizzebuchungen, khkppsbdestempel |  | 0.0 | False | False | None | 31210 | missing_required=osemzizzebuchungen,khkppsbdestempel |
| CP6 | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | khkppsffmaterial, khkifauftraege, khklieferschwellen, khkppsffmatbeigestellt, khkppsffretourenmat, b | 0.0 | False | True | True | 5060 | missing_required=khkekbelege,khkekbelegepositionen,khkekbelegepositionenlager |
| CP7 | khkbuchungserfassung | khkppswerkzeuge, khkdruckprozessedruckbelege2, khkppsressourcenagpositionen, khkdruckbelegekennzeichen, khkppsfabelegeagpositionen | 0.0 | False | True | True | 7419 | missing_required=khkbuchungserfassung |
| CP8 | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel | bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmobjekte, bcspjmobjekterapport, bcspjmobjektestapel, bcspjmartikelobjectconsumption, bcspjmobjektestacks, bcspjmadressenkontakt, bcspjmobjektezubehoer, bcspjmprojekte, b | 0.0 | False | False | None | 5870 | missing_required=khkppsfabelege,khkppsfabelegeagpositionen,khkppsbdestempel |
| CP9 | osemzizzebuchungen, khkppsbdestempel, khkppsfabelege, khkppsfabelegeagpositionen | bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bscrmkalenderpositionen, b | 0.0 | False | False | None | 5906 | missing_required=osemzizzebuchungen,khkppsbdestempel,khkppsfabelege,khkppsfabelegeagpositionen |

### scout_enriched_ranked

| Query ID | Required tables | Surfaced tables | Required recall | All-required-ok | SQL present | Execution success | Latency (ms) | Notes/mismatches |
|---|---|---|---:|---|---|---|---:|---|
| CP1 | khkartikel, khkartikellieferant, khkartikelvarianten | khkppsffmaterial, khkppsffmatbeigestellt, khkppsffretourenmat, khkppsgemeinkostensaetze, khkppsrueckmeldungenfibu, b | 0.0 | False | True | True | 6811 | missing_required=khkartikel,khkartikellieferant,khkartikelvarianten |
| CP2 | khkvkbelege, khkvkbelegepositionen | khkdispostapelpositionen, khkekbelege, khkekbelegepositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege, b | 0.0 | False | True | False | 7647 | missing_required=khkvkbelege,khkvkbelegepositionen |
| CP3 | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel | bsbdegesrm, bscrmpositionenzeitstempel, khkppsressourcenkopf, vwkhk_ac_bestandsverlauf, bscrmpositionenvorgaenger, khkppsffrueckmeldungen, b, bcspjmartikelobjektverbrauch, bcspjmobjektestapelpositionen, bcspjmvertraegebedingungen, bcspjmvertraegebedingungenpos, bcspjmartikelobjectconsumption | 0.0 | False | True | True | 13208 | missing_required=khkppsfabelege,khkppsfabelegeagpositionen,khkppsbdestempel |
| CP4 | osemzizzebuchungen | khkppsbdeap, khkppsrueckmeldungen, vwkhkppssammellohnschein, khkppsbdestempelbackup, bcspjmprojektevorgaengeleist | 0.0 | False | True | True | 7052 | missing_required=osemzizzebuchungen |
| CP5 | osemzizzebuchungen, khkppsbdestempel | bsbdegesrm, bcspjmprojektevorgaengezeitenreise, bsbdestempelgesrm, bsmykampagnemitarbeiter, bswinbdema, b, bsmycampaignemployees, khkdruckbelegekennzeichen | 0.0 | False | True | True | 18260 | missing_required=osemzizzebuchungen,khkppsbdestempel |
| CP6 | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | khkppsffmaterial, khkifauftraege, khklieferschwellen, khkppsffmatbeigestellt, khkppsffretourenmat, b | 0.0 | False | True | True | 3786 | missing_required=khkekbelege,khkekbelegepositionen,khkekbelegepositionenlager |
| CP7 | khkbuchungserfassung | khkppswerkzeuge, khkdruckprozessedruckbelege2, khkppsressourcenagpositionen, khkdruckbelegekennzeichen, khkppsfabelegeagpositionen | 0.0 | False | True | True | 6876 | missing_required=khkbuchungserfassung |
| CP8 | khkppsfabelege, khkppsfabelegeagpositionen, khkppsbdestempel | bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmobjekte, bcspjmobjekterapport, bcspjmobjektestapel, bcspjmartikelobjectconsumption, bcspjmobjektestacks, bcspjmadressenkontakt, bcspjmobjektezubehoer, bcspjmprojekte, b | 0.0 | False | False | None | 5670 | missing_required=khkppsfabelege,khkppsfabelegeagpositionen,khkppsbdestempel |
| CP9 | osemzizzebuchungen, khkppsbdestempel, khkppsfabelege, khkppsfabelegeagpositionen | bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bscrmkalenderpositionen, b | 0.0 | False | False | None | 5074 | missing_required=osemzizzebuchungen,khkppsbdestempel,khkppsfabelege,khkppsfabelegeagpositionen |

## Interpretation

Primary signal: required-table grounding under full `/process_query` pipeline. Best mean required-table recall in this run set: `scout_structural`.

## Methodological Comparability (H2a vs H2b)

H2a and H2b both use the same `/process_query` full agent pipeline.
H2a is scored on semantic correctness; H2b is scored on production table grounding and operational robustness.
