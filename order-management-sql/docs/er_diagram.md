# Entity Relationship Diagram

The diagram shows the project tables and their one-to-many relationships. `Inventory` is one-to-one with `Products`; a product can have many order lines and price audit entries. An order can have multiple payment attempts.

```mermaid
erDiagram
    Customers ||--o{ Orders : places
    Categories ||--o{ Products : groups
    Products ||--|| Inventory : tracks
    Orders ||--|{ OrderItems : contains
    Products ||--o{ OrderItems : appears_in
    Orders ||--o{ Payments : receives
    Products ||--o{ PriceAuditLog : records_changes

    Customers {
        int CustomerID PK
        nvarchar FirstName
        nvarchar LastName
        nvarchar Email UK
        nvarchar Phone
        datetime2 CreatedAt
    }
    Categories {
        int CategoryID PK
        nvarchar CategoryName UK
        nvarchar Description
        bit IsActive
    }
    Products {
        int ProductID PK
        int CategoryID FK
        nvarchar SKU UK
        nvarchar ProductName
        decimal Price
        bit IsActive
    }
    Inventory {
        int ProductID PK, FK
        int QuantityOnHand
        int ReorderLevel
        datetime2 LastUpdatedAt
    }
    Orders {
        bigint OrderID PK
        int CustomerID FK
        datetime2 OrderDate
        varchar OrderStatus
    }
    OrderItems {
        bigint OrderItemID PK
        bigint OrderID FK
        int ProductID FK
        int Quantity
        decimal UnitPrice
    }
    Payments {
        bigint PaymentID PK
        bigint OrderID FK
        nvarchar PaymentMethod
        decimal Amount
        varchar PaymentStatus
        datetime2 PaidAt
    }
    PriceAuditLog {
        bigint PriceAuditID PK
        int ProductID FK
        decimal OldPrice
        decimal NewPrice
        datetime2 ChangedAt
        sysname ChangedBy
    }
```

`UK` labels a unique key. `OrderItems.UnitPrice` is the checkout-time price, not a copy of the current catalog price; it preserves transaction history when `Products.Price` changes.
