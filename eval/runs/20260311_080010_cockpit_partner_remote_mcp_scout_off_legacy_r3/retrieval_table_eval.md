# Cockpit MCP Table-Retrieval Evaluation

- Generated: `2026-03-11T08:00:11.790108Z`
- Run ID: `20260311_080010_cockpit_partner_remote_mcp_scout_off_legacy_r3`
- Mode label: `scout_off_legacy`
- MCP URL: `http://192.168.1.35:8000`

## Aggregate

- Total queries: `9`
- Mean Recall@5: `0.1111`
- Required-tables-ok@5: `1/9`
- Mean Recall@10: `0.1111`
- Required-tables-ok@10: `1/9`
- MRR: `0.1111`

| Query | Recall@5 | Required ok@5 | Required tables | Top-10 retrieved | Missing required (top-10) |
|---|---:|---:|---|---|---|
| CP1 | 0.000 | False | khkartikel, khkartikellieferanten, khkartikelvarianten | khkppsffmaterial, khksmlklassen, khkppsstlimportpos, khkadressenverweise, khkadressentelefon, khkadressen, tkhkppsffbeistellmaterial, khksteuerklassen, khkbelegartenadressen, khkadressenformate | khkartikel, khkartikellieferanten, khkartikelvarianten |
| CP2 | 0.000 | False | khkvkbelege, khkbelegepositionen | khkvkbelegarten, khkekbelegarten, khkbuchungserfassung, khkvkvorgaengepositionen, khkekvorgaengepositionen, khklagerplatzbuchungen, khkbuchungsjournal, khkkostenjournal, khkkostenumsatz, khkvkvorgaenge | khkbelegepositionen, khkvkbelege |
| CP3 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | osemzizsalpersonalstammkorrespondenz, osemzizzepersonalstammabrechnungsparameter, osemzizsalpersonalstammkontaktpersonen, osemzizsalpersonalstammbewilligung, osemzizsalabrechnungenstunden, osemzizsalpersonalstammabwesenheit, osemzizsalpersonalstammabrechnungsparameter, osemzizsalpersonalstammkinder, osemzizsalpersonalstammeintrittaustritt, osemzizsalpersonalstamm | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP4 | 0.000 | False | osemzizzebuchungen | khkppsschichtmodelleintervalle, osemzizvsaversicherungen, osemzizsalabrechnungendetail, osemzizsalpersonalstammabrechnungsparameter, osemzizsallohnartenstammabrechnungsparameter, khkvwprotokollkopf, bswinbdema, khkanlagen, osemzizvsaagenturen, osemzizvsabroker | osemzizzebuchungen |
| CP5 | 0.000 | False | osemzizzebuchungen, khkppsstempel | khklagerplaetzepermanenteiv, khkppsffrueckmeldungen, khkverpackungen, khkartikelvariantenverpackungen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkverpackungeninhaltsstoffe, usysdmsdocumenttypemapping, tbcspjminfomanagerprint, khklagerplatzbuchungenchargen | khkppsstempel, osemzizzebuchungen |
| CP6 | 0.000 | False | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager | khkppsffmaterial, khkverpackungen, khkartikelvariantenverpackungen, bscrmkalenderpositionenverweise, bscrmkalenderpositionenverweiseblacklist, khkverpackungeninhaltsstoffe, tkhkppsfafibupositionen, khklagerplatzbuchungenchargen, khklagerplatzbestaendechargen, khklagerplatzbuchungenseriennr | khkekbelege, khkekbelegepositionen, khkekbelegepositionenlager |
| CP7 | 1.000 | True | khkbuchungserfassung | khkbuchungserfassung, khkbuchungserfassungop, khkbuchungserfassungsdiv, khkbuchungserfassunga, khkbuchungserfassungsdiva, khkbuchungserfassungopa, khkbuchungserfassungsdivbg, khkbuchungserfassungbg, khkbelegerfassunggridfield, osemzizsallohnartenerfassung |  |
| CP8 | 0.000 | False | khkppsbelege, khkpppsbelegeagpositionen, khkppsstempel | khkartikelzubehoer, khkpreislistenartikel, khkartikelvariantenverpackungen, khkrabattlistenartikel, khkivbelegeposzugangknhistorie, khkppsekzuordnung, khkartikelstueckliste, khkartikelbewertungmekhistorie, khkartikelzubehoerstaffel, bscrmkalenderpositionenverweiseblacklist | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel |
| CP9 | 0.000 | False | osemzizzebuchungen, khkppsstempel, khkppsbelege, khkpppsbelegeagpositionen | khkprojektezeiterfassung, khklagerplatzbuchungenzugkng, khkppsbdestempelbackup, khkppsbdeap, khkppsbdestempel, khkartikelzubehoer, khkvkbelegezuschlaege, khkarchivvkzuschlaege, khkekbelegezuschlaege, bcspjmprojektevorgaengezeiten | khkpppsbelegeagpositionen, khkppsbelege, khkppsstempel, osemzizzebuchungen |
