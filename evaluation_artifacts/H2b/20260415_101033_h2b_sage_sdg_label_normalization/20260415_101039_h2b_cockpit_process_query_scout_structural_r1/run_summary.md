# /process_query Northwind Run (scout_structural)

- Run ID: `20260415_101039_h2b_cockpit_process_query_scout_structural_r1`
- Run name: `h2b_cockpit_process_query_scout_structural_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `9`
- Successes: `8`
- Failures: `1`
- Avg latency ms: `10382.2`
- P95 latency ms: `31210.0`
- Required stage traces: `discovery, ranked`
- Trace requirements met: `9/9`

| Query | Status | Latency (ms) | SQL present | Trace OK | Missing trace stages | Tables used |
|---|---|---:|---|---|---|---|
| CP1 | success | 7485 | True | True |  | dbo.KHKPpsFfMatBeigestellt, dbo.KHKPpsFfMaterial, dbo.KHKPpsFfRetourenMat, dbo.KHKPpsGemeinkostensaetze, dbo.KHKPpsRueckmeldungenFibu, z.B, khkppsffmaterial, khkppsffmatbeigestellt, khkppsffretourenmat, khkppsgemeinkostensaetze, khkppsrueckmeldungenfibu, b |
| CP2 | success | 7330 | True | True |  | dbo.KHKDispostapelPositionen, dbo.KHKEKBelege, dbo.KHKEKBelegePositionen, dbo.KHKEKBelegePositionenChargen, dbo.KHKEKBelegeZuschlaege, z.B, khkdispostapelpositionen, khkekbelege, khkekbelegepositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege, b |
| CP3 | success | 4953 | True | True |  | dbo.BCSPjmProjekteVorgaengeZeitenReise, dbo.KHKMitarbeiter, dbo.KHKPpsRessourcenkopf, dbo.KHKProjekte, dbo.KHKProjekteZeiterfassung, z.B, khkprojektezeiterfassung, bcspjmprojektevorgaengezeitenreise, khkmitarbeiter, khkppsressourcenkopf, khkprojekte, b |
| CP4 | success | 18207 | True | True |  | dbo.KHKPpsRueckmeldungen, dbo.vwKHKPpsSammellohnschein, dbo.KHKPpsBdeStempelBackup, dbo.KHKPpsBdeAp, dbo.BCSPjmProjekteVorgaengeLeist, khkppsbdeap, khkppsrueckmeldungen, vwkhkppssammellohnschein, khkppsbdestempelbackup, bcspjmprojektevorgaengeleist |
| CP5 | failed | 31210 | False | True |  |  |
| CP6 | success | 5060 | True | True |  | dbo.KHKIFAuftraege, dbo.KHKLieferschwellen, dbo.KHKPpsFfMatBeigestellt, dbo.KHKPpsFfMaterial, dbo.KHKPpsFfRetourenMat, z.B, khkppsffmaterial, khkifauftraege, khklieferschwellen, khkppsffmatbeigestellt, khkppsffretourenmat, b |
| CP7 | success | 7419 | True | True |  | dbo.KHKPpsWerkzeuge, dbo.KHKDruckprozesseDruckbelege2, dbo.KHKPpsRessourcenAGPositionen, dbo.KHKDruckbelegeKennzeichen, dbo.KHKPpsFaBelegeAGPositionen, u201edbo.KHKPpsWerkzeuge, khkppswerkzeuge, khkdruckprozessedruckbelege2, khkppsressourcenagpositionen, khkdruckbelegekennzeichen, khkppsfabelegeagpositionen |
| CP8 | success | 5870 | False | True |  | dbo.BCSPjmArtikelObjektVerbrauch, dbo.BCSPjmArtikelObjektZaehler, dbo.BCSPjmObjekte, dbo.BCSPjmObjekteRapport, dbo.BCSPjmObjekteStapel, dbo.BCSPjmArtikelObjectConsumption, dbo.BCSPjmObjekteStacks, dbo.BCSPjmAdressenKontakt, dbo.BCSPjmObjekteZubehoer, dbo.BCSPjmProjekte, z.B, bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmobjekte, bcspjmobjekterapport, bcspjmobjektestapel, bcspjmartikelobjectconsumption, bcspjmobjektestacks, bcspjmadressenkontakt, bcspjmobjektezubehoer, bcspjmprojekte, b |
| CP9 | success | 5906 | False | True |  | dbo.BSBDEGesRm, dbo.BSBDEGesRmSerienNr, dbo.BSBDEStempelGesRm, dbo.BSBDEStempelGesRmSerienNr, dbo.BSCrmKalenderPositionen, z.B, bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bscrmkalenderpositionen, b |
