# .env Migration Guide

## 🎯 Quick Migration (2 minutes)

Your `.env` file has been cleaned up! Here's what to do:

---

## Step 1: Backup Your Current .env

```bash
cp .env .env.backup.$(date +%Y%m%d)
```

This creates a timestamped backup just in case.

---

## Step 2: Replace with Updated Version

```bash
mv .env.UPDATED .env
```

This replaces your old `.env` with the cleaned-up version that:
- ✅ Keeps your OpenAI API key
- ✅ Removes old proxy settings
- ✅ Uses new MCP server configuration
- ✅ Matches the current architecture

---

## Step 3: Verify the Configuration

Open `.env` and check:

```bash
# Should see:
OPENAI_API_KEY=sk-proj-AEMx...  # Your actual key ✅
MCP_SERVER_URL=http://10.255.152.48:8000  # Windows IP ✅
MCP_API_KEY=supersecretapikey  # Matches Windows ✅

# Should NOT see:
PROXY_HOST=...  # ❌ Removed
PROXY_PORT=...  # ❌ Removed
DB_MODE=proxy   # ❌ Removed
```

---

## Step 4: Test Your Services

```bash
# Start Mac services
./start_all_services_mac.sh

# Should see:
# ✅ Checking Windows MCP server connectivity...
# ✅ Starting LangGraph service...
# ✅ Starting Web UI...
```

---

## What Changed?

### ❌ Removed (Old Proxy Architecture)
```bash
PROXY_HOST=10.255.152.48
PROXY_PORT=5000
DB_MODE=proxy
PROXY_BASE_URL=http://10.255.152.48:5000
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_API_KEY=dummy-key-for-testing
```

### ✅ Added (New MCP Architecture)
```bash
MCP_SERVER_URL=http://10.255.152.48:8000
MCP_API_KEY=supersecretapikey
LANGGRAPH_API_KEY=supersecretapikey
WEB_UI_HOST=localhost
WEB_UI_PORT=3000
```

### ✅ Kept (Your Important Keys)
```bash
OPENAI_API_KEY=sk-proj-...  # Your actual key preserved!
```

---

## Rollback (If Needed)

If something goes wrong, restore your backup:

```bash
# List backups
ls -la .env.backup.*

# Restore the latest backup
cp .env.backup.20250101 .env  # Use your actual backup filename
```

---

## Optional: Clean Up Subdirectory .env Files

If your services are configured to read from the root `.env`, you can delete the subdirectory files:

```bash
# Check what's there
find . -name ".env" -type f

# Delete subdirectory .env files (optional)
rm chatbot_ui/.env
rm mcp_server/.env
rm synthetic_data_service/.env
```

**Note:** Only do this if you've verified your services load from the root `.env` file!

---

## Need Help?

- **Configuration Guide:** `ENV_CONFIGURATION_GUIDE.md`
- **Cleanup Summary:** `ENV_FILES_CLEANUP_SUMMARY.md`
- **Deployment Guide:** `DEPLOYMENT_GUIDE.md`

---

**You're all set! Your .env configuration is now clean and matches the current architecture.** 🎉