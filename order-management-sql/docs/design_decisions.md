# Design Decisions

## Relational Design

- **Third normal form:** Customers, Categories, Products, Orders, Payments, and Inventory each store facts about one entity. `OrderItems` models the many-to-many relationship between orders and products. Category names and customer details are not repeated on every order line, which limits update anomalies.
- **Checkout-time unit price:** `OrderItems.UnitPrice` is intentionally stored with the order line. It is a fact about that transaction and must not change when the catalog price changes later.
- **Inventory separation:** One `Inventory` row per product separates changing stock quantities from product descriptions and prices. Its product key is also its foreign key.
- **Payment history:** Payments are separate from Orders so failed attempts, successful payments, and later refunds can be represented without overwriting the order.
- **Price audit:** `PriceAuditLog` stores old/new price, time, and SQL Server login for each real product price change. It is an audit trail, not the current source of price.
- **Constraints:** Named PK/FK, CHECK, UNIQUE, and DEFAULT constraints reject invalid values close to the data. Examples include positive order quantity, nonnegative prices/stock, and unique customer email/SKU.

## Transaction and Trigger Choices

- `usp_PlaceOrder` accepts `dbo.OrderProductList`, validates every requested product and stock quantity, writes order/items/payment in one transaction, and rethrows errors after rollback.
- Inventory rows are read with update/serializable locks while stock is checked. This protects the validation-and-deduction workflow from two concurrent orders spending the same units.
- The order-item trigger aggregates the `inserted` pseudo-table by product, checks all required stock, and applies one set-based update. SQL Server triggers fire per statement, not once per row, so code must handle multi-row inserts.
- The price trigger joins `inserted` and `deleted` by product ID and records only actual price changes. An update statement may affect multiple products.
- Historical data is bulk-loaded before triggers are created. The generator initializes on-hand stock to historical sold units plus a remaining quantity, so loading those order rows does not deduct stock twice.

## Index Choices

- SQL Server creates clustered primary-key indexes for the identity keys and a unique index for the inventory product key. This makes row identity and one-to-one inventory lookup efficient.
- `IX_Orders_OrderDate_CustomerID` supports date-range reporting and covers the customer/order columns used by the baseline query. A leading date key can seek a time range.
- `IX_OrderItems_ProductID_OrderID` supports joins from selected products to their order lines and includes quantity/price so the aggregate can be covered.
- `IX_Payments_OrderID_PaymentStatus` supports order-to-payment lookups and includes amount for settled-revenue reporting.
- Indexes consume storage and add write work. Measure actual plans, logical reads, and elapsed time before deciding to retain an index; do not assume every index improves every workload.

## Measurement Rules

The baseline and after scripts use matching parameters and enable `SET STATISTICS IO ON` and `SET STATISTICS TIME ON`. Record logical reads from SSMS Messages and elapsed time from the same execution method. Keep dataset, parameters, server conditions, and measurement method consistent, and report only values actually observed on your SQL Server.
