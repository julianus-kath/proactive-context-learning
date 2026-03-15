# Cockpit MCP Table-Retrieval Evaluation

- Generated: `2026-03-10T11:15:01.334422Z`
- Run ID: `20260310_111456_cockpit_partner_remote_mcp_scout_on_r1`
- Mode label: `scout_on_remote`
- MCP URL: `http://192.168.1.35:8000`

## Aggregate

- Total queries: `9`
- Mean Recall@5: `0.1111`
- Required-tables-ok@5: `1/9`
- Mean Recall@10: `0.2222`
- Required-tables-ok@10: `2/9`
- MRR: `0.0509`

| Query | Recall@5 | Required ok@5 | Required tables | Top-10 retrieved | Missing required (top-10) |
|---|---:|---:|---|---|---|
| CP1 | 0.000 | False | khkartikel, khkartikellieferanten, khkartikelvarianten | khklagerplatzbuchungen, khkppsfabelegepositionen, khkppsfabelegeagpositionen, khkppsffmatbeigestellt, khkppsffmaterial, khkppsressourcenpositionen, khkdispoartikel, tkhkprintpositionartikelvk, tkhkppsprintfapos, tkhkppsressourcenpositionen | khkartikel, khkartikellieferanten, khkartikelvarianten |
| CP2 | 0.000 | False | khkvkbelege, khkbelegepositionen | khklagerplatzbuchungen, khkbuchungsjournal, khkkostenjournal, khkbuchungserfassung, khkkostenumsatz, khkkontenumsatz, khkbuchungserfassunga, khkppsffbestellmengen, osemzizsalabrechnungenferien, tkhkbuchungsnachweis | khkbelegepositionen, khkvkbelege |
| CP3 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | osemzizsalquellensteuertarif, osemzizzebuchungen, khkvkbelege, osemzizzeabrechnungendetailtag, osemzizzeabrechnungendetailtarif, khkppsfabelegepositionen, khkstatvk, osemzizsalabrechnungendetail, khkppsfabelege, khkppsfabelegeagpositionen | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP4 | 1.000 | True | osemzizzebuchungen | khkppsrueckmeldungen, khkvkbelegepositionen, osemzizzebuchungen, khkvkbelege, osemzizzeabrechnungendetailtarif, khkppsfabelegepositionen, khkstatvk, osemzizsalabrechnungendetail, khkppsfabelegeagpositionen, khkartikel |  |
| CP5 | 0.000 | False | osemzizzebuchungen, khkppsstempel | khkartikelvarianten, osemzizsallohnartenerfassung, osemzizsalpersonalstammabrechnungsparameter, khkartikelgruppen, khkmitarbeiter, khkekbelegarten | khkppsstempel, osemzizzebuchungen |
| CP6 | 0.000 | False | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | khkppsfabelegepositionen, khkppsfabelegeagpositionen, khkppsffmatbeigestellt, khkppsffmaterial, khkppsressourcenpositionen, khkdispoartikel, tkhkprintpositionartikelvk, tkhkppsprintfapos, tkhkppsressourcenpositionen, khkppsgemeinkostensaetze | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager |
| CP7 | 0.000 | False | khkbuchungserfassung | khkppsrueckmeldungen, khkppsbdestempelbackup, khkartikelbewertungmekhistorie, khkvkbelegepositionen, khkppsbdeap, khkppsbdemafm, khkvkbelegezkd, khkbuchungserfassung, khkdruckbelegekennzeichen, khkppsfabelegepositionen |  |
| CP8 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | khklagerplatzbuchungen, khkppsrueckmeldungen, khkppsbdestempelbackup, osemzizsalquellensteuertarif, khkbuchungsjournal, khkartikelbewertungmekhistorie, khkvkbelegepositionen, khkppsbdeap, khkppsbdemafm, khkppsbdemafmart | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP9 | 0.000 | False | osemzizzebuchungen, khkppsstempel, khkppsbelege, khkpppsbelegeagpositionen | khkppsrueckmeldungen, khkppsbdestempelbackup, khkppsbdeap, tkhkppsmitarbeiterbuchungen, khkppsfabelegepositionen, khkppsfabelege, khkppsfabelegeagpositionen, khkppsffbeistellpos, khkppsbdestempel, osemzizsallohnartenerfassung | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel, osemzizzebuchungen |
