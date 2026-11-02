"""Streamlit dashboard for the order-management SQL database."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd
import pyodbc
import streamlit as st

# Allow the documented repository-root launch command to resolve the app package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import get_connection
from app.data_import import (
    TABLE_COLUMNS,
    excel_sheet_names,
    insert_rows,
    prepare_import,
    read_upload,
)
from app.queries import (
    CUSTOMER_HISTORY_SQL,
    KPI_SQL,
    LOW_STOCK_SQL,
    MONTHLY_REVENUE_SQL,
    TOP_PRODUCTS_SQL,
)

st.set_page_config(page_title="Order Management Dashboard", layout="wide")

MAX_ARCHIVE_MEMBER_SIZE = 512 * 1024 * 1024
IMPORT_FILE_EXTENSIONS = (".csv", ".xlsx", ".xlsm")
MAX_IMPORT_FILE_SIZE = 512 * 1024 * 1024


def resolve_workspace_file(path_text: str, project_root: Path) -> Path:
    """Allow imports only from files inside the checked-out project workspace."""
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
    """Read a validated file directly from the server workspace."""
    approved_path = resolve_workspace_file(str(path), project_root)
    return approved_path.name, approved_path.read_bytes()


def archive_file_names(file_name: str, content: bytes) -> list[str]:
    """List supported data files in a ZIP upload without extracting to disk."""
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


def resolve_uploaded_data(
    file_name: str,
    content: bytes,
    archive_member: str | None = None,
) -> tuple[str, bytes]:
    """Return the selected upload content for both current and older import helpers."""
    if not file_name.lower().endswith(".zip"):
        if archive_member is not None:
            raise ValueError("A ZIP member was selected for a non-ZIP upload.")
        return file_name, content
    if archive_member is None:
        raise ValueError("Select a data file from the ZIP archive.")

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


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def cached_workspace_file(
    path_text: str, modified_ns: int, file_size: int
) -> tuple[str, bytes]:
    del modified_ns, file_size
    return read_workspace_file(Path(path_text), PROJECT_ROOT)


st.title("Order Management & Sales Analytics")


def get_db() -> object:
    """Return a fresh, health-checked connection on every Streamlit rerun."""
    return get_connection()


try:
    conn = get_db()
    kpis = pd.read_sql_query(KPI_SQL, conn)
    monthly = pd.read_sql_query(MONTHLY_REVENUE_SQL, conn)
    top_products = pd.read_sql_query(TOP_PRODUCTS_SQL, conn)
    low_stock = pd.read_sql_query(LOW_STOCK_SQL, conn)
except Exception as exc:  # pragma: no cover - UI fallback for local configuration
    st.warning(
        "SQL Server connection failed after automatic retries. Check DB_SERVER in "
        "the project .env file and confirm SQL Server is running and reachable."
    )
    st.code(str(exc))
    st.stop()


col1, col2, col3 = st.columns(3)
with col1:
    total_revenue = float(kpis.iloc[0]["TotalRevenue"]) if not kpis.empty else 0.0
    st.metric("Total Revenue", f"${total_revenue:,.2f}")
with col2:
    total_orders = int(kpis.iloc[0]["TotalOrders"]) if not kpis.empty else 0
    st.metric("Orders", f"{total_orders:,}")
with col3:
    total_customers = int(kpis.iloc[0]["TotalCustomers"]) if not kpis.empty else 0
    st.metric("Customers", f"{total_customers:,}")

st.subheader("Monthly revenue")
if not monthly.empty:
    st.line_chart(monthly.set_index("SalesMonth")["Revenue"])
else:
    st.info("No monthly revenue data available.")

left, right = st.columns([1.5, 1])
with left:
    st.subheader("Top products by revenue")
    if not top_products.empty:
        st.dataframe(top_products, width="stretch")
    else:
        st.info("No sales data yet.")

with right:
    st.subheader("Low-stock products")
    if not low_stock.empty:
        st.dataframe(low_stock, width="stretch")
    else:
        st.info("All products are above reorder threshold.")

st.subheader("Customer history lookup")
customer_id = st.number_input("Customer ID", min_value=1, step=1, value=1)
if st.button("Load customer history"):
    try:
        history = pd.read_sql_query(CUSTOMER_HISTORY_SQL, conn, params=(customer_id,))
        if history.empty:
            st.info(f"No orders found for customer {customer_id}.")
        else:
            st.dataframe(history, width="stretch")
    except Exception as exc:  # pragma: no cover - execution-time fallback
        st.error(f"Could not load customer history: {exc}")

with st.expander("Import your real CSV / Excel data"):
    st.warning(
        "Imports add rows to the selected table; they do not replace existing data. "
        "Import linked tables in dependency order and use matching numeric IDs."
    )
    table_name = st.selectbox("Database table", list(TABLE_COLUMNS))
    required_columns = [
        column.name for column in TABLE_COLUMNS[table_name] if column.required
    ]
    st.caption(
        "Required fields: "
        + ", ".join(required_columns)
        + ". Optional fields can be left unmapped to use database defaults."
    )
    st.info(
        "Upload a file below, or use the workspace option for large files if your "
        "browser or proxy rejects the upload."
    )
    uploaded_file = st.file_uploader(
        "Choose a CSV, Excel, or ZIP file",
        type=["csv", "xlsx", "xlsm", "zip"],
        key="real_data_file_upload",
    )
    with st.form("workspace_import_file_form"):
        workspace_path_text = st.text_input(
            "Project-relative file path",
            value="data/imports/talabat_orders.csv",
            key="workspace_import_file_path_v2",
            help=(
                "This path is relative to the order-management-sql project folder. "
                "Add the file to order-management-sql/data/imports/ first, then edit "
                "this path if its filename is different."
            ),
        )
        load_workspace_file = st.form_submit_button("Load workspace file")

    if load_workspace_file:
        st.session_state.pop("real_data_workspace_path", None)
        try:
            resolved_path = resolve_workspace_file(workspace_path_text, PROJECT_ROOT)
            st.session_state["real_data_workspace_path"] = str(resolved_path)
        except (OSError, ValueError) as exc:
            st.error(f"Could not load workspace file: {exc}")

    file_name: str | None = None
    file_content: bytes | None = None
    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_content = uploaded_file.getvalue()
    else:
        active_workspace_path = st.session_state.get("real_data_workspace_path")
        if active_workspace_path:
            try:
                resolved_path = resolve_workspace_file(
                    active_workspace_path, PROJECT_ROOT
                )
                file_name, file_content = cached_workspace_file(
                    str(resolved_path),
                    resolved_path.stat().st_mtime_ns,
                    resolved_path.stat().st_size,
                )
                st.caption(
                    "Loaded from workspace: "
                    f"{resolved_path.relative_to(PROJECT_ROOT).as_posix()}"
                )
            except (OSError, ValueError) as exc:
                st.error(f"Could not read workspace file: {exc}")

    if file_name is not None and file_content is not None:
        try:
            archive_members = archive_file_names(file_name, file_content)
            archive_member = None
            if file_name.lower().endswith(".zip"):
                if not archive_members:
                    raise ValueError(
                        "The ZIP archive must contain at least one CSV, XLSX, or XLSM file."
                    )
                archive_member = st.selectbox(
                    "Data file in ZIP archive",
                    archive_members,
                    key="real_data_archive_member",
                )
            data_file_name, data_file_content = resolve_uploaded_data(
                file_name,
                file_content,
                archive_member,
            )
            sheet_names = excel_sheet_names(data_file_name, data_file_content)
            sheet_name = None
            if sheet_names:
                sheet_name = st.selectbox("Worksheet", sheet_names)
            import_frame = read_upload(
                data_file_name,
                data_file_content,
                sheet_name,
            )
        except (ValueError, ImportError, OSError) as exc:
            st.error(f"Could not read the data file: {exc}")
            import_frame = None

        if import_frame is not None:
            if import_frame.empty or len(import_frame.columns) == 0:
                st.error("The selected file has no columns or data rows.")
            else:
                st.dataframe(import_frame.head(10), width="stretch")
                source_columns = [str(column) for column in import_frame.columns]
                mapping_options = ["(skip)"] + source_columns

                def suggested_source(target: str) -> str:
                    normalize = lambda value: "".join(
                        character.lower() for character in value if character.isalnum()
                    )
                    target_key = normalize(target)
                    return next(
                        (
                            source
                            for source in source_columns
                            if normalize(source) == target_key
                        ),
                        "(skip)",
                    )

                source_by_target: dict[str, str | None] = {}
                st.write("Match your file columns to the database fields:")
                for column in TABLE_COLUMNS[table_name]:
                    choice = st.selectbox(
                        f"{column.name}{' *' if column.required else ''}",
                        mapping_options,
                        index=mapping_options.index(suggested_source(column.name)),
                        key=f"import_{table_name}_{column.name}",
                    )
                    source_by_target[column.name] = (
                        None if choice == "(skip)" else choice
                    )

                if st.button("Validate and import", type="primary"):
                    try:
                        mapped_columns, import_rows = prepare_import(
                            table_name, import_frame, source_by_target
                        )
                        imported_count = insert_rows(
                            conn, table_name, mapped_columns, import_rows
                        )
                    except (ValueError, pyodbc.Error) as exc:
                        st.error(
                            "Import failed and the database transaction was rolled back: "
                            f"{exc}"
                        )
                    else:
                        st.success(
                            f"Imported {imported_count:,} rows into dbo.{table_name}."
                        )
                        st.rerun()

conn.close()
