/*
Purpose: Add targeted non-clustered/covering indexes and show the SARGable monthly rewrite.
How to run: Run after recording 01_slow_queries_before.sql measurements.
             Indexes are created only when their named equivalents do not exist.
*/

USE [OrderManagementSalesAnalytics];
GO
SET NOCOUNT ON;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO

-- Cover recent-order counts and customer counts without a lookup to the base table.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Orders') AND name = N'IX_Orders_OrderDate_CustomerID')
BEGIN
    CREATE NONCLUSTERED INDEX IX_Orders_OrderDate_CustomerID
        ON dbo.Orders (OrderDate, CustomerID)
        INCLUDE (OrderID, OrderStatus);
END;
GO

-- Cover product/category reporting and avoid scanning all order-item rows by ProductID.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.OrderItems') AND name = N'IX_OrderItems_ProductID_OrderID')
BEGIN
    CREATE NONCLUSTERED INDEX IX_OrderItems_ProductID_OrderID
        ON dbo.OrderItems (ProductID, OrderID)
        INCLUDE (Quantity, UnitPrice);
END;
GO

-- Cover payment status and amount when monthly orders are joined to payments.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Payments') AND name = N'IX_Payments_OrderID_PaymentStatus')
BEGIN
    CREATE NONCLUSTERED INDEX IX_Payments_OrderID_PaymentStatus
        ON dbo.Payments (OrderID, PaymentStatus)
        INCLUDE (Amount);
END;
GO

-- SARGable rewrite for Q3: calculate the range once instead of applying YEAR/MONTH to every row.
DECLARE @SalesYear int = 2025;
DECLARE @SalesMonth int = 1;
DECLARE @MonthStart datetime2(0) = DATETIME2FROMPARTS(@SalesYear, @SalesMonth, 1, 0, 0, 0, 0, 0);
DECLARE @MonthEnd datetime2(0) = DATEADD(MONTH, 1, @MonthStart);
SELECT COUNT(DISTINCT o.OrderID) AS PaidOrders,
       SUM(pay.Amount) AS MonthlyRevenue
FROM dbo.Orders AS o
JOIN dbo.Payments AS pay ON pay.OrderID = o.OrderID
WHERE pay.PaymentStatus = 'Succeeded'
  AND o.OrderDate >= @MonthStart
  AND o.OrderDate < @MonthEnd;
GO

-- Index maintenance adds write and storage cost. Review actual plans before keeping indexes.
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
