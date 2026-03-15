# Cockpit MCP Table-Retrieval Evaluation

- Generated: `2026-03-11T06:09:38.460633Z`
- Run ID: `20260311_060936_cockpit_partner_remote_mcp_scout_off_aligned_r3`
- Mode label: `scout_off_aligned`
- MCP URL: `http://192.168.1.35:8000`

## Aggregate

- Total queries: `9`
- Mean Recall@5: `0.1111`
- Required-tables-ok@5: `1/9`
- Mean Recall@10: `0.1481`
- Required-tables-ok@10: `1/9`
- MRR: `0.0554`

| Query | Recall@5 | Required ok@5 | Required tables | Top-10 retrieved | Missing required (top-10) |
|---|---:|---:|---|---|---|
| CP1 | 0.000 | False | khkartikel, khkartikellieferanten, khkartikelvarianten | khklagerplatzbuchungen, khkppsffmatbeigestellt, khkppsffmaterial, khkppsffretourenmat, khkppsstlimportpos, khkprojektematerialplanung, tkhkppsffbeistellmaterial, khkdispoartikel, khklagerbewegungsarten, khklagerregelnarten | khkartikel, khkartikellieferanten, khkartikelvarianten |
| CP2 | 0.000 | False | khkvkbelege, khkbelegepositionen | khkbankverbindungend, khkbankverbindungenl, khkbuchungserfassung, khkbuchungserfassunga, khkbuchungsjournal, khkbuchungsmatrix, khkbuchungstransferpositionen, khkdispostapelpositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege | khkbelegepositionen, khkvkbelege |
| CP3 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | bcspjmprojektevorgaengezeiten, bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, bscrmpositionenzeitstempel, bscrmzeitzone, bsmykampagne, khkafamethoden, khkafamethodensub, khkanlagentermine | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP4 | 0.000 | False | osemzizzebuchungen | bcspjmprojektevorgaengeleist, bcspjmprojektevorgaengezeiten, bsmyvertriebsphasekontaktvorlage, khkartikelkunden, khkbankverbindungench, khkhausbankend, khkintrastatgrundlagen, khkkonsolidierung, khkkonsolidierungmandanten, khkkonsolidierungmandantenums | osemzizzebuchungen |
| CP5 | 0.000 | False | osemzizzebuchungen, khkppsstempel | bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkartikelvariantenlagerplatz, khkartikelvariantenverpackungen, khkbankverbindungena, khkbuchungstransferpositionen, khklagerplaetze, khklagerplaetzepermanenteiv, khklagerplatzbestaende | khkppsstempel, osemzizzebuchungen |
| CP6 | 0.000 | False | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | bscrmkalenderpositionen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkartikelvariantenlagerplatz, khkartikelvariantenverpackungen, khkbankverbindungena, khkbuchungstransferpositionen, khkekbelegepositionenlager, khkekbelegezuschlaege, khklagerorte | khkekbelege, khkekbelegepositionen |
| CP7 | 1.000 | True | khkbuchungserfassung | bsmykampagnemitarbeiter, bsmyteammitglieder, khkbuchungserfassung, khkbuchungserfassunga, khkbuchungserfassungbg, khkbuchungserfassungop, khkbuchungserfassungopa, khkbuchungserfassungsdiv, khkbuchungserfassungsdiva, khkbuchungserfassungsdivbg |  |
| CP8 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmprojekte, bcspjmprojektepositionen, bcspjmprojektepositionenflow, bcspjmprojektetemplates, bcspjmprojektevorgaengeleist, bcspjmprojektevorgaengezeiten, bcspjmprojektevorgaengezeitenarchiv, bcspjmprojektevorgaengezeitenreise | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP9 | 0.000 | False | osemzizzebuchungen, khkppsstempel, khkppsbelege, khkpppsbelegeagpositionen | bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bswinbdema, bswinbdemastatus, khkppsbdeap, khkppsbdeimportserver, khkppsbdekommtgeht, khkppsbdemafm | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel, osemzizzebuchungen |
