# Partner Label Normalization Review

- Generated: `2026-03-15T15:08:49.374181Z`
- Labels source: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_partner_table_labels_v1.json`
- Catalog source: `/private/tmp/catalog_smoke.json`

## Summary

- Unique partner labels: `13`
- Exact matches: `9`
- Alias/prefix matches: `4`
- Manual confirmed: `0`
- Unresolved: `0`

| Partner label | Match type | Matched live table | Candidate matches |
|---|---|---|---|
| dbo.KHKArtikelLieferanten | alias_prefix_normalized | dbo.KHKArtikelLieferant | dbo.KHKArtikel, dbo.KHKArtikelLieferant, dbo.KHKArtikelVarianten |
| dbo.KHKBelegePositionen | alias_prefix_normalized | dbo.KHKVKBelegePositionen | dbo.KHKVKBelegePositionen, dbo.KHKEKBelegePositionen, dbo.KHKPpsFABelegeAGPositionen, dbo.KHKEKBelegePositionenLager |
| dbo.KHKPppsBelegeAGPositionen | alias_prefix_normalized | dbo.KHKPpsFABelegeAGPositionen | dbo.KHKPpsFABelegeAGPositionen, dbo.KHKVKBelegePositionen, dbo.KHKEKBelegePositionen, dbo.KHKEKBelegePositionenLager |
| dbo.KHKPpsBelege | alias_prefix_normalized | dbo.KHKPpsFABelege | dbo.KHKPpsFABelege, dbo.KHKVKBelege, dbo.KHKEKBelege |
| KHKBuchungserfassung | exact | dbo.KHKBuchungserfassung | dbo.KHKBuchungserfassung |
| dbo.KHKArtikel | exact | dbo.KHKArtikel | dbo.KHKArtikel |
| dbo.KHKArtikelVarianten | exact | dbo.KHKArtikelVarianten | dbo.KHKArtikelVarianten |
| dbo.KHKEKBelege | exact | dbo.KHKEKBelege | dbo.KHKEKBelege |
| dbo.KHKEKBelegePositionen | exact | dbo.KHKEKBelegePositionen | dbo.KHKEKBelegePositionen |
| dbo.KHKEKBelegePositionenLager | exact | dbo.KHKEKBelegePositionenLager | dbo.KHKEKBelegePositionenLager |
| dbo.KHKPpsStempel | exact | dbo.KHKPpsStempel | dbo.KHKPpsStempel |
| dbo.KHKVKBelege | exact | dbo.KHKVKBelege | dbo.KHKVKBelege |
| dbo.OsemzizZEBuchungen | exact | dbo.OsemzizZEBuchungen | dbo.OsemzizZEBuchungen |
