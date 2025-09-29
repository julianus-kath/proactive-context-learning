# proxy.py  — tiny read-only SQL-over-HTTP proxy

# Run on Windows (VPN-connected). Your Mac calls http://<windows_lan_ip>:5000/query?sql=...

# Security: ONLY SELECT is allowed. Do NOT expose outside your LAN.

from flask import Flask, request, jsonify, Response, abort

import os

import pyodbc

import csv

import io

import re

app = Flask(__name__)

# --- Configuration via environment variables (with safe defaults) ---

# --- Configuration via environment variables (with safe defaults) ---

SQL_HOST = os.getenv("SQLSERVER_HOST", "192.168.200.16")

SQL_PORT = os.getenv("SQLSERVER_PORT", "1433")

SQL_DB = os.getenv("SQLSERVER_DB", "master")

SQL_USER = os.getenv("SQLSERVER_USER", "SimonM")

SQL_PASS = os.getenv("SQLSERVER_PASSWORD", "")

# We will auto-detect an installed driver.

PREFERRED_DRIVERS = [

    os.getenv("ODBC_DRIVER"),  # user-specified (no braces)

    "ODBC Driver 18 for SQL Server",

    "ODBC Driver 17 for SQL Server",

    "SQL Server",

]


def pick_driver():
    try:

        installed = [d.strip("{}") for d in pyodbc.drivers()]  # strip braces from names returned by pyodbc

    except Exception:

        installed = []

    for name in PREFERRED_DRIVERS:

        if not name:
            continue

        n = name.strip()

        n = n.strip("{}")  # remove braces if user put them

        if n in installed:
            return n, installed

    return (installed[0] if installed else None), installed


ODBC_DRIVER, _DRIVERS = pick_driver()

if not ODBC_DRIVER:
    raise RuntimeError(
        "No suitable SQL Server ODBC driver found. Install 'ODBC Driver 18 for SQL Server' or 'ODBC Driver 17 for SQL Server'.")


# Build connection string robustly (we insert braces exactly once around the driver)

def build_conn_str():
    parts = {

        "DRIVER": "{" + ODBC_DRIVER + "}",  # ONE pair of braces

        "SERVER": f"{SQL_HOST},{SQL_PORT}",

        "DATABASE": SQL_DB,

        "UID": SQL_USER,

        "PWD": SQL_PASS,

        "Encrypt": os.getenv("SQL_ENCRYPT", "yes"),

        "TrustServerCertificate": os.getenv("SQL_TRUST_CERT", "yes"),

    }

    return ";".join(f"{k}={v}" for k, v in parts.items()) + ";"


CONN_STR = build_conn_str()


@app.route("/diag")
def diag():
    redacted = CONN_STR.replace(SQL_PASS, "*****") if SQL_PASS else CONN_STR

    return jsonify({

        "driver_picked": ODBC_DRIVER,

        "drivers_installed": _DRIVERS,

        "conn_str_preview": redacted,

        "host": SQL_HOST, "port": SQL_PORT, "db": SQL_DB

    })


# Only allow simple SELECT statements (block writes / DDL). Very basic guard:

SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)


def run_select(sql: str):
    # Open a short-lived connection per request (simple + safe)

    with pyodbc.connect(CONN_STR, autocommit=True) as conn:
        cur = conn.cursor()

        cur.execute(sql)

        # Some SELECTs (e.g. SET statements) might not return rows

        cols = [c[0] for c in cur.description] if cur.description else []

        rows = cur.fetchall() if cols else []

    return cols, rows


@app.route("/health")
def health():
    return jsonify({"ok": True, "db_host": SQL_HOST, "db": SQL_DB})


@app.route("/query")
def query():
    sql = request.args.get("sql")

    if not sql:
        abort(400, "Missing 'sql' query parameter.")

    if not SELECT_ONLY.match(sql):
        abort(403, "Only SELECT queries are allowed.")

    fmt = (request.args.get("format") or "json").lower().strip()

    try:

        cols, rows = run_select(sql)

    except pyodbc.Error as e:

        # Return a terse error (avoid leaking internals)

        abort(400, f"Database error: {str(e)}")

    if fmt == "csv":

        sio = io.StringIO()

        w = csv.writer(sio)

        if cols:

            w.writerow(cols)

            for r in rows:
                w.writerow([str(x) if x is not None else "" for x in r])

        return Response(sio.getvalue(), mimetype="text/csv")

    # default: JSON

    data = []

    if cols:

        for r in rows:
            data.append({cols[i]: (str(r[i]) if r[i] is not None else None) for i in range(len(cols))})

    return jsonify({"columns": cols, "rows": data})


if __name__ == "__main__":
    # Listen on all interfaces so your Mac can reach it over LAN

    port = int(os.getenv("PORT", "5000"))

    app.run(host="0.0.0.0", port=port)

