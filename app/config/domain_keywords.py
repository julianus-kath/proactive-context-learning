"""
Domain Keywords Configuration

This file contains domain-specific keyword mappings for table selection.
These are heuristic hints to help the system identify relevant tables.

**IMPORTANT: These keywords are OPTIONAL**
- Set DOMAIN_KEYWORDS = {} to disable keyword-based matching entirely
- The system will still work using direct table/column name matching
- Future: Replace with knowledge base or embedding-based semantic search

**How to customize:**
1. Edit the keywords below to match your database domain
2. Add new categories as needed
3. Or disable by setting DOMAIN_KEYWORDS = {}

**Future Enhancement:**
Replace this with:
- Knowledge base API (fetch_from_knowledge_base())
- External JSON config (load_from_json("config/keywords.json"))
- LLM-based intent classification
- Embedding-based semantic search
"""

# Domain-specific keyword mappings
# These are common patterns in business/ERP systems
# Modify or disable these based on your database structure
DOMAIN_KEYWORDS = {
    'sales': ['sales?', 'orders?', 'order_items?', 'invoices?', 'revenue'],
    'customers': ['customers?', 'clients?', 'accounts?', 'contacts?'],
    'products': ['products?', 'items?', 'inventory', 'stock', 'catalog'],
    'employees': ['employees?', 'staff', 'users?', 'personnel', 'hr'],
    'finance': ['payments?', 'transactions?', 'ledger', 'accounts?', 'billing', 'unpaid'],
    'shipping': ['shipments?', 'deliveries?', 'logistics', 'tracking'],
    'suppliers': ['suppliers?', 'vendors?', 'purchases?', 'procurement'],
}

# Intent patterns - map query patterns to table categories
# These use regex patterns to detect user intent from natural language
INTENT_PATTERNS = [
    (r'\b(sales?|sold|revenue|invoices?)\b', 'sales'),
    (r'\b(customers?|clients?|buyers?)\b', 'customers'),
    (r'\b(products?|items?|inventory|stock)\b', 'products'),
    (r'\b(employees?|staff|workers?)\b', 'employees'),
    (r'\b(payments?|transactions?|paid|unpaid|bills?)\b', 'finance'),
    (r'\b(ship|deliver|sent)\b', 'shipping'),
    (r'\b(suppliers?|vendors?|purchases?)\b', 'suppliers'),
]


# ============================================================================
# ALTERNATIVE CONFIGURATIONS (uncomment to use)
# ============================================================================

# Option 1: Disable keywords entirely (use only direct name matching)
# DOMAIN_KEYWORDS = {}
# INTENT_PATTERNS = []

# Option 2: Minimal keywords (only most common terms)
# DOMAIN_KEYWORDS = {
#     'sales': ['sales?', 'orders?'],
#     'customers': ['customers?', 'clients?'],
#     'products': ['products?', 'items?'],
# }

# Option 3: Load from external file (future enhancement)
# import json
# with open('config/keywords.json') as f:
#     DOMAIN_KEYWORDS = json.load(f)