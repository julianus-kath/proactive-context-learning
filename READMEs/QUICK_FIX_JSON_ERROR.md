# Quick Fix: Agent "Malformed JSON" Error

## 🚨 Problem
Agent responds with error to queries like "Show me our top 5 products by sales":
```
Error parsing database schema due to malformed JSON
```

## ✅ Solution
Fixed dict/object serialization bug in `discovery_tools.py`

The bug: Code was trying to access dict keys as object attributes
```python
# ❌ BROKEN
table = catalog.get_table(schema, name)  # Returns dict
data["schema"] = table.schema             # Can't access dict.key

# ✅ FIXED
data["schema"] = table["schema"]          # Correct dict access
```

## 🔧 What Was Fixed

**File:** `mcp_server/discovery_tools.py`

**Methods Fixed:**
1. `describe_table()` - Lines 638-688
   - Fixed table lookup accessing dicts as objects
   - Fixed column/FK serialization
   
2. `list_relations()` - Lines 786-814
   - Fixed table lookup accessing dicts as objects

**Changes:**
- Changed `table.schema` → `table["schema"]`
- Changed `t.name` → `t["name"]`
- Used `table.get("columns", [])` instead of manually accessing
- All dataclass→dict conversions now happen once in catalog (not repeated)

## 🚀 Deploy

### Option 1: Restart Services (Recommended)

```bash
# Stop current services
# Then restart:

# Option A: Windows MCP Server
cd /path/to/mcp_server
./start_mcp_server_windows.bat

# Option B: Mac Services
./start_all_services_mac.sh
```

### Option 2: Just Reload
If you're using auto-reload:
- The fix is already in `discovery_tools.py`
- Services should pick it up automatically
- Test a query to verify

## ✨ Verify the Fix

### Test Query
```
You: "Show me our top 5 products by sales"
```

### Expected Result
- ✅ No "malformed JSON" error
- ✅ Agent finds products table
- ✅ Query executes
- ✅ Results returned

### Check Logs
```bash
# Should see NO errors like:
# JSONDecodeError
# malformed JSON
# Unexpected character

# Should work fine!
```

## 📋 What Changed

| Before | After |
|--------|-------|
| ❌ Agent errors on table queries | ✅ Queries work perfectly |
| ❌ JSON parse failures | ✅ Clean JSON serialization |
| ❌ describe_table() broken | ✅ Returns proper table details |
| ❌ Malformed dict access | ✅ Proper key-value access |

## 🎯 Expected Behavior After Fix

**Query:** "Show me our top 5 products by sales"

1. Agent searches for "products" table ✅
2. Scout Mode returns ranked matches ✅
3. describe_table() called for details ✅
4. Catalog returns clean dict with columns ✅
5. JSON serializes properly ✅
6. Agent gets data and writes SQL ✅
7. Query executes successfully ✅
8. Results returned to user ✅

**Total time:** <1 second (vs error before)

## 🔍 Technical Details

See `docs/DISCOVERY_TOOLS_JSON_FIX.md` for full technical analysis.

## ⏱️ Time to Deploy

- **To deploy:** 5 minutes
- **To test:** 1 minute
- **Total:** ~10 minutes

## ✅ Post-Deployment Checklist

- [ ] Restarted MCP server (or services auto-reloaded)
- [ ] Tried a query: "Show me our top 5 products by sales"
- [ ] No JSON errors in response
- [ ] Agent works normally
- [ ] Check langgraph.log - no "JSONDecodeError" or "malformed JSON"

---

**Status:** Ready to deploy! 🚀