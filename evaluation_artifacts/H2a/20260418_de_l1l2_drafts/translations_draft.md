# German L1-L2 Query Drafts — H2a Benchmark Extension

**Date:** 2026-04-18
**Purpose:** Pre-approval draft of 20 German queries to mirror the existing 20 English L1-L2 queries in `northwind_extended_difficulty_v1.jsonl`.
**Status:** AWAITING APPROVAL — no canonical artifacts have been modified.

---

## Naming convention

Existing pattern in the dataset:

| Code | Level | Category label | Language |
|---|---|---|---|
| `NW1`-`NW10` | L1 | `direct` | `en` |
| `NL1`-`NL10` | L2 | `paraphrase` | `en` |
| `CL1`-`CL12` | L3 | `crosslingual` | `de` |
| `HX1`-`HX12` | L4 | `complex` | `de` |
| `US_CL*_U*` | L5 | `underspecified` | `de` |
| `LB_CL*_LX*` | L6 | `lexical_breakpoint` | `de` |

**Proposed new IDs:**

| New ID | Level | Category label | Language | Mirrors |
|---|---|---|---|---|
| `NW_DE_01`-`NW_DE_10` | L1 | `direct` | `de` | `NW1`-`NW10` |
| `NL_DE_01`-`NL_DE_10` | L2 | `paraphrase` | `de` | `NL1`-`NL10` |

Rationale: preserves the `NW`/`NL` category encoding already in use, appends `_DE_NN` to mark the language shift without breaking the prefix-as-category contract.

---

## Translation methodology

- **Calibration corpus:** existing German L3/L4/L5 queries (CL1-CL12, HX1-HX12, US_CL*). These set the vocabulary register used throughout the thesis benchmark.
- **Register:** Standard written German appropriate for Swiss business reporting (matches the `CHF` / `'` thousands convention used in existing agent responses). Informal phrasing avoided.
- **Lexical-mismatch principle:** all queries use German business vocabulary (Artikel, Abnehmer, Meldebestand, Auftragsnummer, Versanddienstleister, rabattiert, Nettoumsatz, …). None of these tokens match the English-named Northwind identifiers (products, customers, reorder_level, order_id, shippers, discount, revenue).
- **Ground truth:** German queries preserve the intent of their English counterparts exactly, so `required_tables` and `reference_sql` are identical to the English mirror.

---

## L1 Direct — 10 queries (`NW_DE_01` through `NW_DE_10`)

L1 style: direct, simple intent-to-table mapping. German business vernacular substitutes for English schema identifiers.

### NW_DE_01 — mirrors NW1
- **German:** Gib die fünf Artikel zurück, deren Lagerbestand unter dem Meldebestand liegt, sortiert nach grösster Bestandslücke zuerst. Liefere genau: Artikelnummer, Artikelbezeichnung, Lagerbestand und Meldebestand.
- **English (NW1):** Return the 5 products that need reordering (units_in_stock < reorder_level), sorted by the largest shortage first. Return exactly: product_id, product_name, units_in_stock, reorder_level.
- **required_tables:** `products`

### NW_DE_02 — mirrors NW2
- **German:** Berechne je Warengruppe den Nettoumsatz nach Rabatten als SUMME(Stückpreis × Menge × (1 − Rabatt)). Gib für alle Warengruppen den Warengruppennamen und den Nettoumsatz zurück, absteigend nach Nettoumsatz sortiert.
- **English (NW2):** For each product category, calculate total revenue after discounts as SUM(unit_price * quantity * (1 - discount)). Return all categories with category_name and total_revenue, sorted by total_revenue descending.
- **required_tables:** `categories`, `products`, `order_details`

### NW_DE_03 — mirrors NW3
- **German:** Liste alle Abnehmer mit mehr als 10 verschiedenen Aufträgen. Gib Abnehmernummer, Firmenbezeichnung, Auftragsanzahl und Auftragswert zurück, wobei Auftragswert = SUMME(Stückpreis × Menge) ohne Rabattberücksichtigung. Sortiere absteigend nach Auftragswert und dann nach Abnehmernummer.
- **English (NW3):** List customers with more than 10 distinct orders. Return customer_id, company_name, order_count, and total_order_value where total_order_value = SUM(unit_price * quantity) (without discount adjustment), sorted by total_order_value descending and customer_id.
- **required_tables:** `customers`, `orders`, `order_details`

