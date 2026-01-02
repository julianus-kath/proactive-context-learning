"""
Test fixtures for Scout Mode v2 Phase 1 testing.

Provides sample columns (German + English) for testing role enrichment.
"""

# ===== GERMAN COLUMNS (typical German ERP systems) =====
GERMAN_COLUMNS = [
    {"name": "BestellID", "type": "int"},
    {"name": "BestellDatum", "type": "datetime"},
    {"name": "Lieferdatum", "type": "date"},
    {"name": "KundenNr", "type": "varchar"},
    {"name": "KundenID", "type": "int"},
    {"name": "ArtikelnNr", "type": "varchar"},
    {"name": "Menge", "type": "int"},
    {"name": "EinzelBetrag", "type": "decimal"},
    {"name": "Gesamtbetrag", "type": "money"},
    {"name": "RechnungsDatum", "type": "datetime"},
    {"name": "Status", "type": "varchar"},
    {"name": "Kundenname", "type": "varchar"},
    {"name": "Telefon", "type": "varchar"},
    {"name": "EMail", "type": "varchar"},
    {"name": "PLZ", "type": "varchar"},
    {"name": "ArtikelCode", "type": "varchar"},
    {"name": "Beschreibung", "type": "text"},
    {"name": "ErstelltAm", "type": "datetime"},
    {"name": "GeändertAm", "type": "datetime"},
    {"name": "Zustand", "type": "varchar"},
]

# ===== ENGLISH COLUMNS (typical English ERP systems) =====
ENGLISH_COLUMNS = [
    {"name": "OrderID", "type": "int"},
    {"name": "OrderDate", "type": "datetime"},
    {"name": "DeliveryDate", "type": "date"},
    {"name": "CustomerNumber", "type": "varchar"},
    {"name": "CustomerID", "type": "int"},
    {"name": "ProductNumber", "type": "varchar"},
    {"name": "Quantity", "type": "int"},
    {"name": "UnitPrice", "type": "decimal"},
    {"name": "TotalAmount", "type": "money"},
    {"name": "InvoiceDate", "type": "datetime"},
    {"name": "Status", "type": "varchar"},
    {"name": "CustomerName", "type": "varchar"},
    {"name": "Phone", "type": "varchar"},
    {"name": "Email", "type": "varchar"},
    {"name": "PostalCode", "type": "varchar"},
    {"name": "ProductCode", "type": "varchar"},
    {"name": "Description", "type": "text"},
    {"name": "CreatedAt", "type": "datetime"},
    {"name": "ModifiedAt", "type": "datetime"},
    {"name": "State", "type": "varchar"},
]

# ===== MIXED COLUMNS (real-world German/English mix) =====
MIXED_COLUMNS = [
    {"name": "id", "type": "int"},  # English: id
    {"name": "Datum", "type": "date"},  # German: Datum
    {"name": "timestamp", "type": "datetime"},  # English: timestamp
    {"name": "Betrag", "type": "decimal"},  # German: Betrag
    {"name": "amount", "type": "money"},  # English: amount
    {"name": "Menge", "type": "int"},  # German: Menge
    {"name": "qty", "type": "int"},  # English: qty
    {"name": "telefon_nr", "type": "varchar"},  # German: telefon_nr
    {"name": "phone_number", "type": "varchar"},  # English: phone_number
    {"name": "email_addr", "type": "varchar"},  # English: email_addr
    {"name": "status_code", "type": "varchar"},  # English: status_code
    {"name": "is_active", "type": "boolean"},  # English: is_active
]

# ===== EDGE CASES =====
EDGE_CASES = [
    {"name": "", "type": "int"},  # Empty name
    {"name": "col_12345", "type": "varchar"},  # Generic/unhelpful name
    {"name": "xxx", "type": "unknown"},  # Unknown type
    {"name": "Rechnungsnummer", "type": "int"},  # No direct role match
    {"name": "is_deleted", "type": "boolean"},  # Boolean flag
    {"name": "created_date", "type": "datetime"},  # Compound English
    {"name": "ErstellungsDatum", "type": "datetime"},  # Compound German
    {"name": "fk_OrderId", "type": "int"},  # FK prefix
]

# ===== EXPECTED ROLE MAPPINGS =====
EXPECTED_ROLES = {
    # German
    "BestellID": ["id"],
    "BestellDatum": ["date"],
    "Lieferdatum": ["date"],
    "KundenNr": ["code"],
    "KundenID": ["id"],
    "ArtikelnNr": ["code"],
    "Menge": ["quantity"],
    "EinzelBetrag": ["amount"],
    "Gesamtbetrag": ["amount"],
    "RechnungsDatum": ["date"],
    "Status": ["status"],
    "Kundenname": ["name"],
    "Telefon": ["phone"],
    "EMail": ["email"],
    "PLZ": ["postal_code"],
    "ArtikelCode": ["code"],
    "Beschreibung": ["name"],
    "ErstelltAm": ["date"],
    "GeändertAm": ["date"],
    "Zustand": ["status"],
    
    # English
    "OrderID": ["id"],
    "OrderDate": ["date"],
    "DeliveryDate": ["date"],
    "CustomerNumber": ["code"],
    "CustomerID": ["id"],
    "ProductNumber": ["code"],
    "Quantity": ["quantity"],
    "UnitPrice": ["amount"],
    "TotalAmount": ["amount"],
    "InvoiceDate": ["date"],
    "Phone": ["phone"],
    "Email": ["email"],
    "PostalCode": ["postal_code"],
    "ProductCode": ["code"],
    "CustomerName": ["name"],
    "Description": ["name"],
    "CreatedAt": ["date"],
    "ModifiedAt": ["date"],
    "State": ["status"],
    
    # Mixed
    "id": ["id"],
    "Datum": ["date"],
    "timestamp": ["date"],
    "Betrag": ["amount"],
    "amount": ["amount"],
    "Menge": ["quantity"],
    "qty": ["quantity"],
    "status_code": ["status"],
    
    # Edge cases (may be empty or fallback)
    "": [],
    "col_12345": [],
    "xxx": [],
}

# ===== FOREIGN KEY RELATIONSHIPS =====
SAMPLE_FOREIGN_KEYS = [
    {"column": "KundenID", "referenced_table": "Customer"},
    {"column": "ArtikelnNr", "referenced_table": "Product"},
    {"column": "CustomerID", "referenced_table": "Customer"},
    {"column": "ProductNumber", "referenced_table": "Product"},
]

# ===== TABLES WITH COLUMNS AND FKS =====
SAMPLE_INVOICE_TABLE_DE = {
    "name": "Rechnung",
    "schema": "dbo",
    "type": "BASE TABLE",
    "columns": [
        {"name": "RechnungsID", "type": "int"},
        {"name": "RechnungsDatum", "type": "datetime"},
        {"name": "KundenID", "type": "int"},
        {"name": "GesamtBetrag", "type": "money"},
        {"name": "Status", "type": "varchar"},
    ],
    "foreign_keys": [
        {"column": "KundenID", "referenced_table": "Kunde"},
    ],
}

SAMPLE_INVOICE_TABLE_EN = {
    "name": "Invoice",
    "schema": "dbo",
    "type": "BASE TABLE",
    "columns": [
        {"name": "InvoiceID", "type": "int"},
        {"name": "InvoiceDate", "type": "datetime"},
        {"name": "CustomerID", "type": "int"},
        {"name": "TotalAmount", "type": "money"},
        {"name": "Status", "type": "varchar"},
    ],
    "foreign_keys": [
        {"column": "CustomerID", "referenced_table": "Customer"},
    ],
}