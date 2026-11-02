/*
Purpose: Create transactional order placement and customer/monthly reporting procedures.
How to run: Execute after 03_bulk_insert.sql. Safe to rerun; procedures are replaced.
Notes: usp_PlaceOrder accepts dbo.OrderProductList, a table-valued parameter. It checks
       stock under update/serializable locks; the OrderItems trigger performs deduction.
*/

USE [OrderManagementSalesAnalytics];
GO

-- A table type passes any number of product/quantity pairs as one procedure argument.
IF TYPE_ID(N'dbo.OrderProductList') IS NULL
BEGIN
    EXEC(N'CREATE TYPE dbo.OrderProductList AS TABLE
    (
        ProductID int NOT NULL PRIMARY KEY,
        Quantity int NOT NULL CHECK (Quantity > 0)
    );');
END;
GO

-- Place the entire order atomically so payment/order rows cannot be partially saved.
CREATE OR ALTER PROCEDURE dbo.usp_PlaceOrder
    @CustomerID int,
    @Products dbo.OrderProductList READONLY,
    @PaymentMethod nvarchar(30),
    @OrderID bigint OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    SET @OrderID = NULL;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF NOT EXISTS (SELECT 1 FROM dbo.Customers WHERE CustomerID = @CustomerID)
            THROW 50001, 'Customer does not exist.', 1;

        IF NOT EXISTS (SELECT 1 FROM @Products)
            THROW 50002, 'An order must contain at least one product.', 1;

        IF @PaymentMethod IS NULL OR LEN(LTRIM(RTRIM(@PaymentMethod))) = 0
            THROW 50003, 'Payment method is required.', 1;

        -- Lock stock rows until commit so two orders cannot spend the same units.
        IF EXISTS
        (
            SELECT 1
            FROM @Products AS requested
            LEFT JOIN dbo.Products AS p ON p.ProductID = requested.ProductID
            LEFT JOIN dbo.Inventory AS i WITH (UPDLOCK, HOLDLOCK)
                ON i.ProductID = requested.ProductID
            WHERE p.ProductID IS NULL
               OR p.IsActive = 0
               OR i.ProductID IS NULL
               OR i.QuantityOnHand < requested.Quantity
        )
            THROW 50004, 'A requested product is inactive, missing, or out of stock.', 1;

        DECLARE @OrderTotal decimal(12,2);
        SELECT @OrderTotal = SUM(CONVERT(decimal(19,2), requested.Quantity) * p.Price)
        FROM @Products AS requested
        JOIN dbo.Products AS p ON p.ProductID = requested.ProductID;

        INSERT INTO dbo.Orders (CustomerID, OrderStatus)
        VALUES (@CustomerID, 'Pending');
        SET @OrderID = CONVERT(bigint, SCOPE_IDENTITY());

        -- This insert invokes trg_OrderItems_ReduceInventory in the same transaction.
        INSERT INTO dbo.OrderItems (OrderID, ProductID, Quantity, UnitPrice)
        SELECT @OrderID, requested.ProductID, requested.Quantity, p.Price
        FROM @Products AS requested
        JOIN dbo.Products AS p ON p.ProductID = requested.ProductID;

        INSERT INTO dbo.Payments (OrderID, PaymentMethod, Amount, PaymentStatus)
        VALUES (@OrderID, @PaymentMethod, @OrderTotal, 'Pending');

        COMMIT TRANSACTION;

        SELECT @OrderID AS OrderID, @OrderTotal AS OrderTotal;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;
        SET @OrderID = NULL;
        THROW;
    END CATCH;
END;
GO

-- Return one row per order item plus the successful payment amount for that order.
CREATE OR ALTER PROCEDURE dbo.usp_GetCustomerHistory
    @CustomerID int
AS
BEGIN
    SET NOCOUNT ON;

    SELECT o.OrderID, o.OrderDate, o.OrderStatus,
           oi.ProductID, p.ProductName, oi.Quantity, oi.UnitPrice,
           CONVERT(decimal(12,2), oi.Quantity * oi.UnitPrice) AS LineTotal,
           paid.PaidAmount
    FROM dbo.Orders AS o
    LEFT JOIN dbo.OrderItems AS oi ON oi.OrderID = o.OrderID
    LEFT JOIN dbo.Products AS p ON p.ProductID = oi.ProductID
    OUTER APPLY
    (
        SELECT SUM(pay.Amount) AS PaidAmount
        FROM dbo.Payments AS pay
        WHERE pay.OrderID = o.OrderID
          AND pay.PaymentStatus = 'Succeeded'
    ) AS paid
    WHERE o.CustomerID = @CustomerID
    ORDER BY o.OrderDate DESC, o.OrderID DESC, oi.OrderItemID;
END;
GO

-- Use a half-open date range so the OrderDate filter can use a future index.
CREATE OR ALTER PROCEDURE dbo.usp_GetMonthlySalesReport
    @Year int,
    @Month int
AS
BEGIN
    SET NOCOUNT ON;

    IF @Month NOT BETWEEN 1 AND 12 OR @Year NOT BETWEEN 1900 AND 9999
        RAISERROR('Provide a valid year and month.', 16, 1);

    DECLARE @MonthStart date = DATEFROMPARTS(@Year, @Month, 1);
    DECLARE @MonthEnd date = DATEADD(MONTH, 1, @MonthStart);

    SELECT @Year AS SalesYear,
           @Month AS SalesMonth,
           COUNT(DISTINCT o.OrderID) AS OrderCount,
           COUNT(DISTINCT o.CustomerID) AS CustomerCount,
           COALESCE(SUM(pay.Amount), CONVERT(decimal(18,2), 0)) AS Revenue
    FROM dbo.Orders AS o
    LEFT JOIN dbo.Payments AS pay
        ON pay.OrderID = o.OrderID
       AND pay.PaymentStatus = 'Succeeded'
    WHERE o.OrderDate >= @MonthStart
      AND o.OrderDate < @MonthEnd;
END;
GO
