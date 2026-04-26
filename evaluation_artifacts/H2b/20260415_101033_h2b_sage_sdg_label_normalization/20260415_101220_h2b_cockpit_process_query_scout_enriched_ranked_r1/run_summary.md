# /process_query Northwind Run (scout_enriched_ranked)

- Run ID: `20260415_101220_h2b_cockpit_process_query_scout_enriched_ranked_r1`
- Run name: `h2b_cockpit_process_query_scout_enriched_ranked_r1`
- Scout start: `ScoutRunner` | active=`True`
- Scout end: `ScoutRunner` | active=`True`
- Meaning: Scout mode ACTIVE: MCP discovery backend is ScoutRunner. Catalog source is scout_runner_catalog.
- Total queries: `9`
- Successes: `9`
- Failures: `0`
- Avg latency ms: `8264.9`
- P95 latency ms: `18260.0`
- Required stage traces: `discovery, ranked`
- Trace requirements met: `9/9`

| Query | Status | Latency (ms) | SQL present | Trace OK | Missing trace stages | Tables used |
|---|---|---:|---|---|---|---|
| CP1 | success | 6811 | True | True |  | dbo.KHKPpsFfMatBeigestellt, dbo.KHKPpsFfMaterial, dbo.KHKPpsFfRetourenMat, dbo.KHKPpsGemeinkostensaetze, dbo.KHKPpsRueckmeldungenFibu, z.B, khkppsffmaterial, khkppsffmatbeigestellt, khkppsffretourenmat, khkppsgemeinkostensaetze, khkppsrueckmeldungenfibu, b |
| CP2 | success | 7647 | True | True |  | dbo.KHKDispostapelPositionen, dbo.KHKEKBelege, dbo.KHKEKBelegePositionen, dbo.KHKEKBelegePositionenChargen, dbo.KHKEKBelegeZuschlaege, z.B, khkdispostapelpositionen, khkekbelege, khkekbelegepositionen, khkekbelegepositionenchargen, khkekbelegezuschlaege, b |
| CP3 | success | 13208 | True | True |  | dbo.BSCrmPositionenZeitstempel, dbo.KHKPpsRessourcenkopf, dbo.vwKHK_AC_Bestandsverlauf, dbo.BSCrmPositionenVorgaenger, dbo.KHKPpsFfRueckmeldungen, z.B, dbo.BCSPjmArtikelObjektVerbrauch, dbo.BCSPjmObjekteStapelPositionen, dbo.BCSPjmVertraegeBedingungen, dbo.BCSPjmVertraegeBedingungenPos, dbo.BSBDEGesRm, dbo.BCSPjmArtikelObjectConsumption, bsbdegesrm, bscrmpositionenzeitstempel, khkppsressourcenkopf, vwkhk_ac_bestandsverlauf, bscrmpositionenvorgaenger, khkppsffrueckmeldungen, b, bcspjmartikelobjektverbrauch, bcspjmobjektestapelpositionen, bcspjmvertraegebedingungen, bcspjmvertraegebedingungenpos, bcspjmartikelobjectconsumption |
| CP4 | success | 7052 | True | True |  | dbo.KHKPpsRueckmeldungen, dbo.vwKHKPpsSammellohnschein, dbo.KHKPpsBdeStempelBackup, dbo.KHKPpsBdeAp, dbo.BCSPjmProjekteVorgaengeLeist, khkppsbdeap, khkppsrueckmeldungen, vwkhkppssammellohnschein, khkppsbdestempelbackup, bcspjmprojektevorgaengeleist |
| CP5 | success | 18260 | True | True |  | dbo.BCSPjmProjekteVorgaengeZeitenReise, dbo.BSBDEGesRm, dbo.BSBDEStempelGesRm, dbo.BSMyKampagneMitarbeiter, dbo.BsWinBDEMa, z.B, dbo.BSMyCampaignEmployees, dbo.KHKDruckbelegeKennzeichen, bsbdegesrm, bcspjmprojektevorgaengezeitenreise, bsbdestempelgesrm, bsmykampagnemitarbeiter, bswinbdema, b, bsmycampaignemployees, khkdruckbelegekennzeichen |
| CP6 | success | 3786 | True | True |  | dbo.KHKIFAuftraege, dbo.KHKLieferschwellen, dbo.KHKPpsFfMatBeigestellt, dbo.KHKPpsFfMaterial, dbo.KHKPpsFfRetourenMat, z.B, khkppsffmaterial, khkifauftraege, khklieferschwellen, khkppsffmatbeigestellt, khkppsffretourenmat, b |
| CP7 | success | 6876 | True | True |  | dbo.KHKPpsWerkzeuge, dbo.KHKDruckprozesseDruckbelege2, dbo.KHKPpsRessourcenAGPositionen, dbo.KHKDruckbelegeKennzeichen, dbo.KHKPpsFaBelegeAGPositionen, u201edbo.KHKPpsWerkzeuge, khkppswerkzeuge, khkdruckprozessedruckbelege2, khkppsressourcenagpositionen, khkdruckbelegekennzeichen, khkppsfabelegeagpositionen |
| CP8 | success | 5670 | False | True |  | dbo.BCSPjmArtikelObjektVerbrauch, dbo.BCSPjmArtikelObjektZaehler, dbo.BCSPjmObjekte, dbo.BCSPjmObjekteRapport, dbo.BCSPjmObjekteStapel, dbo.BCSPjmArtikelObjectConsumption, dbo.BCSPjmObjekteStacks, dbo.BCSPjmAdressenKontakt, dbo.BCSPjmObjekteZubehoer, dbo.BCSPjmProjekte, z.B, bcspjmartikelobjektverbrauch, bcspjmartikelobjektzaehler, bcspjmobjekte, bcspjmobjekterapport, bcspjmobjektestapel, bcspjmartikelobjectconsumption, bcspjmobjektestacks, bcspjmadressenkontakt, bcspjmobjektezubehoer, bcspjmprojekte, b |
| CP9 | success | 5074 | False | True |  | dbo.BSBDEGesRm, dbo.BSBDEGesRmSerienNr, dbo.BSBDEStempelGesRm, dbo.BSBDEStempelGesRmSerienNr, dbo.BSCrmKalenderPositionen, z.B, bsbdegesrm, bsbdegesrmseriennr, bsbdestempelgesrm, bsbdestempelgesrmseriennr, bscrmkalenderpositionen, b |
