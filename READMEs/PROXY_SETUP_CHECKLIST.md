# 🚀 Proxy Connection Setup - Quick Checklist

**Goal:** Connect Mac agent to Windows proxy for Phase 2 testing

---

## ✅ Pre-Flight Checklist

### Windows Side (Proxy Server)
- [ ] VPN connected to corporate network
- [ ] `connections.yaml` configured with database credentials
- [ ] Environment variables set (or `.env` file created)
- [ ] TLS certificates generated (if using HTTPS)
- [ ] Firewall allows incoming connections on port 5000
- [ ] `proxy.py` is ready to start

### Mac Side (Agent)
- [ ] Python 3.11+ installed
- [ ] Project dependencies installed
- [ ] `.env` file ready to configure

---

## 🎬 Step-by-Step Setup

### Step 1: Start Windows Proxy ⚡

**On Windows:**
```powershell
cd vpn_config
python proxy.py
```

**Expected output:**
```
✅ Proxy version: 1.5.0
✅ Running on https://0.0.0.0:5000
✅ Loaded 2 connection(s)
```

**Note:** Keep this terminal open!

---

### Step 2: Get Windows IP Address 🌐

**On Windows:**
```cmd
ipconfig
```

**Look for:** IPv4 Address (e.g., `10.255.152.48`)

**Write it down:** `_________________`

---

### Step 3: Configure Mac .env File 📝

**On Mac:**
```bash
# Navigate to project root
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"

# Copy template if needed
cp .env.template .env

# Edit .env file
nano .env
```

**Add these lines:**
```bash
# Database mode
DB_MODE=proxy

# Proxy connection (replace IP with your Windows IP)
PROXY_BASE_URL=https://10.255.152.48:5000
PROXY_API_KEY=your_api_key_from_windows
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_TLS_VERIFY=false
PROXY_TIMEOUT=30
```

**Important:**
- Replace `10.255.152.48` with your Windows IP
- Replace `your_api_key_from_windows` with actual API key
- Replace `corp_sql_erp` with your connection name from `connections.yaml`

---

### Step 4: Test Connection 🧪

**On Mac:**
```bash
python tests/test_proxy_connection.py
```

**Expected result:**
```
✅ All tests passed! Phase 2 is working with real database!
```

---

## 🔧 Quick Troubleshooting

### ❌ Connection Refused
```bash
# Test if port is reachable
nc -zv 10.255.152.48 5000
```
**Fix:** Check Windows firewall, verify proxy is running

---

### ❌ SSL Certificate Error
**Fix:** Set `PROXY_TLS_VERIFY=false` in `.env`

---

### ❌ Authentication Failed
**Fix:** Verify `PROXY_API_KEY` matches Windows configuration

---

### ❌ No Connections Available
**Fix:** Check `connections.yaml` on Windows, verify database credentials

---

## 🎯 What You Need

### From Windows Proxy
1. **IP Address:** `_________________`
2. **Port:** `5000` (default)
3. **API Key:** `_________________`
4. **Connection Name:** `_________________`

### For Mac .env
```bash
PROXY_BASE_URL=https://[WINDOWS_IP]:5000
PROXY_API_KEY=[API_KEY]
PROXY_DEFAULT_CONN=[CONNECTION_NAME]
```

---

## 📋 Test Checklist

Run these tests in order:

- [ ] **Test 1:** Environment Configuration
- [ ] **Test 2:** Proxy Health Check
- [ ] **Test 3:** Simple Query
- [ ] **Test 4:** Schema Discovery
- [ ] **Test 5:** Query Validation
- [ ] **Test 6:** Safe Execution
- [ ] **Test 7:** Table Selection
- [ ] **Test 8:** End-to-End Workflow

**All passing?** ✅ You're ready for Phase 3!

---

## 🚨 Common Issues

| Issue | Quick Fix |
|-------|-----------|
| Can't reach proxy | Check Windows firewall |
| SSL error | Set `PROXY_TLS_VERIFY=false` |
| Auth failed | Verify API key matches |
| No connections | Check `connections.yaml` |
| Timeout | Increase `PROXY_TIMEOUT` |

---

## 📞 Quick Commands

```bash
# Full test suite
python tests/test_proxy_connection.py

# Quick health check
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().health_check())"

# List connections
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().get_available_connections())"

# Test simple query
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().query('SELECT 1'))"
```

---

## ✨ Success Criteria

You're ready to proceed when:

✅ Proxy is running on Windows  
✅ Mac can connect to proxy  
✅ Health check returns `True`  
✅ Connections are listed  
✅ Simple query executes  
✅ Schema discovery works  
✅ All 8 tests pass  

---

## 📚 Documentation

- **Full Guide:** `docs/PROXY_CONNECTION_GUIDE.md`
- **Phase 2 Summary:** `docs/PHASE_2_COMPLETE.md`
- **Architecture:** `adrs/0011-proxy-for-vpn-tunneling.md`

---

**Ready? Let's connect!** 🚀

1. Start Windows proxy
2. Configure Mac .env
3. Run tests
4. Celebrate! 🎉