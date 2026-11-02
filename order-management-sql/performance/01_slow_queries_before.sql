/*
Purpose: Capture baseline reads and elapsed time for three intentionally expensive query patterns.
How to run: Run after loading 100,000+ orders and before 02_indexes_and_rewrites.sql.
             Keep the dataset and date parameters the same when comparing after tuning.
*/

USE [OrderManagementSalesAnalytics];
GO
SET NOCOUNT ON;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO

-- Q1 baseline: date range is SARGable, but Orders has no OrderDate index yet.
-- Keep this fixed window identical in the after script for a fair comparison.
DECLARE @Q1Start datetime2(0) = '2025-01-01T00:00:00';
DECLARE @Q1End datetime2(0) = '2025-04-01T00:00:00';
SELECT COUNT_BIG(*) AS RecentOrderCount,
       COUNT(DISTINCT CustomerID) AS RecentCustomers
FROM dbo.Orders
WHERE OrderDate >= @Q1Start
  AND OrderDate < @Q1End;
GO

-- Q2 baseline: ProductID is an unindexed foreign key in OrderItems before tuning.
DECLARE @CategoryID int = 1;
SELECT p.CategoryID, p.ProductID, p.ProductName,
       SUM(CONVERT(decimal(19,2), oi.Quantity) * oi.UnitPrice) AS ProductRevenue
FROM dbo.Products AS p
JOIN dbo.OrderItems AS oi ON oi.ProductID = p.ProductID
WHERE p.CategoryID = @CategoryID
GROUP BY p.CategoryID, p.ProductID, p.ProductName
ORDER BY ProductRevenue DESC;
GO

-- Q3 baseline: functions on OrderDate prevent an efficient seek on a date index.
DECLARE @SalesYear int = 2025;
DECLARE @SalesMonth int = 1;
SELECT COUNT(DISTINCT o.OrderID) AS PaidOrders,
       SUM(pay.Amount) AS MonthlyRevenue
FROM dbo.Orders AS o
JOIN dbo.Payments AS pay ON pay.OrderID = o.OrderID
WHERE pay.PaymentStatus = 'Succeeded'
  AND YEAR(o.OrderDate) = @SalesYear
  AND MONTH(o.OrderDate) = @SalesMonth;
GO

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
