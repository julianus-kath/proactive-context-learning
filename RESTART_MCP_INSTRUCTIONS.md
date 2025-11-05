# 🔄 MCP Server Restart Instructions

## What Changed

We've consolidated `scout_mode.py` and `scout_runner.py` into a single, powerful system that:

✅ **Accurate row counts** from database partition stats  
✅ **Semantic search** with fuzzy matching for German names  
✅ **Intent-aware ranking** (customer/product/revenue)  
✅ **Archive table penalties** (-0.7 score for junk tables)  
✅ **Master table boosts** (+0.6 for customer tables in COUNT queries)  

## 🚀 How to Apply the Fix

### On Windows (Where MCP Server Runs)

1. **Stop the current MCP server** (if running):
   - Press `Ctrl+C` in the terminal where it's running

2. **Restart using the updated script**:
   ```bash
   cd C:\Users\unisg\Desktop\pcl_julianus\proactive-context-learning\vpn_config
   start_mcp_server_windows.bat
   ```

3. **Watch for the rebuild**:
   - You'll see: `🔄 Forcing Fresh Catalog Rebuild`
   - It will delete the old catalog
   - Rebuild will take 30-60 seconds
   - You'll see: `✅ Catalog build completed in X.Xs, 943 tables, Y views`

## 📊 What to Expect After Restart

### Before (OLD Catalog):
```
Search "customers" → BSDMSArchivEKBelegarten (11 rows, WRONG!)
Search "KHKAdressen" → vewBCSPjmObjektliste (project list, WRONG!)
All tables: estimated_rows = 0 (WRONG!)
```

### After (NEW Catalog):
```
Search "customers" → KHKAdressen (419 rows, CORRECT! ✅)
Search "KHKAdressen" → KHKAdressen (exact match, CORRECT! ✅)
All tables: accurate row counts from sys.dm_db_partition_stats ✅
Archive tables: heavily penalized in ranking ✅
```

## 🧪 Test It

After restarting, test with:

```bash
python debug_orchestrator_surgical.py "How many customers do we have?"
```

**Expected Result:**
```
✅ SQL: SELECT COUNT(*) FROM KHKAdressen
✅ Result: 419 customers
✅ Source: KHKAdressen (customer master table)
```

**NOT:**
```
❌ SQL: SELECT COUNT(*) FROM BSDMSArchivEKBelegarten
❌ Result: 11 (archive table - WRONG!)
```

## 🔍 How to Verify the Fix

### 1. Check MCP Server Logs
After startup, you should see:
```
🔍 Scout search 'customers' found 5 results, top score: 1.650
   1. KHKAdressen (score: 1.650, reasons: Exact match, Customer master boost, 419 rows)
   2. ... (other tables with lower scores)
```

### 2. Check Health Endpoint
```bash
curl http://localhost:8000/health
```

Should show:
```json
{
  "catalog_exists": true,
  "catalog_valid": true,
  "catalog_age_hours": 0.0,
  "tables_count": 943,
  "scout_running": true
}
```

### 3. Run Canonical Queries

**Customer Count:**
```bash
python debug_orchestrator_surgical.py "How many customers do we have?"
```
✅ Should use: `KHKAdressen` (419 rows)  
❌ Should NOT use: Archive tables

**Product Count:**
```bash
python debug_orchestrator_surgical.py "How many products do we own?"
```
✅ Should use: `Artikelstamm` or similar product master table  
❌ Should NOT use: `vewBCSPjmObjektliste` (project list)

**Revenue Query:**
```bash
python debug_orchestrator_surgical.py "Wer sind unsere Top 5 Kunden nach Gesamtumsatz?"
```
✅ Should use: Sales transaction tables + customer dimension  
❌ Should NOT use: Archive or config tables

## 🛠️ Troubleshooting

### If catalog rebuild fails:
1. Check database connection (MCP server needs VPN/network access)
2. Check `.env` file has correct `DB_*` variables
3. Look for errors in startup logs

### If still returning wrong tables:
1. Check MCP server logs for semantic search results
2. Verify catalog was actually rebuilt (check timestamp)
3. Try manually deleting: `data/catalog/catalog.json.gz`
4. Restart again

### If "0 rows" still appears:
This means the catalog builder couldn't access `sys.dm_db_partition_stats`.
- Check database permissions
- Ensure using MSSQL 2017+ (required for partition stats)

## 📁 Files Changed

1. **`mcp_server/scout_runner.py`** - Consolidated semantic search
2. **`mcp_server/tools.py`** - Wired to use `ScoutRunner.search()`
3. **`vpn_config/start_mcp_server_windows.bat`** - Auto-delete old catalog
4. **`scout_mode.py`** - Can be deprecated (functionality moved to scout_runner)

## 🎯 Success Criteria

You'll know it's working when:
1. ✅ Customer count query returns 419 (using KHKAdressen)
2. ✅ Archive tables are NOT selected for business queries
3. ✅ MCP search for "customers" returns KHKAdressen as #1 result
4. ✅ All canonical queries return sensible results

---

**If you see these results, the fix is complete! 🎉**

