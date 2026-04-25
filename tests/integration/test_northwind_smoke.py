"""Integration smoke tests against the local Northwind Postgres container.

Gated behind the 'integration' marker. To skip these on a machine without
the Northwind container running:

    pytest -m "not integration"

Assumes the Northwind Docker container is reachable on localhost:55432 with
default postgres/postgres credentials. Override via environment:

    NORTHWIND_HOST, NORTHWIND_PORT, NORTHWIND_DB,
    NORTHWIND_USER, NORTHWIND_PASSWORD
"""
import os

import pytest

pytestmark = pytest.mark.integration

_CONN_KWARGS = {
    "host": os.getenv("NORTHWIND_HOST", "localhost"),
    "port": int(os.getenv("NORTHWIND_PORT", "55432")),
    "dbname": os.getenv("NORTHWIND_DB", "northwind"),
    "user": os.getenv("NORTHWIND_USER", "postgres"),
    "password": os.getenv("NORTHWIND_PASSWORD", "postgres"),
}

# Canonical Northwind public-schema tables. If any are missing, the
# benchmark ground truth is unreliable.
EXPECTED_TABLES = {
    "categories",
    "customers",
    "employees",
    "order_details",
    "orders",
    "products",
    "shippers",
    "suppliers",
}


@pytest.fixture(scope="module")
def conn():
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed")
    try:
        c = psycopg2.connect(**_CONN_KWARGS)
    except Exception as exc:
        pytest.skip(f"Northwind Postgres not reachable: {exc}")
    yield c
    c.close()


def test_connection_alive(conn):
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone()[0] == 1


def test_canonical_tables_present(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public'"
    )
    actual = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_TABLES - actual
    assert not missing, f"Missing Northwind tables: {missing}"


def test_customers_has_rows(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    assert cur.fetchone()[0] > 0


def test_orders_has_rows(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    assert cur.fetchone()[0] > 0


def test_order_details_join_is_sound(conn):
    """Sanity: order_details → orders foreign key is populated and traversable."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM order_details od "
        "JOIN orders o ON od.order_id = o.order_id"
    )
    join_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM order_details")
    od_count = cur.fetchone()[0]
    assert join_count == od_count, (
        f"order_details → orders join lost rows: {od_count - join_count} orphan(s)"
    )
