"""Append 20 German L1-L2 queries to the canonical H2a artifacts.

- northwind_extended_difficulty_v1.jsonl: append 20 lines
- northwind_extended_difficulty_v1.contracts.json: append 20 entries
- reference_sql_l1_l4.json: add 20 keys (SQL copied from English mirror)

Idempotent: if any target ID already exists, raise.
"""
import json
from pathlib import Path

ROOT = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis")
DATASET = ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.jsonl"
CONTRACTS = ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.contracts.json"
REF_SQL = ROOT / "code/eval/runs/20260416_h2a_semantic_labels/reference_sql_l1_l4.json"

# German query texts
DE_QUERIES: dict[str, str] = {
    "NW_DE_01": "Gib die fünf Artikel zurück, deren Lagerbestand unter dem Meldebestand liegt, sortiert nach grösster Bestandslücke zuerst. Liefere genau: Artikelnummer, Artikelbezeichnung, Lagerbestand und Meldebestand.",
    "NW_DE_02": "Berechne je Warengruppe den Nettoumsatz nach Rabatten als SUMME(Stückpreis × Menge × (1 − Rabatt)). Gib für alle Warengruppen den Warengruppennamen und den Nettoumsatz zurück, absteigend nach Nettoumsatz sortiert.",
    "NW_DE_03": "Liste alle Abnehmer mit mehr als 10 verschiedenen Aufträgen. Gib Abnehmernummer, Firmenbezeichnung, Auftragsanzahl und Auftragswert zurück, wobei Auftragswert = SUMME(Stückpreis × Menge) ohne Rabattberücksichtigung. Sortiere absteigend nach Auftragswert und dann nach Abnehmernummer.",
    "NW_DE_04": "Gib für jeden Versanddienstleister anhand von Aufträgen und Dienstleisterstamm die Dienstleisternummer, die Firmenbezeichnung, die Anzahl verspäteter Sendungen (Versanddatum > Solltermin) und die Gesamtzahl der Sendungen zurück.",
    "NW_DE_05": "Berechne für jede Mitarbeiterin und jeden Mitarbeiter den rabattierten Nettoumsatz aus den zugehörigen Aufträgen. Verknüpfe Personal-, Auftrags- und Auftragspositionsdaten und gib Personalnummer, Vorname, Nachname und Nettoumsatz zurück, absteigend nach Nettoumsatz sortiert.",
    "NW_DE_06": "Gib die fünf Artikel mit der höchsten verkauften Stückzahl zurück. Nutze PostgreSQL LIMIT 5 (nicht TOP). Liefere Artikelnummer, Artikelbezeichnung und verkaufte Stückzahl, absteigend sortiert nach Stückzahl und dann aufsteigend nach Artikelnummer.",
    "NW_DE_07": "Finde die Lieferantenpaare, die am häufigsten zusammen in derselben Bestellung vorkommen. Nutze einen Self-Join auf Auftragspositionen als ap1 und ap2 (gleiche Auftragsnummer, unterschiedliche Artikelnummer), verknüpfe Artikel p1/p2 und Lieferanten l1/l2, und erzwinge l1.Lieferantennummer < l2.Lieferantennummer, um Paare zu deduplizieren. Berechne Gemeinsam_Bestellt = ANZAHL(DISTINCT ap1.Auftragsnummer). Gib Lieferant_1, Lieferant_2, Gemeinsam_Bestellt zurück, absteigend sortiert nach Gemeinsam_Bestellt und dann nach Lieferant_1 und Lieferant_2, Top 10.",
    "NW_DE_08": "Berechne je Abnehmerland den durchschnittlichen Auftragswert in zwei Aggregationsschritten: zuerst den Auftragswert je Auftrag als SUMME(Stückpreis × Menge × (1 − Rabatt)), anschliessend den Mittelwert der Auftragswerte pro Land. Gib Land und Mittlerer_Auftragswert zurück.",
    "NW_DE_09": "Zähle die offenen Aufträge (Versanddatum IST NULL) und ermittle ihren rabattierten Gesamtwert. Gib Offene_Auftraege = ANZAHL(DISTINCT Auftragsnummer) und Gesamtwert = SUMME(Stückpreis × Menge × (1 − Rabatt)) zurück.",
    "NW_DE_10": "Zeige die monatliche Nettoumsatzentwicklung nach Rabatten, gruppiert auf DATE_TRUNC('month', Auftragsdatum)::date als monat. Gib monat und Umsatz zurück, aufsteigend nach monat sortiert.",
    "NL_DE_01": "Welche Artikel werden voraussichtlich bald knapp, gemessen am aktuellen Lagerbestand im Vergleich zum Meldebestand?",
    "NL_DE_02": "Welche Abnehmer bestellen besonders häufig und erzielen gleichzeitig insgesamt den höchsten Bruttoauftragswert?",
    "NL_DE_03": "Bei welchen Zustellpartnern werden zugesagte Termine am häufigsten verfehlt, und wie gross ist deren gesamtes Sendungsvolumen?",
    "NL_DE_04": "Welche Artikel bewegen insgesamt die höchste Anzahl an Einheiten?",
    "NL_DE_05": "In welchen Abnehmerregionen ist der durchschnittliche Warenkorbwert am höchsten?",
    "NL_DE_06": "Wie entwickelt sich der rabattbereinigte Ertrag Monat für Monat?",
    "NL_DE_07": "Welche vorgelagerten Partner erzielen über ihre Waren den höchsten rabattbereinigten Umsatz?",
    "NL_DE_08": "Wie stark und wie häufig sind Sendungen je Frachtführer durchschnittlich verspätet?",
    "NL_DE_09": "Welche Vertriebsmitarbeitenden betreuen die breiteste Abnehmerbasis?",
    "NL_DE_10": "Welche Konten haben bis heute keine Transaktion ausgelöst?",
}

