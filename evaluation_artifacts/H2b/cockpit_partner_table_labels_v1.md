# Cockpit Partner Table Labels v1

Source documents:
- `/Users/juli/Downloads/Cockpit.docx` (question list)
- `/Users/juli/Downloads/CockpitMitTabellen.docx` (question + relevant tables)

This file documents the table-label mapping used for production table-correctness evaluation.

| Query ID | Question (short) | Required tables (partner mapping) | Notes |
|---|---|---|---|
| CP1 | Ø56 Material bestellen | `dbo.KHKArtikel`, `dbo.KHKArtikelLieferanten`, `dbo.KHKArtikelVarianten` | Reorder logic |
| CP2 | Bestellung XY geliefert | `dbo.KHKVKBelege`, `dbo.KHKBelegePositionen` | Delivery status |
| CP3 | Teile 04:00-07:00 vs 08:00-11:00 | `dbo.KHKPpsBelege`, `dbo.KHKPppsBelegeAGPositionen`, `dbo.KHKPpsStempel` | Production + time windows |
| CP4 | Anwesenheits-/Pausenzeiten | `dbo.OsemzizZEBuchungen` | Time compliance |
| CP5 | MA XY heute Morgen | `dbo.OsemzizZEBuchungen`, `dbo.KHKPpsStempel` | Time + ERP feedback |
| CP6 | Material XY angeliefert | `dbo.KHKEKBelege`, `dbo.KHKEKBelegePositionen`, `dbo.KHKEKBelegePositionenLager` | Inbound logistics |
| CP7 | Wartungspunkte vs Kosten | `KHKBuchungserfassung` + external `NewZP_Plus64.accde/WartungsTermine` | Includes non-SQL source |
| CP8 | Verhältnis Vorgabe/Ist | `dbo.KHKPpsBelege`, `dbo.KHKPppsBelegeAGPositionen`, `dbo.KHKPpsStempel` | Target vs actual |
| CP9 | Start Zeiterfassung vs Start BDE | `dbo.OsemzizZEBuchungen`, `dbo.KHKPpsStempel`, `dbo.KHKPpsBelege`, `dbo.KHKPppsBelegeAGPositionen` | Duplicate table mention deduplicated |

Machine-readable label file:
- `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_partner_table_labels_v1.json`
