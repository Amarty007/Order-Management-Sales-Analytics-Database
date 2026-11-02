"""Validated CSV/Excel imports into the project's SQL Server tables."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

import pandas as pd
import pyodbc

MAX_ARCHIVE_MEMBER_SIZE = 512 * 1024 * 1024
IMPORT_FILE_EXTENSIONS = (".csv", ".xlsx", ".xlsm")
MAX_IMPORT_FILE_SIZE = 512 * 1024 * 1024


@dataclass(frozen=True)
class ImportColumn:
    name: str
    kind: str
    required: bool = False
    identity: bool = False


TABLE_COLUMNS: dict[str, tuple[ImportColumn, ...]] = {
    "Categories": (
        ImportColumn("CategoryID", "int", identity=True),
        ImportColumn("CategoryName", "str", required=True),
        ImportColumn("Description", "str"),
        ImportColumn("IsActive", "bool"),
    ),
    "Customers": (
        ImportColumn("CustomerID", "int", identity=True),
        ImportColumn("FirstName", "str", required=True),
        ImportColumn("LastName", "str", required=True),
        ImportColumn("Email", "str", required=True),
        ImportColumn("Phone", "str"),
        ImportColumn("CreatedAt", "datetime"),
    ),
    "Products": (
        ImportColumn("ProductID", "int", identity=True),
        ImportColumn("CategoryID", "int", required=True),
        ImportColumn("SKU", "str", required=True),
        ImportColumn("ProductName", "str", required=True),
        ImportColumn("Price", "decimal", required=True),
        ImportColumn("IsActive", "bool"),
        ImportColumn("CreatedAt", "datetime"),
    ),
    "Inventory": (
        ImportColumn("ProductID", "int", required=True),
        ImportColumn("QuantityOnHand", "int", required=True),
        ImportColumn("ReorderLevel", "int"),
        ImportColumn("LastUpdatedAt", "datetime"),
    ),
    "Orders": (
        ImportColumn("OrderID", "int", identity=True),
        ImportColumn("CustomerID", "int", required=True),
        ImportColumn("OrderDate", "datetime"),
        ImportColumn("OrderStatus", "str"),
    ),
    "OrderItems": (
        ImportColumn("OrderItemID", "int", identity=True),
        ImportColumn("OrderID", "int", required=True),
        ImportColumn("ProductID", "int", required=True),
        ImportColumn("Quantity", "int", required=True),
        ImportColumn("UnitPrice", "decimal", required=True),
    ),
    "Payments": (
        ImportColumn("PaymentID", "int", identity=True),
        ImportColumn("OrderID", "int", required=True),
        ImportColumn("PaymentMethod", "str", required=True),
        ImportColumn("Amount", "decimal", required=True),
        ImportColumn("PaymentStatus", "str"),
        ImportColumn("TransactionReference", "str"),
        ImportColumn("PaidAt", "datetime"),
        ImportColumn("CreatedAt", "datetime"),
    ),
}


def resolve_workspace_file(path_text: str, project_root: Path) -> Path:
    """Resolve a data file only when it is inside the workspace project directory."""
    if not path_text.strip():
        raise ValueError("Enter the path to a file inside the project workspace.")

    root = project_root.resolve()
    candidate = Path(path_text.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    if not candidate.is_relative_to(root):
        raise ValueError("For safety, import files must be inside the project workspace.")
    if not candidate.is_file():
        raise ValueError(f"File not found: {candidate.relative_to(root).as_posix()}.")
    if candidate.suffix.lower() not in (*IMPORT_FILE_EXTENSIONS, ".zip"):
        raise ValueError("Supported file formats are CSV, XLSX, XLSM, and ZIP.")
    if candidate.stat().st_size > MAX_IMPORT_FILE_SIZE:
        raise ValueError("The file is larger than the 512 MB import limit.")
    return candidate


def read_workspace_file(path: Path, project_root: Path) -> tuple[str, bytes]:
    """Read an approved project-workspace file without sending it through the browser."""
    approved_path = resolve_workspace_file(str(path), project_root)
    return approved_path.name, approved_path.read_bytes()


def archive_file_names(file_name: str, content: bytes) -> list[str]:
    """List supported data files in a ZIP upload without extracting them to disk."""
    if not file_name.lower().endswith(".zip"):
        return []
    try:
        with ZipFile(BytesIO(content)) as archive:
            return [
                info.filename
                for info in archive.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith(IMPORT_FILE_EXTENSIONS)
            ]
    except BadZipFile as exc:
        raise ValueError("The uploaded ZIP file is invalid or incomplete.") from exc


def _resolve_upload(
    file_name: str,
    content: bytes,
    archive_member: str | None,
) -> tuple[str, bytes]:
    if not file_name.lower().endswith(".zip"):
        if archive_member is not None:
            raise ValueError("A ZIP member was selected for a non-ZIP upload.")
        return file_name, content

    if archive_member is None:
        raise ValueError("Select a CSV or Excel file from the ZIP archive.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            try:
                member = archive.getinfo(archive_member)
            except KeyError as exc:
                raise ValueError("The selected file was not found in the ZIP archive.") from exc
            if member.is_dir() or not member.filename.lower().endswith(
                IMPORT_FILE_EXTENSIONS
            ):
                raise ValueError("ZIP archives may contain CSV, XLSX, or XLSM files.")
            if member.file_size > MAX_ARCHIVE_MEMBER_SIZE:
                raise ValueError(
                    "The uncompressed file is larger than the 512 MB import limit."
                )
            return member.filename, archive.read(member)
    except BadZipFile as exc:
        raise ValueError("The uploaded ZIP file is invalid or incomplete.") from exc


def excel_sheet_names(
    file_name: str,
    content: bytes,
    archive_member: str | None = None,
) -> list[str]:
    """Return workbook sheet names for Excel uploads."""
    resolved_name, resolved_content = _resolve_upload(
        file_name, content, archive_member
    )
    if not resolved_name.lower().endswith((".xlsx", ".xlsm")):
        return []
    workbook = pd.ExcelFile(BytesIO(resolved_content), engine="openpyxl")
    return workbook.sheet_names


def read_upload(
    file_name: str,
    content: bytes,
    sheet_name: str | None = None,
    archive_member: str | None = None,
) -> pd.DataFrame:
    """Read a CSV or Excel sheet without modifying the uploaded file."""
    resolved_name, resolved_content = _resolve_upload(
        file_name, content, archive_member
    )
    suffix = resolved_name.lower().rsplit(".", 1)[-1] if "." in resolved_name else ""
    if suffix == "csv":
        return pd.read_csv(BytesIO(resolved_content), encoding="utf-8-sig")
    if suffix in {"xlsx", "xlsm"}:
        if sheet_name is None:
            raise ValueError("Select a worksheet from the uploaded Excel workbook.")
        return pd.read_excel(
            BytesIO(resolved_content), sheet_name=sheet_name, engine="openpyxl"
        )
    raise ValueError("Supported file formats are CSV, XLSX, XLSM, and ZIP archives.")


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _convert_value(value: Any, column: ImportColumn, row_number: int) -> Any:
    if _missing(value):
        if column.required:
            raise ValueError(f"Row {row_number}: {column.name} is required.")
        return None

    try:
        if column.kind == "str":
            converted = str(value).strip()
            if column.required and not converted:
                raise ValueError(f"Row {row_number}: {column.name} cannot be blank.")
            return converted
        if column.kind == "int":
            number = Decimal(str(value).strip())
            if number != number.to_integral_value():
                raise ValueError
            return int(number)
        if column.kind == "decimal":
            return Decimal(str(value).strip().replace(",", ""))
        if column.kind == "bool":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"1", "true", "yes", "active"}:
                return True
            if normalized in {"0", "false", "no", "inactive"}:
                return False
            raise ValueError
        if column.kind == "datetime":
            timestamp = pd.to_datetime(value, errors="raise")
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert("UTC").tz_localize(None)
            return timestamp.to_pydatetime()
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"Row {row_number}: {column.name} must be a valid {column.kind} value; got {value!r}."
        ) from exc

    raise ValueError(f"Unsupported import type {column.kind!r} for {column.name}.")


def prepare_import(
    table_name: str,
    frame: pd.DataFrame,
    source_by_target: dict[str, str | None],
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Apply the selected column mapping and validate required values and types."""
    if table_name not in TABLE_COLUMNS:
        raise ValueError(f"Unsupported target table: {table_name}.")

    columns = TABLE_COLUMNS[table_name]
    selected = [(column, source_by_target.get(column.name)) for column in columns]
    selected = [(column, source) for column, source in selected if source is not None]
    if not selected:
        raise ValueError("Map at least one source column before importing.")

    missing_required = [
        column.name
        for column in columns
        if column.required and source_by_target.get(column.name) is None
    ]
    if missing_required:
        raise ValueError("Map required fields: " + ", ".join(missing_required) + ".")

    sources = [source for _, source in selected]
    if len(sources) != len(set(sources)):
        raise ValueError("Each source column can be mapped to only one database field.")
    missing_sources = [source for source in sources if source not in frame.columns]
    if missing_sources:
        raise ValueError("Source columns not found: " + ", ".join(missing_sources) + ".")

    data = frame.dropna(how="all").reset_index(drop=True)
    rows = [
        tuple(
            _convert_value(data.iloc[index][source], column, int(index) + 2)
            for column, source in selected
        )
        for index in range(len(data))
    ]
    if not rows:
        raise ValueError("The uploaded file has no data rows.")
    return [column.name for column, _ in selected], rows