### NW_DE_04 — mirrors NW4
- **German:** Gib für jeden Versanddienstleister anhand von Aufträgen und Dienstleisterstamm die Dienstleisternummer, die Firmenbezeichnung, die Anzahl verspäteter Sendungen (Versanddatum > Solltermin) und die Gesamtzahl der Sendungen zurück.
- **English (NW4):** Using orders and shippers, for each shipping company return shipper_id, company_name, late_shipments (where shipped_date > required_date), and total_shipments.
- **required_tables:** `orders`, `shippers`

### NW_DE_05 — mirrors NW5
- **German:** Berechne für jede Mitarbeiterin und jeden Mitarbeiter den rabattierten Nettoumsatz aus den zugehörigen Aufträgen. Verknüpfe Personal-, Auftrags- und Auftragspositionsdaten und gib Personalnummer, Vorname, Nachname und Nettoumsatz zurück, absteigend nach Nettoumsatz sortiert.
- **English (NW5):** For each employee, calculate total revenue after discounts from their orders. Join employees, orders, and order_details, and return employee_id, first_name, last_name, total_revenue sorted by total_revenue descending.
- **required_tables:** `employees`, `orders`, `order_details`

### NW_DE_06 — mirrors NW6
- **German:** Gib die fünf Artikel mit der höchsten verkauften Stückzahl zurück. Nutze PostgreSQL LIMIT 5 (nicht TOP). Liefere Artikelnummer, Artikelbezeichnung und verkaufte Stückzahl, absteigend sortiert nach Stückzahl und dann aufsteigend nach Artikelnummer.
- **English (NW6):** Return the top 5 best-selling products by total quantity sold. Use PostgreSQL LIMIT 5 (not TOP). Return product_id, product_name, quantity_sold, sorted by quantity_sold descending and product_id.
- **required_tables:** `products`, `order_details`

### NW_DE_07 — mirrors NW7
- **German:** Finde die Lieferantenpaare, die am häufigsten zusammen in derselben Bestellung vorkommen. Nutze einen Self-Join auf Auftragspositionen als ap1 und ap2 (gleiche Auftragsnummer, unterschiedliche Artikelnummer), verknüpfe Artikel p1/p2 und Lieferanten l1/l2, und erzwinge l1.Lieferantennummer < l2.Lieferantennummer, um Paare zu deduplizieren. Berechne Gemeinsam_Bestellt = ANZAHL(DISTINCT ap1.Auftragsnummer). Gib Lieferant_1, Lieferant_2, Gemeinsam_Bestellt zurück, absteigend sortiert nach Gemeinsam_Bestellt und dann nach Lieferant_1 und Lieferant_2, Top 10.
- **English (NW7):** Find supplier pairs that most frequently appear together in the same order. Use a self-join on order_details as od1 and od2 (same order_id, different product_id), join products p1/p2 and suppliers s1/s2, enforce s1.supplier_id < s2.supplier_id to deduplicate pairs, and compute co_order_count = COUNT(DISTINCT od1.order_id). Return supplier_1, supplier_2, co_order_count, sorted by co_order_count descending, then supplier_1 and supplier_2, top 10.
- **required_tables:** `suppliers`, `products`, `order_details`

### NW_DE_08 — mirrors NW8
- **German:** Berechne je Abnehmerland den durchschnittlichen Auftragswert in zwei Aggregationsschritten: zuerst den Auftragswert je Auftrag als SUMME(Stückpreis × Menge × (1 − Rabatt)), anschliessend den Mittelwert der Auftragswerte pro Land. Gib Land und Mittlerer_Auftragswert zurück.
- **English (NW8):** By customer country, compute average order value with a two-step aggregation: first compute each order total as SUM(unit_price * quantity * (1 - discount)), then average order_total per country. Return country and avg_order_value.
- **required_tables:** `customers`, `orders`, `order_details`

