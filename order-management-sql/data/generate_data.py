"""Generate related, repeatable CSV data for the Order Management database."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from faker import Faker

CATEGORY_COUNT = 8
BATCH_SIZE = 5_000

CUSTOMER_COLUMNS = ["CustomerID", "FirstName", "LastName", "Email", "Phone", "CreatedAt"]
PRODUCT_COLUMNS = ["ProductID", "CategoryID", "SKU", "ProductName", "Price", "IsActive", "CreatedAt"]
INVENTORY_COLUMNS = ["ProductID", "QuantityOnHand", "ReorderLevel", "LastUpdatedAt"]
ORDER_COLUMNS = ["OrderID", "CustomerID", "OrderDate", "OrderStatus"]
ITEM_COLUMNS = ["OrderItemID", "OrderID", "ProductID", "Quantity", "UnitPrice"]
PAYMENT_COLUMNS = ["PaymentID", "OrderID", "PaymentMethod", "Amount", "PaymentStatus", "TransactionReference", "PaidAt", "CreatedAt"]
ORDER_STATUSES = ["Paid", "Shipped", "Delivered", "Pending", "Cancelled"]
ORDER_WEIGHTS = [0.40, 0.20, 0.20, 0.10, 0.10]
PAYMENT_METHODS = ["Card", "Wallet", "BankTransfer", "CashOnDelivery"]


def write_csv(rows: Iterable[Sequence[object]], columns: list[str], path: Path, mode: str = "w") -> None:
    """Write a batch with stable column order and SQL Server-friendly UTF-8 CSV."""
    frame = pd.DataFrame.from_records(rows, columns=columns)
    frame.to_csv(
        path,
        mode=mode,
        header=(mode == "w"),
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def timestamp_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def generate(output_dir: Path, order_count: int, customer_count: int, product_count: int, seed: int) -> dict[str, int]:
    """Create parent CSVs first, then stream order-dependent CSVs in batches."""
    if order_count < 1 or customer_count < 1 or product_count < 5:
        raise ValueError("Orders/customers must be positive and at least 5 products are required.")

    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    fake = Faker()
    fake.seed_instance(seed)

    # Generate customer and product identifiers explicitly for KEEPIDENTITY bulk loading.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=365 * 3)
    customer_profiles = [
        (customer_id, fake.first_name(), fake.last_name(), fake.unique.email(), fake.phone_number()[:30])
        for customer_id in range(1, customer_count + 1)
    ]

    products = []
    product_prices: dict[int, float] = {}
    for product_id in range(1, product_count + 1):
        category_id = ((product_id - 1) % CATEGORY_COUNT) + 1
        price = rng.randint(500, 50_000) / 100
        product_prices[product_id] = price
        products.append((product_id, category_id, f"SKU-{product_id:06d}", fake.catch_phrase(), price, 1, timestamp_text(start)))
    write_csv(products, PRODUCT_COLUMNS, output_dir / "Products.csv")

    # Keep a record of sold units so loaded stock represents post-history on-hand stock.
    sold_units = [0] * (product_count + 1)
    order_item_id = 0
    span_seconds = int((now - start).total_seconds())
    first_order_by_customer: list[datetime | None] = [None] * (customer_count + 1)
    files = {name: output_dir / f"{name}.csv" for name in ("Orders", "OrderItems", "Payments")}

    for batch_start in range(1, order_count + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, order_count + 1)
        orders = []
        items = []
        payments = []
        for order_id in range(batch_start, batch_end):
            customer_id = rng.randint(1, customer_count)
            order_time = start + timedelta(seconds=rng.randrange(span_seconds + 1))
            first_order = first_order_by_customer[customer_id]
            if first_order is None or order_time < first_order:
                first_order_by_customer[customer_id] = order_time
            order_status = rng.choices(ORDER_STATUSES, weights=ORDER_WEIGHTS, k=1)[0]
            orders.append((order_id, customer_id, timestamp_text(order_time), order_status))

            # Three to five unique products guarantees at least 300,000 lines per 100,000 orders.
            line_count = rng.randint(3, 5)
            product_ids = rng.sample(range(1, product_count + 1), line_count)
            order_total = 0.0
            for product_id in product_ids:
                quantity = rng.randint(1, 4)
                unit_price = product_prices[product_id]
                order_total += quantity * unit_price
                sold_units[product_id] += quantity
                order_item_id += 1
                items.append((order_item_id, order_id, product_id, quantity, unit_price))

            successful = order_status in {"Paid", "Shipped", "Delivered"}
            payment_status = "Succeeded" if successful else ("Failed" if order_status == "Cancelled" else "Pending")
            paid_at = timestamp_text(order_time) if successful else ""
            payments.append((order_id, order_id, rng.choice(PAYMENT_METHODS), round(order_total, 2), payment_status,
                             f"SYN-{order_id:010d}", paid_at, timestamp_text(order_time)))

        mode = "w" if batch_start == 1 else "a"
        write_csv(orders, ORDER_COLUMNS, files["Orders"], mode)
        write_csv(items, ITEM_COLUMNS, files["OrderItems"], mode)
        write_csv(payments, PAYMENT_COLUMNS, files["Payments"], mode)

    # Customer creation precedes the first synthetic order; unused test customers start near the data window.
    customers = []
    for customer_id, first_name, last_name, email, phone in customer_profiles:
        first_order = first_order_by_customer[customer_id] or start
        created_at = first_order - timedelta(days=rng.randint(1, 365))
        customers.append((customer_id, first_name, last_name, email, phone, timestamp_text(created_at)))
    write_csv(customers, CUSTOMER_COLUMNS, output_dir / "Customers.csv")

    # The inventory file follows the order history; no trigger is needed during the bulk load.
    inventory = [
        (product_id, sold_units[product_id] + rng.randint(0, 250), rng.randint(10, 50), timestamp_text(now))
        for product_id in range(1, product_count + 1)
    ]
    write_csv(inventory, INVENTORY_COLUMNS, output_dir / "Inventory.csv")

    counts = {
        "customers": customer_count,
        "products": product_count,
        "orders": order_count,
        "order_items": order_item_id,
        "payments": order_count,
    }
    if counts["orders"] >= 100_000 and counts["order_items"] < 250_000:
        raise RuntimeError("Generated order-item count is below the required minimum.")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic, relational order-management CSV files.")
    parser.add_argument("--orders", type=int, default=100_000, help="Number of orders to generate (default: 100000).")
    parser.add_argument("--customers", type=int, default=5_000, help="Number of customers (default: 5000).")
    parser.add_argument("--products", type=int, default=500, help="Number of products; minimum 5 (default: 500).")
    parser.add_argument("--seed", type=int, default=20261005, help="Random seed for repeatable data (default: 20261005).")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "csv",
                        help="Directory for CSV output (default: data/csv).")
    args = parser.parse_args()

    counts = generate(args.output_dir, args.orders, args.customers, args.products, args.seed)
    print(f"CSV files written to: {args.output_dir.resolve()}")
    print("Generated rows: " + ", ".join(f"{name}={count:,}" for name, count in counts.items()))


if __name__ == "__main__":
    main()