def insert_rows(
    connection: pyodbc.Connection,
    table_name: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
) -> int:
    """Insert a validated batch atomically; table/column names come from the whitelist."""
    if table_name not in TABLE_COLUMNS:
        raise ValueError(f"Unsupported target table: {table_name}.")
    allowed_columns = {column.name: column for column in TABLE_COLUMNS[table_name]}
    if not columns or any(column not in allowed_columns for column in columns):
        raise ValueError("Import contains a column that is not allowed for this table.")
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("Import rows do not match the selected columns.")

    table_sql = f"[dbo].[{table_name}]"
    columns_sql = ", ".join(f"[{column}]" for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {table_sql} ({columns_sql}) VALUES ({placeholders});"
    identity_column = next(
        (column for column in columns if allowed_columns[column].identity), None
    )
    cursor = connection.cursor()
    identity_insert_enabled = False
    try:
        if identity_column is not None:
            cursor.execute(f"SET IDENTITY_INSERT {table_sql} ON;")
            identity_insert_enabled = True

        cursor.fast_executemany = True
        for start in range(0, len(rows), 1000):
            cursor.executemany(insert_sql, rows[start : start + 1000])

        if identity_insert_enabled:
            cursor.execute(f"SET IDENTITY_INSERT {table_sql} OFF;")
            identity_insert_enabled = False
        connection.commit()
        return len(rows)
    except Exception:
        connection.rollback()
        if identity_insert_enabled:
            cursor.execute(f"SET IDENTITY_INSERT {table_sql} OFF;")
        raise
    finally:
        cursor.close()