### NW_DE_09 — mirrors NW9
- **German:** Zähle die offenen Aufträge (Versanddatum IST NULL) und ermittle ihren rabattierten Gesamtwert. Gib Offene_Auftraege = ANZAHL(DISTINCT Auftragsnummer) und Gesamtwert = SUMME(Stückpreis × Menge × (1 − Rabatt)) zurück.
- **English (NW9):** Count distinct pending orders and their discounted total value where shipped_date IS NULL. Return pending_orders = COUNT(DISTINCT order_id) and total_value = SUM(unit_price * quantity * (1 - discount)).
- **required_tables:** `orders`, `order_details`

### NW_DE_10 — mirrors NW10
- **German:** Zeige die monatliche Nettoumsatzentwicklung nach Rabatten, gruppiert auf DATE_TRUNC('month', Auftragsdatum)::date als monat. Gib monat und Umsatz zurück, aufsteigend nach monat sortiert.
- **English (NW10):** Show monthly revenue trend after discounts by grouping on DATE_TRUNC('month', order_date)::date as month. Return month and revenue, sorted by month.
- **required_tables:** `orders`, `order_details`

---

## L2 Paraphrase — 10 queries (`NL_DE_01` through `NL_DE_10`)

L2 style: indirect or paraphrastic formulation of the same intent, without explicit column specifications. German business vernacular throughout.

### NL_DE_01 — mirrors NL1
- **German:** Welche Artikel werden voraussichtlich bald knapp, gemessen am aktuellen Lagerbestand im Vergleich zum Meldebestand?
- **English (NL1):** Which offerings look most likely to run short soon based on current stock versus replenishment threshold?
- **required_tables:** `products`

### NL_DE_02 — mirrors NL2
- **German:** Welche Abnehmer bestellen besonders häufig und erzielen gleichzeitig insgesamt den höchsten Bruttoauftragswert?
- **English (NL2):** Which buyers place very frequent orders and represent the highest gross order value overall?
- **required_tables:** `customers`, `order_details`, `orders`

### NL_DE_03 — mirrors NL3
- **German:** Bei welchen Zustellpartnern werden zugesagte Termine am häufigsten verfehlt, und wie gross ist deren gesamtes Sendungsvolumen?
- **English (NL3):** Which delivery providers miss promised dates the most, and what is their overall shipment volume?
- **required_tables:** `orders`, `shippers`

### NL_DE_04 — mirrors NL4
- **German:** Welche Artikel bewegen insgesamt die höchste Anzahl an Einheiten?
- **English (NL4):** Which offerings move the highest number of units overall?
- **required_tables:** `order_details`, `products`

### NL_DE_05 — mirrors NL5
- **German:** In welchen Abnehmerregionen ist der durchschnittliche Warenkorbwert am höchsten?
- **English (NL5):** Where are average basket values highest by buyer location?
- **required_tables:** `customers`, `order_details`, `orders`

### NL_DE_06 — mirrors NL6
- **German:** Wie entwickelt sich der rabattbereinigte Ertrag Monat für Monat?
- **English (NL6):** How does discounted income evolve month by month?
- **required_tables:** `order_details`, `orders`

### NL_DE_07 — mirrors NL7
- **German:** Welche vorgelagerten Partner erzielen über ihre Waren den höchsten rabattbereinigten Umsatz?
- **English (NL7):** Which upstream partners generate the most discounted turnover through their goods?
- **required_tables:** `order_details`, `products`, `suppliers`

### NL_DE_08 — mirrors NL8
- **German:** Wie stark und wie häufig sind Sendungen je Frachtführer durchschnittlich verspätet?
- **English (NL8):** For each freight carrier, how late are shipments on average and how often are they late?
- **required_tables:** `orders`, `shippers`

### NL_DE_09 — mirrors NL9
- **German:** Welche Vertriebsmitarbeitenden betreuen die breiteste Abnehmerbasis?
- **English (NL9):** Which staff members serve the broadest buyer base?
- **required_tables:** `employees`, `orders`

### NL_DE_10 — mirrors NL10
- **German:** Welche Konten haben bis heute keine Transaktion ausgelöst?
- **English (NL10):** Which accounts have never transacted?
- **required_tables:** `customers`, `orders`

