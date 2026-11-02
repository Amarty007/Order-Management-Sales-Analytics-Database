from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from app.data_import import (
    archive_file_names,
    insert_rows,
    prepare_import,
    read_upload,
    read_workspace_file,
    resolve_workspace_file,
)


def test_prepare_import_maps_columns_and_converts_types() -> None:
    frame = pd.DataFrame(
        [
            {
                "customer_id": 17,
                "first name": "  Ada ",
                "last_name": "Lovelace",
                "email": "ada@example.test",
                "created": "2025-01-02",
            }
        ]
    )
    columns, rows = prepare_import(
        "Customers",
        frame,
        {
            "CustomerID": "customer_id",
            "FirstName": "first name",
            "LastName": "last_name",
            "Email": "email",
            "Phone": None,
            "CreatedAt": "created",
        },
    )

    assert columns == ["CustomerID", "FirstName", "LastName", "Email", "CreatedAt"]
    assert rows[0][0:4] == (17, "Ada", "Lovelace", "ada@example.test")
    assert rows[0][4].isoformat().startswith("2025-01-02")


def test_prepare_import_rejects_missing_required_mapping() -> None:
    with pytest.raises(ValueError, match="Map required fields: Email"):
        prepare_import(
            "Customers",
            pd.DataFrame({"first": ["Ada"], "last": ["Lovelace"]}),
            {
                "FirstName": "first",
                "LastName": "last",
                "Email": None,
            },
        )


def test_prepare_import_rejects_invalid_values_and_reused_source() -> None:
    with pytest.raises(ValueError, match="valid int"):
        prepare_import(
            "Inventory",
            pd.DataFrame({"product": ["not-an-id"], "stock": [10]}),
            {"ProductID": "product", "QuantityOnHand": "stock"},
        )

    with pytest.raises(ValueError, match="only one database field"):
        prepare_import(
            "Customers",
            pd.DataFrame({"name": ["Ada"], "email": ["ada@example.test"]}),
            {
                "FirstName": "name",
                "LastName": "name",
                "Email": "email",
            },
        )


def test_read_upload_supports_utf8_csv() -> None:
    frame = read_upload("customers.csv", "Name,Email\nAda,ada@example.test\n".encode())
    assert frame.to_dict(orient="records") == [
        {"Name": "Ada", "Email": "ada@example.test"}
    ]


def test_read_upload_supports_excel_workbooks() -> None:
    content = BytesIO()
    with pd.ExcelWriter(content, engine="openpyxl") as writer:
        pd.DataFrame({"Name": ["Ada"]}).to_excel(
            writer, sheet_name="Customers", index=False
        )

    frame = read_upload("customers.xlsx", content.getvalue(), "Customers")

    assert frame.to_dict(orient="records") == [{"Name": "Ada"}]


def test_workspace_file_reader_loads_project_file_without_browser_upload(
    tmp_path: Path,
) -> None:
    imports_dir = tmp_path / "data" / "imports"
    imports_dir.mkdir(parents=True)
    source = imports_dir / "orders.csv"
    source.write_text("OrderID,CustomerID\n12,7\n", encoding="utf-8")

    resolved = resolve_workspace_file("data/imports/orders.csv", tmp_path)
    file_name, content = read_workspace_file(resolved, tmp_path)

    assert file_name == "orders.csv"
    assert read_upload(file_name, content).to_dict(orient="records") == [
        {"OrderID": 12, "CustomerID": 7}
    ]


def test_workspace_file_reader_rejects_paths_outside_project(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.csv"
    outside_file.write_text("secret\nvalue\n", encoding="utf-8")

    with pytest.raises(ValueError, match="inside the project workspace"):
        resolve_workspace_file("../outside.csv", tmp_path)


def test_workspace_file_reader_reports_missing_or_unsupported_files(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="File not found"):
        resolve_workspace_file("data/imports/missing.csv", tmp_path)

    unsupported_file = tmp_path / "data" / "imports" / "notes.txt"
    unsupported_file.parent.mkdir(parents=True)
    unsupported_file.write_text("not data", encoding="utf-8")
    with pytest.raises(ValueError, match="Supported file formats"):
        resolve_workspace_file("data/imports/notes.txt", tmp_path)


def test_read_upload_supports_csv_inside_zip_archive() -> None:
    archive_content = BytesIO()
    with ZipFile(archive_content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("export/orders.csv", "OrderID,CustomerID\n12,7\n")
        archive.writestr("notes.txt", "not a data file")

    content = archive_content.getvalue()
    assert archive_file_names("orders.zip", content) == ["export/orders.csv"]

    frame = read_upload(
        "orders.zip",
        content,
        archive_member="export/orders.csv",
    )
    assert frame.to_dict(orient="records") == [{"OrderID": 12, "CustomerID": 7}]


def test_archive_upload_rejects_invalid_zip() -> None:
    with pytest.raises(ValueError, match="ZIP file is invalid"):
        archive_file_names("orders.zip", b"not a ZIP archive")


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.inserted: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.fast_executemany = False
        self.fail_inserts = False

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def executemany(self, statement: str, rows: list[tuple[Any, ...]]) -> None:
        self.inserted.append((statement, rows))
        if self.fail_inserts:
            raise RuntimeError("insert failed")

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_insert_rows_uses_identity_insert_and_commits() -> None:
    connection = FakeConnection()

    inserted = insert_rows(
        connection,  # type: ignore[arg-type]
        "Customers",
        ["CustomerID", "FirstName", "LastName", "Email"],
        [(9, "Ada", "Lovelace", "ada@example.test")],
    )

    assert inserted == 1
    assert connection.fake_cursor.executed == [
        "SET IDENTITY_INSERT [dbo].[Customers] ON;",
        "SET IDENTITY_INSERT [dbo].[Customers] OFF;",
    ]
    assert connection.fake_cursor.inserted[0][0].startswith(
        "INSERT INTO [dbo].[Customers]"
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_insert_rows_rolls_back_and_disables_identity_insert_on_failure() -> None:
    connection = FakeConnection()
    connection.fake_cursor.fail_inserts = True

    with pytest.raises(RuntimeError, match="insert failed"):
        insert_rows(
            connection,  # type: ignore[arg-type]
            "Customers",
            ["CustomerID", "FirstName", "LastName", "Email"],
            [(9, "Ada", "Lovelace", "ada@example.test")],
        )

    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.fake_cursor.executed[-1] == (
        "SET IDENTITY_INSERT [dbo].[Customers] OFF;"
    )