# Map new_id -> english_mirror (source for contract + reference_sql).
MIRROR: dict[str, str] = {
    "NW_DE_01": "NW1",  "NW_DE_02": "NW2",  "NW_DE_03": "NW3",
    "NW_DE_04": "NW4",  "NW_DE_05": "NW5",  "NW_DE_06": "NW6",
    "NW_DE_07": "NW7",  "NW_DE_08": "NW8",  "NW_DE_09": "NW9",
    "NW_DE_10": "NW10",
    "NL_DE_01": "NL1",  "NL_DE_02": "NL2",  "NL_DE_03": "NL3",
    "NL_DE_04": "NL4",  "NL_DE_05": "NL5",  "NL_DE_06": "NL6",
    "NL_DE_07": "NL7",  "NL_DE_08": "NL8",  "NL_DE_09": "NL9",
    "NL_DE_10": "NL10",
}


def main() -> int:
    # --- Load current state ---
    jsonl_lines: list[dict] = []
    with DATASET.open() as f:
        for line in f:
            line = line.strip()
            if line:
                jsonl_lines.append(json.loads(line))
    contracts: list[dict] = json.loads(CONTRACTS.read_text())
    ref_sql_map: dict[str, str] = json.loads(REF_SQL.read_text())

    existing_ids = {row["id"] for row in jsonl_lines}
    existing_contract_ids = {c["query_id"] for c in contracts}

    # --- Idempotency guards ---
    for qid in DE_QUERIES:
        if qid in existing_ids:
            raise SystemExit(f"[FATAL] {qid} already present in dataset JSONL — aborting.")
        if qid in existing_contract_ids:
            raise SystemExit(f"[FATAL] {qid} already present in contracts — aborting.")
        if qid in ref_sql_map:
            raise SystemExit(f"[FATAL] {qid} already present in reference SQL — aborting.")
    for mirror in MIRROR.values():
        if mirror not in ref_sql_map:
            raise SystemExit(f"[FATAL] mirror {mirror} missing from reference SQL — aborting.")

    # --- Build contract lookup from English mirrors ---
    contract_by_id: dict[str, dict] = {c["query_id"]: c for c in contracts}

    # --- Build additions ---
    new_jsonl_rows = []
    new_contracts = []
    new_ref_entries: dict[str, str] = {}
    for qid, text in DE_QUERIES.items():
        mirror = MIRROR[qid]
        level_category = contract_by_id[mirror]["category"]  # "direct" or "paraphrase"
        required_tables = list(contract_by_id[mirror]["required_tables"])
        new_jsonl_rows.append({
            "id": qid,
            "question": text,
            "category": level_category,
            "language": "de",
            "mirrors": mirror,
        })
        new_contracts.append({
            "query_id": qid,
            "required_tables": required_tables,
            "category": level_category,
            "language": "de",
            "mirrors": mirror,
        })
        new_ref_entries[qid] = ref_sql_map[mirror]

    # --- Write atomically ---
    # JSONL: append new lines, preserving existing lines byte-identically.
    # We already loaded existing lines as dicts; re-serialise would alter formatting.
    # Instead, read the raw file and append.
    with DATASET.open("a") as f:
        for row in new_jsonl_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # contracts.json: full rewrite (was always a single pretty-printed array).
    merged_contracts = contracts + new_contracts
    CONTRACTS.write_text(json.dumps(merged_contracts, indent=2, ensure_ascii=False))

    # reference_sql_l1_l4.json: full rewrite.
    merged_ref = {**ref_sql_map, **new_ref_entries}
    REF_SQL.write_text(json.dumps(merged_ref, indent=2, ensure_ascii=False))

    # --- Post-check ---
    jsonl_after = []
    with DATASET.open() as f:
        for line in f:
            line = line.strip()
            if line:
                jsonl_after.append(json.loads(line))
    contracts_after = json.loads(CONTRACTS.read_text())
    ref_after = json.loads(REF_SQL.read_text())

    assert len(jsonl_after) == 84, f"Expected 84 dataset rows, got {len(jsonl_after)}"
    assert len(contracts_after) == 84, f"Expected 84 contract rows, got {len(contracts_after)}"
    # reference_sql_l1_l4 covers only L1-L4 queries (NW*, NL*, CL*, HX*): 40 existing + 20 new = 60.
    expected_ref_count = len(ref_sql_map) + 20
    assert len(ref_after) == expected_ref_count, (
        f"Expected {expected_ref_count} ref_sql entries, got {len(ref_after)}"
    )

    ids = [r["id"] for r in jsonl_after]
    assert len(set(ids)) == len(ids), "Duplicate id in dataset"
    contract_ids = [c["query_id"] for c in contracts_after]
    assert len(set(contract_ids)) == len(contract_ids), "Duplicate query_id in contracts"
    assert set(ids) == set(contract_ids), (
        f"Dataset and contract ID sets differ:\n"
        f"  only_in_dataset={sorted(set(ids) - set(contract_ids))}\n"
        f"  only_in_contracts={sorted(set(contract_ids) - set(ids))}"
    )

    # Every L1-L4 query must have ref SQL.
    l1_l4_categories = {"direct", "paraphrase", "crosslingual", "complex"}
    for row in jsonl_after:
        if row.get("category") in l1_l4_categories:
            assert row["id"] in ref_after, f"Missing ref SQL for {row['id']}"

    print("=== Append complete ===")
    print(f"  Dataset rows : {len(jsonl_after)} (was 64, +20)")
    print(f"  Contract rows: {len(contracts_after)} (was 64, +20)")
    print(f"  Ref SQL keys : {len(ref_after)} (was {len(ref_sql_map)}, +20)")
    print(f"  New IDs: {list(DE_QUERIES.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