---

## Reference SQL plan

All 20 new queries share reference SQL with their English mirrors. No SQL will be rewritten; the existing SQL from `reference_sql_l1_l4.json` for NW1-NW10 and NL1-NL10 will be duplicated under the new IDs. This keeps the ground truth identical across mirrored pairs so that any metric delta between the English and German cohorts is attributable to language alone.

## Files that will be modified (after approval)

1. `code/eval/datasets/northwind_extended_difficulty_v1.jsonl` — append 20 lines.
2. `code/eval/datasets/northwind_extended_difficulty_v1.contracts.json` — append 20 entries.
3. `code/eval/runs/20260416_h2a_semantic_labels/reference_sql_l1_l4.json` — add 20 keys (this is the reference-SQL artifact the L1-L4 semantic labeler already consumes; see `label_pipeline.py:43`).

All changes are **append-only**; existing 64 entries and their reference SQL remain byte-identical.

## Schema and reference-SQL verification (completed 2026-04-18)

Executed all 20 English-mirror reference SQLs against `localhost:55432 northwind` (read-only, 15 s timeout) before drafting the German versions. Full report: [reference_sql_verification.json](reference_sql_verification.json).

**Schema coverage:**
Northwind `public` schema contains 14 tables: `categories, customer_customer_demo, customer_demographics, customers, employee_territories, employees, order_details, orders, products, region, shippers, suppliers, territories, us_states`. All 20 `required_tables` sets resolve against this schema.

**Reference-SQL smoke test (all 20 pass, 0 failures):**

| qid | rows | preview of first row |
|---|---|---|
| NW1 | 5 | `(31, 'Gorgonzola Telino', 0, 20)` |
| NW2 | 8 | `('Beverages', 267868.18)` |
| NW3 | 28 | `('QUICK', 'QUICK-Stop', 28, 117483.39)` |
| NW4 | 3 | `(1, 'Speedy Express', 12, 249)` |
| NW5 | 9 | `(4, 'Margaret', 'Peacock', 232890.85)` |
| NW6 | 5 | `(60, 'Camembert Pierrot', 1577)` |
| NW7 | 10 | `('Specialty Biscuits, Ltd.', 'Plutzer Lebensmittelgroßmärkte AG', 25)` |
| NW8 | 21 | `('Austria', 3200.10)` |
| NW9 | 1 | `(21, 25937.43)` |
| NW10 | 23 | `(1996-07-01, 27861.90)` |
| NL1 | 18 | `(31, 'Gorgonzola Telino', 0, 20, 20)` |
| NL2 | 89 | `('QUICK', 'QUICK-Stop', 28, 117483.39)` |
| NL3 | 3 | `(2, 'United Package', 16, 326)` |
| NL4 | 77 | `(60, 'Camembert Pierrot', 1577)` |
| NL5 | 21 | `('Austria', 3200.10)` |
| NL6 | 23 | `(1996-07-01, 27861.90)` |
| NL7 | 29 | `(18, 'Aux joyeux ecclésiastiques', 153691.28)` |
| NL8 | 3 | `(1, 'Speedy Express', 8.08, 12, 245)` |
| NL9 | 9 | `(4, 'Margaret', 'Peacock', 75)` |
| NL10 | 2 | `('FISSA', 'FISSA Fabrica Inter. Salchichas S.A.')` |

**Reading this:** the reference SQL defines the ground-truth answer for each intent. The German queries `NW_DE_01`-`NW_DE_10` and `NL_DE_01`-`NL_DE_10` inherit these exact SQL statements unchanged, so the ground-truth rowsets above are the rowsets the agent's generated SQL will be compared against when the semantic labeler runs on the new cohort.

**Remaining schema checks (will be done after you approve, before Step 6):**
- Total query count in `.jsonl` is 84.
- No duplicate `id` / `query_id` across dataset and contracts.
- Every new query has exactly one contract entry and one reference SQL entry.

## What stays frozen

- All existing 64 queries: text, category, contract, reference SQL — byte-identical.
- Thesis LaTeX: untouched.
- April 14 run directories: not rerun, not modified.
