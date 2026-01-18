"""
Phase 1: Column Role Enricher - Fuzzy German/English Role Tagging

Scout Mode v2 enhancement that adds rich, column-level role_hints using fuzzy matching
and optional LLM-powered translation for German/English bidirectional support.

Roles tagged:
- id (primary keys, surrogate keys, identifiers)
- fk_to:<Table> (foreign keys with target table)
- date (temporal data: Datum, Lieferdatum, Rechnungsdatum, Buchungsdatum, etc.)
- amount (financial: Betrag, Preis, Kosten, Wert, Summe, Total, etc.)
- quantity (counts: Menge, Anzahl, Stück, Count, Quantity)
- status (state: Status, Zustand, State, Condition)
- email, phone, postal_code (contact data)
- name (text: Bezeichnung, Name, Titel, Description)
- code (coded identifiers: ArtikelNr, KundenNr, Code, Number)

Architecture:
- Proxy-only separation: No business logic, just metadata enrichment
- Multi-tier matching: Direct keywords → fuzzy synonyms → LLM fallback
- Caching: Memoization of LLM calls for performance
- Graceful degradation: Works without LLM (pure fuzzy fallback)
- German error messages: All exceptions report in German
- Backward compatible: Missing role_hints don't break old code
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from functools import lru_cache
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ColumnRoleEnricher:
    """
    Enriches column metadata with role hints using fuzzy German/English matching.
    
    Multi-tier approach:
    1. Direct keyword match (high confidence)
    2. Fuzzy match via string similarity + synonyms (medium confidence)
    3. LLM-powered translation (optional, for ambiguous cases)
    4. Type-based inference (fallback)
    """
    
    # ===== MULTILINGUAL LEXICON (German <-> English) =====
    # Each role has German and English keywords/patterns
    
    LEXICON: Dict[str, Dict[str, List[str]]] = {
        "id": {
            "en": ["id", "identifier", "pk", "primary", "key", "uid", "uuid", "oid", "objectid"],
            "de": ["id", "identifikator", "pk", "primär", "schlüssel", "uid", "uuid", "oid", "objektid", "nr", "nummer"],
            # Compound patterns
            "patterns": [r"^id$", r"_id$", r"^pk", r"_key$", r"uuid", r"^oid"]
        },
        "date": {
            "en": ["date", "time", "created", "modified", "birth", "start", "end", "due", "deadline", "timestamp", "datetime"],
            "de": ["datum", "zeit", "erstellt", "geändert", "geburt", "anfang", "ende", "fällig", "termin", "zeitstempel", "datefrom", "dateto", "lieferdatum", "rechnungsdatum", "buchungsdatum", "erstellungsdatum", "änderungsdatum"],
            "patterns": [r"datum$", r"_date$", r"^date", r"_time$", r"^created", r"^modified", r"_at$"]
        },
        "amount": {
            "en": ["amount", "price", "cost", "total", "sum", "value", "rate", "fee", "charge", "balance", "account"],
            "de": ["betrag", "preis", "kosten", "gesamt", "summe", "wert", "satz", "gebühr", "belastung", "saldo", "konto", "gesamtbetrag"],
            "patterns": [r"betrag$", r"_amount$", r"^amount", r"_price$", r"_cost$", r"_total$", r"^total"]
        },
        "quantity": {
            "en": ["quantity", "count", "number", "qty", "amount", "volume", "units", "items"],
            "de": ["menge", "anzahl", "zahl", "menge", "volumen", "einheiten", "artikel", "stück"],
            "patterns": [r"menge$", r"_qty$", r"^qty", r"_count$", r"^count", r"_quantity$"]
        },
        "status": {
            "en": ["status", "state", "condition", "stage", "phase", "flag", "active", "enabled", "deleted"],
            "de": ["status", "zustand", "bedingung", "phase", "bühne", "flagge", "aktiv", "aktiviert", "gelöscht"],
            "patterns": [r"status$", r"_status$", r"^status", r"_state$", r"^state", r"_flag$"]
        },
        "email": {
            "en": ["email", "mail", "address", "e-mail"],
            "de": ["email", "e-mail", "mail", "adresse"],
            "patterns": [r"email$", r"_email$", r"^email", r"_mail$", r"mail_"]
        },
        "phone": {
            "en": ["phone", "telephone", "mobile", "tel", "contact", "number"],
            "de": ["telefon", "handy", "mobil", "tel", "kontakt", "nummer"],
            "patterns": [r"phone$", r"_phone$", r"^phone", r"telefon", r"mobil"]
        },
        "postal_code": {
            "en": ["zip", "postal", "postcode", "plz"],
            "de": ["plz", "postleitzahl", "postcode", "zip"],
            "patterns": [r"plz$", r"_plz$", r"^plz", r"_zip$", r"postal"]
        },
        "name": {
            "en": ["name", "title", "label", "description", "text", "name"],
            "de": ["name", "titel", "etikett", "beschreibung", "text", "bezeichnung", "name", "name"],
            "patterns": [r"^name$", r"_name$", r"^name", r"_title$", r"^title"]
        },
        "code": {
            "en": ["code", "number", "articlenumber", "customernumber", "external_id"],
            "de": ["code", "nummer", "artikelnummer", "kundennummer", "externe_id", "artikelnr", "kundennr"],
            "patterns": [r"^code$", r"_code$", r"nr$", r"nummer$", r"_nr$"]
        }
    }
    
    # Synonyms for fuzzy matching (help translate between German/English)
    SYNONYMS: Dict[str, List[str]] = {
        # German -> English synonyms
        "datum": ["date", "timestamp"],
        "betrag": ["amount", "total"],
        "menge": ["quantity", "count"],
        "preis": ["price", "cost"],
        "status": ["status", "state"],
        "telefon": ["phone", "telephone"],
        "email": ["email", "mail"],
        "plz": ["postal_code", "zip"],
        "name": ["name", "title"],
        "code": ["code", "number"],
        "nummer": ["number", "code"],
        "zustand": ["status", "state"],
        "beschreibung": ["description", "name"],
        
        # English -> German synonyms (reverse)
        "date": ["datum", "zeit"],
        "amount": ["betrag", "summe"],
        "quantity": ["menge", "anzahl"],
        "price": ["preis", "kosten"],
        "status": ["status", "zustand"],
        "phone": ["telefon", "handy"],
        "postal": ["plz", "postleitzahl"],
        "description": ["beschreibung", "name"],
    }
    
    def __init__(self, use_llm: bool = False, llm_client=None):
        """
        Initialize the column role enricher.
        
        Args:
            use_llm: Enable LLM-powered translation (optional, requires API key)
            llm_client: LLM client (e.g., OpenAI) for translation
        """
        self.use_llm = use_llm
        self.llm_client = llm_client
        self._translation_cache: Dict[str, str] = {}
        self._role_cache: Dict[Tuple[str, str], List[str]] = {}
    
    def enrich_columns(self, columns: List[Dict], foreign_keys: List[Dict] = None) -> List[Dict]:
        """
        Enrich columns with role_hints.
        
        Args:
            columns: List of column dicts with 'name' and 'type'
            foreign_keys: List of FK dicts with 'column' and 'referenced_table'
        
        Returns:
            List of columns with added 'role_hints' field
        """
        if foreign_keys is None:
            foreign_keys = []
        
        # Build FK map for quick lookup
        fk_map = {}
        for fk in foreign_keys:
            fk_map[fk.get("column", "")] = fk.get("referenced_table", "")
        
        enriched = []
        for col in columns:
            col_copy = dict(col)
            col_name = col_copy.get("name", "").strip()
            col_type = col_copy.get("type", "").lower().strip()
            
            # Skip empty names
            if not col_name:
                col_copy["role_hints"] = []
                enriched.append(col_copy)
                continue
            
            try:
                # Infer roles for this column
                roles = self.infer_role_hints(
                    col_name,
                    col_type,
                    fk_table=fk_map.get(col_name)
                )
                col_copy["role_hints"] = roles
            except Exception as e:
                logger.warning(f"Error enriching column {col_name}: {e}")
                col_copy["role_hints"] = []
            
            enriched.append(col_copy)
        
        return enriched
    
    def infer_role_hints(
        self,
        col_name: str,
        col_type: str,
        fk_table: Optional[str] = None
    ) -> List[str]:
        """
        Infer role hints for a single column.
        
        Args:
            col_name: Column name (e.g., "BestellDatum", "product_id")
            col_type: Column data type (e.g., "datetime", "int", "varchar")
            fk_table: Referenced table if this is a FK
        
        Returns:
            List of role hints (e.g., ["date", "fk_to:Order"])
        """
        cache_key = (col_name, col_type, fk_table or "")
        if cache_key in self._role_cache:
            return self._role_cache[cache_key]
        
        roles: List[str] = []
        col_name_lower = col_name.lower()
        col_type_lower = col_type.lower()
        
        # === Tier 1: Check if it's a foreign key ===
        if fk_table:
            roles.append(f"fk_to:{fk_table}")
        
        # === Tier 2: Direct keyword match (high confidence) ===
        for role, keywords in self.LEXICON.items():
            if self._direct_match(col_name_lower, col_type_lower, keywords):
                if role not in roles:
                    roles.append(role)
        
        # === Tier 3: Fuzzy match via synonyms (medium confidence) ===
        if not roles:  # Only if no direct match
            fuzzy_roles = self._fuzzy_match(col_name_lower, col_type_lower)
            roles.extend(fuzzy_roles)
        
        # === Tier 4: LLM-powered translation (optional) ===
        if self.use_llm and not roles and self.llm_client:
            try:
                llm_roles = self._llm_infer_role(col_name, col_type)
                if llm_roles:
                    roles.extend(llm_roles)
            except Exception as e:
                logger.debug(f"LLM role inference failed for {col_name}: {e}")
        
        # === Tier 5: Type-based inference (fallback) ===
        if not roles:
            type_roles = self._type_based_inference(col_type_lower, col_name_lower)
            roles.extend(type_roles)
        
        self._role_cache[cache_key] = roles
        return roles
    
    def _direct_match(self, col_name: str, col_type: str, keywords: Dict) -> bool:
        """
        Direct keyword match using exact terms and regex patterns.
        
        Checks:
        1. Exact keyword match (English + German)
        2. Regex patterns
        """
        en_keywords = keywords.get("en", [])
        de_keywords = keywords.get("de", [])
        patterns = keywords.get("patterns", [])
        
        # Check English keywords
        for kw in en_keywords:
            if kw in col_name or kw in col_type:
                return True
        
        # Check German keywords
        for kw in de_keywords:
            if kw in col_name or kw in col_type:
                return True
        
        # Check regex patterns
        for pattern in patterns:
            if re.search(pattern, col_name, re.IGNORECASE):
                return True
        
        return False
    
    def _fuzzy_match(self, col_name: str, col_type: str, threshold: float = 0.6) -> List[str]:
        """
        Fuzzy match using string similarity + synonyms.
        
        For each synonym, compute Levenshtein-like similarity.
        If similarity > threshold, assign that role.
        """
        roles: List[str] = []
        
        for role, keywords in self.LEXICON.items():
            # Check if any synonym is similar to col_name
            all_synonyms = (
                keywords.get("en", []) +
                keywords.get("de", []) +
                self.SYNONYMS.get(role, [])
            )
            
            for synonym in all_synonyms:
                similarity = self._string_similarity(col_name, synonym)
                if similarity >= threshold:
                    if role not in roles:
                        roles.append(role)
                    break  # Found a match for this role, move to next role
        
        return roles
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Simple string similarity metric (0.0 to 1.0).
        Uses prefix/suffix + character overlap.
        """
        s1, s2 = s1.lower(), s2.lower()
        
        # Exact match
        if s1 == s2:
            return 1.0
        
        # Substring match
        if s2 in s1 or s1 in s2:
            return 0.85
        
        # Character overlap (simple Jaccard)
        set1, set2 = set(s1), set(s2)
        if len(set1 | set2) == 0:
            return 0.0
        
        overlap = len(set1 & set2) / len(set1 | set2)
        return overlap
    
    def _llm_infer_role(self, col_name: str, col_type: str) -> List[str]:
        """
        Use LLM (Claude) to infer role from column name (German/English aware).
        
        Prompt the LLM to translate and identify the role.
        """
        if not self.llm_client:
            return []
        
        # Check translation cache
        cache_key = f"{col_name}_{col_type}"
        if cache_key in self._translation_cache:
            role_str = self._translation_cache[cache_key]
            return [r.strip() for r in role_str.split(",") if r.strip()]
        
        try:
            prompt = f"""Given a database column name and type, identify its semantic role.

Column Name: {col_name}
Column Type: {col_type}

The name might be in German or English. Return a comma-separated list of roles from this set:
id, date, amount, quantity, status, email, phone, postal_code, name, code

Be conservative - only return a role if you're confident. Return empty if unsure.

Example outputs:
- "id"
- "date"
- "amount,quantity"
- "" (if unsure)

Your answer (roles only, no explanation):"""
            
            # Call LLM
            response = self.llm_client.call(prompt)  # Assumes client has a call() method
            role_str = response.strip()
            
            # Cache the result
            self._translation_cache[cache_key] = role_str
            
            # Parse result
            return [r.strip() for r in role_str.split(",") if r.strip()]
        
        except Exception as e:
            logger.debug(f"LLM call failed for {col_name}: {e}")
            return []
    
    def _type_based_inference(self, col_type: str, col_name: str) -> List[str]:
        """
        Infer role purely from data type (fallback).
        
        Rules:
        - date/datetime/timestamp → "date"
        - numeric types + currency-like name → "amount"
        - numeric types → "quantity"
        - varchar/text + email-like name → "email"
        - varchar/text + short name → "code"
        """
        roles: List[str] = []
        
        # Date types
        if any(t in col_type for t in ["date", "datetime", "datetime2", "timestamp", "time"]):
            roles.append("date")
        
        # Numeric types
        elif any(t in col_type for t in ["int", "float", "decimal", "numeric", "bigint", "smallint", "money", "real"]):
            # Check if name suggests amount
            if any(t in col_name for t in ["betrag", "preis", "kosten", "summe", "wert", "amount", "price", "cost", "total"]):
                roles.append("amount")
            elif any(t in col_name for t in ["menge", "anzahl", "qty", "count", "quantity"]):
                roles.append("quantity")
            else:
                # Default: numeric → quantity (or id if name suggests)
                if any(t in col_name for t in ["id", "_id", "key", "nr", "nummer"]):
                    roles.append("id")
                else:
                    roles.append("quantity")  # Conservative guess
        
        # Text types
        elif any(t in col_type for t in ["varchar", "text", "char", "nvarchar", "string"]):
            if any(t in col_name for t in ["email", "mail", "e-mail"]):
                roles.append("email")
            elif any(t in col_name for t in ["phone", "telefon", "tel", "mobile", "handy"]):
                roles.append("phone")
            elif any(t in col_name for t in ["plz", "postal", "zip"]):
                roles.append("postal_code")
            elif any(t in col_name for t in ["code", "nummer", "number", "nr"]):
                roles.append("code")
            else:
                roles.append("name")  # Default for text
        
        return roles
    
    @staticmethod
    def get_error_message_de(error_key: str, details: str = "") -> str:
        """
        Get German error messages for common errors.
        
        Args:
            error_key: Error type (e.g., "column_missing", "invalid_type")
            details: Additional error context
        
        Returns:
            German error message
        """
        messages = {
            "column_missing": f"Spalte fehlt oder ist leer: {details}",
            "invalid_type": f"Ungültiger Spaltentyp: {details}",
            "fk_not_found": f"Fremdschlüssel-Tabelle nicht gefunden: {details}",
            "enrichment_failed": f"Anreicherung fehlgeschlagen: {details}",
            "llm_error": f"LLM-Inferenz fehlgeschlagen: {details}",
        }
        return messages.get(error_key, f"Fehler: {details}")