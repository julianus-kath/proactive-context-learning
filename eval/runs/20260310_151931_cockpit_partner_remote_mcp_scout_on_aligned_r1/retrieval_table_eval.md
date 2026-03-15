# Cockpit MCP Table-Retrieval Evaluation

- Generated: `2026-03-10T15:19:33.360164Z`
- Run ID: `20260310_151931_cockpit_partner_remote_mcp_scout_on_aligned_r1`
- Mode label: `scout_on`
- MCP URL: `http://192.168.1.35:8000`

## Aggregate

- Total queries: `9`
- Mean Recall@5: `0.1111`
- Required-tables-ok@5: `1/9`
- Mean Recall@10: `0.1481`
- Required-tables-ok@10: `1/9`
- MRR: `0.0437`

| Query | Recall@5 | Required ok@5 | Required tables | Top-10 retrieved | Missing required (top-10) |
|---|---:|---:|---|---|---|
| CP1 | 0.000 | False | khkartikel, khkartikellieferanten, khkartikelvarianten | khklagerplatzbuchungen, khkppsffmatbeigestellt, khkppsffmaterial, khkppsffretourenmat, khkprojektematerialplanung, tkhkppsffbeistellmaterial, vwkhk_ac_auftragscockpit, vwkhk_ac_auftragscockpit_famain, vwkhk_ac_auftragscockpit_vkauftraege, vwkhk_ac_auftragscockpit_vkbelegegesamt | khkartikel, khkartikellieferanten, khkartikelvarianten |
| CP2 | 0.000 | False | khkvkbelege, khkbelegepositionen | khkbuchungserfassung, khkbuchungserfassunga, khkbuchungsjournal, khkbuchungsmatrix, khkbuchungstransferpositionen, khkdispostapelpositionen, khkekbelege, khkekbelegepositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege | khkbelegepositionen, khkvkbelege |
| CP3 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | bcspjmprojektevorgaengezeiten, bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, bscrmpositionenzeitstempel, bscrmzeitzone, bsmykampagne, khkafamethoden, khkafamethodensub, khkartikelkunden | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP4 | 0.000 | False | osemzizzebuchungen | bcspjmprojektevorgaengeleist, bcspjmprojektevorgaengezeiten, bsmyvertriebsphasekontaktvorlage, khkartikelkunden, khkintrastatgrundlagen, khkkonsolidierung, khkkonsolidierungmandanten, khkkonsolidierungmandantenums, khkppsrueckmeldungen, khkppsschichtmodelleintervalle | osemzizzebuchungen |
| CP5 | 0.000 | False | osemzizzebuchungen, khkppsstempel | bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkartikelvariantenlagerplatz, khkartikelvariantenverpackungen, khkbuchungstransferpositionen, khklagerplaetze, khklagerplaetzepermanenteiv, khklagerplatzbestaende, khklagerplatzbestaendechargen | khkppsstempel, osemzizzebuchungen |
| CP6 | 0.000 | False | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkartikelvariantenlagerplatz, khkartikelvariantenverpackungen, khkbuchungstransferpositionen, khkekbelegepositionenlager, khkekbelegezuschlaege, khklagerorte, khklagerplaetze | khkekbelege, khkekbelegepositionen |
| CP7 | 1.000 | True | khkbuchungserfassung | bsdmsarchivrewedruckbelege, bsmykampagnemitarbeiter, bsmyteammitglieder, khkbuchungserfassung, khkbuchungserfassunga, khkbuchungserfassungbg, khkbuchungserfassungop, khkbuchungserfassungopa, khkbuchungserfassungsdiv, khkbuchungserfassungsdiva |  |
| CP8 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmprojekte, bcspjmprojektepositionen, bcspjmprojektepositionenflow, bcspjmprojektetemplates, bcspjmprojektevorgaengeleist, bcspjmprojektevorgaengezeiten, bcspjmprojektevorgaengezeitenarchiv, bcspjmprojektevorgaengezeitenreise | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP9 | 0.000 | False | osemzizzebuchungen, khkppsstempel, khkppsbelege, khkpppsbelegeagpositionen | bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bswinbdema, bswinbdemastatus, khkppsbdeap, khkppsbdeimportserver, khkppsbdekommtgeht, khkppsbdemafm | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel, osemzizzebuchungen |
