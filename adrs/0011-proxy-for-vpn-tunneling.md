Perfect 👍 Let’s document this as an **Architecture Decision Record (ADR)**. You can drop this into your repo (e.g., `docs/adr/0001-sql-proxy.md`) and commit `proxy.py` alongside it.

---

# ADR 0011 – Accessing SQL Server from Mac via Windows Proxy

## Context

* Our client runs **Microsoft SQL Server** on-prem, reachable only via the corporate **SonicWall VPN**.
* VPN clients exist only for **Windows** (no Apple Silicon support).
* Development is done on **macOS**, which cannot join the VPN directly.
* Initial attempts with SSH reverse tunnels failed due to SonicWall policy blocking “hairpin” traffic.
* We needed a way for the Mac development environment to **query SQL Server** while only the Windows laptop had VPN access.

---

## Decision

We implemented a **lightweight Flask proxy** (`proxy.py`) running on the Windows laptop (connected to the VPN).

* The proxy exposes a simple **HTTP API** (`/health`, `/query`) on the **Windows LAN IP**.
* The proxy connects to SQL Server using **pyodbc** with the installed **ODBC Driver 17/18 for SQL Server**.
* The Mac queries the proxy over the local LAN (Eduroam, hotspot, or Ethernet) and receives JSON or CSV.
* Only `SELECT` statements are allowed for safety; writes are blocked.
* A `/diag` endpoint provides debugging info (driver picked, sanitized connection string).

This makes SQL Server reachable for development without direct VPN or complex tunneling.

---

## Steps Taken

1. **Verified SQL access on Windows** with `sqlcmd` (`Test-NetConnection` and queries to `192.168.200.16:1433`).
2. **Tested SSH tunnels** → confirmed blocked by SonicWall.
3. **Implemented proxy.py**:

   * Flask app with `/health`, `/query`, `/diag`.
   * Connection string built dynamically from environment variables.
   * JSON (default) and CSV output formats.
   * Simple SQL whitelist: only `SELECT …`.
4. **Installed dependencies** on Windows:

   ```powershell
   py -m pip install flask pyodbc
   ```
5. **Configured environment variables** in PowerShell before running:

   ```powershell
   $env:SQLSERVER_HOST = "192.168.200.16"
   $env:SQLSERVER_PORT = "1433"
   $env:SQLSERVER_DB   = "master"
   $env:SQLSERVER_USER = "SimonM"
   $env:SQLSERVER_PASSWORD = '%Si!Mon!Ma1'
   $env:ODBC_DRIVER = "ODBC Driver 17 for SQL Server"
   $env:SQL_ENCRYPT = "yes"
   $env:SQL_TRUST_CERT = "yes"
   ```
6. **Ran proxy on Windows**:

   ```powershell
   python C:\temp\sqlproxy\proxy.py
   ```
7. **Tested from Mac** (using Windows LAN IP):

   ```bash
   curl "http://10.255.152.48:5000/health"
   curl "http://10.255.152.48:5000/query?sql=SELECT%20name%20FROM%20sys.databases"
   curl "http://10.255.152.48:5000/query?format=csv&sql=SELECT%20TABLE_SCHEMA%2C%20TABLE_NAME%20FROM%20INFORMATION_SCHEMA.TABLES"
   ```
8. **Validated results**: databases and tables returned successfully.

---

## Consequences

* ✅ **Mac can now access SQL Server** indirectly for dev/testing.
* ✅ No changes needed on SonicWall or SQL Server config.
* ⚠️ Requires the Windows laptop to be on, VPN connected, and proxy running.
* ⚠️ Credentials are stored in environment variables → must be handled carefully.
* ⚠️ This setup is not hardened for production; intended for dev only.

---

## Status

**Accepted – Temporary Development Solution**
This pattern will be used until either:

* SonicWall supports Apple Silicon VPN clients, or
* Direct Mac-to-VPN access is granted, or
* IT provisions a secure jump host.

