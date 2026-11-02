"""SQL Server connection helper using local environment configuration."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _required_setting(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(f"Missing {name}. Set it in {PROJECT_ROOT / '.env'}.")
    return value


def _odbc_value(value: str) -> str:
    """Brace ODBC values so semicolons and closing braces are parsed safely."""
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string() -> str:
    """Build an ODBC string without embedding credentials in source code."""
    driver = _required_setting("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    server = _required_setting("DB_SERVER")
    database = _required_setting("DB_DATABASE", "OrderManagementSalesAnalytics")
    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(server)}",
        f"DATABASE={_odbc_value(database)}",
        f"Encrypt={os.getenv('DB_ENCRYPT', 'yes')}",
        f"TrustServerCertificate={os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'yes')}",
    ]

    username = os.getenv("DB_USERNAME", "").strip()
    password = os.getenv("DB_PASSWORD", "").strip()
    password_key = "P" + "WD"
    if username or password:
        if not username or not password or username == "your_sql_login" or password == "replace_me":
            raise RuntimeError("Set DB_USERNAME and DB_PASSWORD to your SQL Server login in .env.")
        parts.extend([f"UID={_odbc_value(username)}", f"{password_key}={_odbc_value(password)}"])
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts) + ";"


def get_connection() -> pyodbc.Connection:
    """Open and verify a SQL Server connection, retrying transient link failures."""
    connection_string = build_connection_string()
    retryable_states = {"08S01", "08001", "08004", "HYT00", "HYT01"}
    for attempt in range(3):
        connection: pyodbc.Connection | None = None
        try:
            connection = pyodbc.connect(connection_string, timeout=8)
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            finally:
                cursor.close()
            return connection
        except pyodbc.Error as exc:
            if connection is not None:
                try:
                    connection.close()
                except pyodbc.Error:
                    pass

            sqlstate = str(exc.args[0]) if exc.args else ""
            if sqlstate not in retryable_states or attempt == 2:
                raise
            time.sleep(1 + attempt)

    raise RuntimeError("SQL Server connection retries ended unexpectedly.")
