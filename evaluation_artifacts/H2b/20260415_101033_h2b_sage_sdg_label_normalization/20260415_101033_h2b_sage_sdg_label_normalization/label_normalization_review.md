# Partner Label Normalization Review

- Generated: `2026-04-15T10:10:33.103221Z`
- Labels source: `C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\eval\datasets\cockpit_partner_table_labels_v1.json`
- Catalog source: `http://localhost:8000`

## Summary

- Unique partner labels: `13`
- Exact matches: `8`
- Alias/prefix matches: `5`
- Manual confirmed: `0`
- Unresolved: `0`

| Partner label | Match type | Matched live table | Candidate matches |
|---|---|---|---|
| dbo.KHKArtikelLieferanten | alias_prefix_normalized | dbo.KHKArtikelLieferant | dbo.KHKArtikel, dbo.KHKArtikelLieferant, dbo.KHKArtikelLieferantPreise, dbo.KHKArtikelLieferantRabatte, dbo.KHKArtikelVarianten, dbo.KHKStatEKLieferanten, dbo.KHKArtikelPlanung, dbo.KHKArtikelKunden |
| dbo.KHKBelegePositionen | alias_prefix_normalized | dbo.KHKVKBelegePositionen | dbo.KHKVKBelegePositionen, dbo.KHKPJBelegePositionen, dbo.KHKIVBelegePositionen, dbo.KHKEKBelegePositionen, dbo.KHKPpsFaBelegePositionen, dbo.KHKVKBelegePositionenLager, dbo.KHKPpsFaBelegeAGPositionen, dbo.KHKPJBelegePositionenLager |
| dbo.KHKPppsBelegeAGPositionen | alias_prefix_normalized | dbo.KHKPpsFaBelegeAGPositionen | dbo.KHKPpsFaBelegeAGPositionen, dbo.tKHKPpsFaBelegeAGPositionen, dbo.KHKPpsFaBelegePositionen, dbo.KHKPJBelegePositionen, dbo.KHKVKBelegePositionen, dbo.KHKIVBelegePositionen, dbo.KHKEKBelegePositionen, dbo.KHKPJBelegePositionenLager |
| dbo.KHKPpsBelege | alias_prefix_normalized | dbo.KHKPpsFaBelege | dbo.KHKPpsFaBelege, dbo.KHKPJBelege, dbo.tKHKPpsBdeFaBelege, dbo.KHKVKBelege, dbo.KHKIVBelege, dbo.KHKEKBelege, dbo.tKHKPpsPrintFaBelege, dbo.KHKPpsWerkzeuge |
| dbo.KHKPpsStempel | alias_prefix_normalized | dbo.KHKPpsBdeStempel | dbo.KHKPpsBdeStempel, dbo.KHKPpsBdeStempelLp, dbo.KHKPpsBdeStempelSplit, dbo.KHKPpsBdeStempelBackup, dbo.KHKPpsDispostapel |
| KHKBuchungserfassung | exact | dbo.KHKBuchungserfassung | dbo.KHKBuchungserfassung |
| dbo.KHKArtikel | exact | dbo.KHKArtikel | dbo.KHKArtikel |
| dbo.KHKArtikelVarianten | exact | dbo.KHKArtikelVarianten | dbo.KHKArtikelVarianten |
| dbo.KHKEKBelege | exact | dbo.KHKEKBelege | dbo.KHKEKBelege |
| dbo.KHKEKBelegePositionen | exact | dbo.KHKEKBelegePositionen | dbo.KHKEKBelegePositionen |
| dbo.KHKEKBelegePositionenLager | exact | dbo.KHKEKBelegePositionenLager | dbo.KHKEKBelegePositionenLager |
| dbo.KHKVKBelege | exact | dbo.KHKVKBelege | dbo.KHKVKBelege |
| dbo.OsemzizZEBuchungen | exact | dbo.OsemzizZEBuchungen | dbo.OsemzizZEBuchungen |
