"""SQL Server integration tests; set .env and install the ODBC driver before running."""

from __future__ import annotations

import uuid
import sys
from pathlib import Path

import pyodbc
import pytest

# The project is nested in a larger workspace, so make its root importable for pytest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import get_connection


@pytest.fixture
def connection():
    """Skip only when SQL Server is not configured/reachable in this environment."""
    try:
        conn = get_connection()
    except Exception as exc:  # A missing local database is not a code-test failure.
        pytest.skip(f"SQL Server integration tests need a configured .env and ODBC driver: {exc}")
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def create_customer_and_product(conn: pyodbc.Connection, stock: int) -> tuple[int, int]:
    """Create isolated fixture rows inside the test transaction."""
    cursor = conn.cursor()
    category_id = cursor.execute(
        "SELECT TOP (1) CategoryID FROM dbo.Categories ORDER BY CategoryID"
    ).fetchone()[0]
    token = uuid.uuid4().hex
    customer_id = cursor.execute(
        "INSERT INTO dbo.Customers (FirstName, LastName, Email) "
        "OUTPUT INSERTED.CustomerID VALUES (?, ?, ?);",
        "Test", "Customer", f"test-{token}@example.test",
    ).fetchone()[0]
    product_id = cursor.execute(
        "INSERT INTO dbo.Products (CategoryID, SKU, ProductName, Price) "
        "OUTPUT INSERTED.ProductID VALUES (?, ?, ?, ?);",
        category_id, f"TEST-{token[:20]}", "Integration Test Product", 12.50,
    ).fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Inventory (ProductID, QuantityOnHand, ReorderLevel) VALUES (?, ?, 5);",
        product_id, stock,
    )
    cursor.close()
    return customer_id, product_id


def test_check_constraint_rejects_blank_customer_email(connection: pyodbc.Connection) -> None:
    cursor = connection.cursor()
    with pytest.raises(pyodbc.IntegrityError):
        cursor.execute(
            "INSERT INTO dbo.Customers (FirstName, LastName, Email) VALUES (?, ?, ?);",
            "Bad", "Email", "",
        )
    connection.rollback()
    cursor.close()


def test_place_order_rolls_back_when_stock_is_insufficient(connection: pyodbc.Connection) -> None:
    cursor = connection.cursor()
    before_count = cursor.execute("SELECT COUNT_BIG(*) FROM dbo.Orders;").fetchone()[0]
    customer_id, product_id = create_customer_and_product(connection, stock=0)
    procedure_call = """
    DECLARE @ProductList dbo.OrderProductList;
    INSERT INTO @ProductList (ProductID, Quantity) VALUES (?, ?);
    DECLARE @CreatedOrderID bigint;
    EXEC dbo.usp_PlaceOrder
        @CustomerID = ?,
        @Products = @ProductList,
        @PaymentMethod = N'Test',
        @OrderID = @CreatedOrderID OUTPUT;
    SELECT @CreatedOrderID;
    """
    with pytest.raises(pyodbc.Error):
        cursor.execute(procedure_call, product_id, 1, customer_id)
        # pyodbc surfaces the server-side exception when it advances the result set from
        # the multi-statement batch, not necessarily at the initial EXEC call itself.
        cursor.fetchall()

    # The procedure's CATCH block rolls back its transaction, including its order insert.
    connection.rollback()
    after_count = cursor.execute("SELECT COUNT_BIG(*) FROM dbo.Orders;").fetchone()[0]
    assert after_count == before_count
    cursor.close()


def test_order_item_trigger_reduces_inventory(connection: pyodbc.Connection) -> None:
    customer_id, product_id = create_customer_and_product(connection, stock=10)
    cursor = connection.cursor()
    order_id = cursor.execute(
        "INSERT INTO dbo.Orders (CustomerID) OUTPUT INSERTED.OrderID VALUES (?);",
        customer_id,
    ).fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.OrderItems (OrderID, ProductID, Quantity, UnitPrice) VALUES (?, ?, ?, ?);",
        order_id, product_id, 3, 12.50,
    )
    quantity = cursor.execute(
        "SELECT QuantityOnHand FROM dbo.Inventory WHERE ProductID = ?;", product_id
    ).fetchone()[0]
    assert quantity == 7
    cursor.close()
    connection.rollback()


def test_product_price_trigger_writes_audit_row(connection: pyodbc.Connection) -> None:
    _, product_id = create_customer_and_product(connection, stock=10)
    cursor = connection.cursor()
    cursor.execute("UPDATE dbo.Products SET Price = 14.25 WHERE ProductID = ?;", product_id)
    audit = cursor.execute(
        "SELECT TOP (1) OldPrice, NewPrice FROM dbo.PriceAuditLog "
        "WHERE ProductID = ? ORDER BY PriceAuditID DESC;",
        product_id,
    ).fetchone()
    assert audit is not None
    assert float(audit[0]) == 12.50
    assert float(audit[1]) == 14.25
    cursor.close()
    connection.rollback()
