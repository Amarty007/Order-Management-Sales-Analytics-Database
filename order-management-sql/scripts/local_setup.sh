#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="order-management-sql-db"
SA_PASSWORD="${MSSQL_SA_PASSWORD:?Set MSSQL_SA_PASSWORD before running this script.}"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
CSV_DIR="$ROOT/data/csv"
CONTAINER_CSV="/var/opt/mssql/data/project_csv"
CONTAINER_SQL="/var/opt/mssql/data/project_sql"
SQLCMD_ARGS=(-S localhost -U sa -P "$SA_PASSWORD" -C -b)

if ! docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  docker run -e 'ACCEPT_EULA=Y' \
    -e "MSSQL_SA_PASSWORD=${SA_PASSWORD}" \
    -p 1433:1433 \
    --restart unless-stopped \
    --name "$CONTAINER_NAME" \
    -d mcr.microsoft.com/mssql/server:2022-latest
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  docker start "$CONTAINER_NAME"
fi

for attempt in {1..180}; do
  if docker exec "$CONTAINER_NAME" "$SQLCMD" "${SQLCMD_ARGS[@]}" -Q "SELECT 1;" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 180 ]]; then
    printf 'SQL Server did not become ready in time. Recent container logs follow:\n' >&2
    docker logs --tail 40 "$CONTAINER_NAME" >&2
    exit 1
  fi
  sleep 2
done

python "$ROOT/data/generate_data.py" --orders 100000 --customers 5000 --products 500 --seed 20261005 --output-dir "$CSV_DIR"

docker exec "$CONTAINER_NAME" mkdir -p "$CONTAINER_CSV"
docker cp "$CSV_DIR/." "$CONTAINER_NAME:$CONTAINER_CSV/"
docker exec "$CONTAINER_NAME" mkdir -p "$CONTAINER_SQL"
docker cp "$ROOT/sql/." "$CONTAINER_NAME:$CONTAINER_SQL/"

docker exec "$CONTAINER_NAME" "$SQLCMD" "${SQLCMD_ARGS[@]}" \
  -Q "IF DB_ID('OrderManagementSalesAnalytics') IS NOT NULL DROP DATABASE [OrderManagementSalesAnalytics];"
for script in \
  00_create_database.sql \
  01_create_tables.sql \
  02_seed_reference_data.sql \
  03_bulk_insert.sql \
  04_stored_procedures.sql \
  05_views.sql \
  06_triggers.sql
do
  docker exec "$CONTAINER_NAME" "$SQLCMD" "${SQLCMD_ARGS[@]}" -i "$CONTAINER_SQL/$script"
done

printf '\nLocal SQL Server is ready.\n'
printf 'Database: OrderManagementSalesAnalytics\n'
printf 'Connection: localhost,1433\n'
printf 'Username: sa\n'
printf 'SA password: supplied via MSSQL_SA_PASSWORD (not displayed)\n'
