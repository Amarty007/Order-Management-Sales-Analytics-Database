/*
Purpose: Enforce stock deduction on order lines and record product price changes.
How to run: Execute after 01_create_tables.sql. Safe to rerun; triggers are replaced.
Notes: The inventory trigger is set-based so one INSERT statement can contain many lines.
*/

USE [OrderManagementSalesAnalytics];
GO

-- Aggregate the inserted lines first because one product can appear on multiple orders.
CREATE OR ALTER TRIGGER dbo.trg_OrderItems_ReduceInventory
ON dbo.OrderItems
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    -- Reject missing inventory or insufficient stock; the insert and trigger roll back together.
    IF EXISTS
    (
        SELECT 1
        FROM
        (
            SELECT ProductID, SUM(CONVERT(bigint, Quantity)) AS RequiredQuantity
            FROM inserted
            GROUP BY ProductID
        ) AS r
        LEFT JOIN dbo.Inventory AS i WITH (UPDLOCK, HOLDLOCK)
            ON i.ProductID = r.ProductID
        WHERE i.ProductID IS NULL
           OR i.QuantityOnHand < r.RequiredQuantity
    )
        THROW 50005, 'Order item insert rejected because stock is missing or insufficient.', 1;

    ;WITH Requested AS
    (
        SELECT ProductID, SUM(CONVERT(bigint, Quantity)) AS RequiredQuantity
        FROM inserted
        GROUP BY ProductID
    )
    UPDATE i
       SET i.QuantityOnHand = i.QuantityOnHand - r.RequiredQuantity,
           i.LastUpdatedAt = SYSUTCDATETIME()
    FROM dbo.Inventory AS i
    JOIN Requested AS r ON r.ProductID = i.ProductID;
END;
GO

-- inserted/deleted let the audit capture every changed product in a multi-row UPDATE.
CREATE OR ALTER TRIGGER dbo.trg_Products_AuditPriceChange
ON dbo.Products
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF UPDATE(Price)
    BEGIN
        INSERT INTO dbo.PriceAuditLog (ProductID, OldPrice, NewPrice, ChangedBy)
        SELECT i.ProductID, d.Price, i.Price, SUSER_SNAME()
        FROM inserted AS i
        JOIN deleted AS d ON d.ProductID = i.ProductID
        WHERE i.Price <> d.Price;
    END;
END;
GO
