/*
Purpose: Rerun the same three workloads after applying 02_indexes_and_rewrites.sql.
How to run: Run after the baseline measurements and after creating the tuning indexes.
             Compare STATISTICS Messages and actual execution plans; do not assume improvement.
*/

USE [OrderManagementSalesAnalytics];
GO
SET NOCOUNT ON;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO

-- Q1 after: use exactly the same fixed date window as the baseline query.
DECLARE @Q1Start datetime2(0) = '2025-01-01T00:00:00';
DECLARE @Q1End datetime2(0) = '2025-04-01T00:00:00';
SELECT COUNT_BIG(*) AS RecentOrderCount,
       COUNT(DISTINCT CustomerID) AS RecentCustomers
FROM dbo.Orders
WHERE OrderDate >= @Q1Start
  AND OrderDate < @Q1End;
GO

-- Q2 after: ProductID-leading index covers the join and aggregate inputs.
DECLARE @CategoryID int = 1;
SELECT p.CategoryID, p.ProductID, p.ProductName,
       SUM(CONVERT(decimal(19,2), oi.Quantity) * oi.UnitPrice) AS ProductRevenue
FROM dbo.Products AS p
JOIN dbo.OrderItems AS oi ON oi.ProductID = p.ProductID
WHERE p.CategoryID = @CategoryID
GROUP BY p.CategoryID, p.ProductID, p.ProductName
ORDER BY ProductRevenue DESC;
GO

-- Q3 after: same metric with a half-open date range, using the date index efficiently.
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

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
