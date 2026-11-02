/*
Purpose: Create reusable sales, inventory, and customer-value reporting views.
How to run: Execute after the tables and data load. Safe to rerun.
*/

USE [OrderManagementSalesAnalytics];
GO

-- Summarize settled sales by month; pending and failed payments are not revenue.
CREATE OR ALTER VIEW dbo.vw_MonthlySales
AS
    SELECT DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1) AS SalesMonth,
           COUNT(DISTINCT o.OrderID) AS OrderCount,
           COUNT(DISTINCT o.CustomerID) AS CustomerCount,
           SUM(pay.Amount) AS Revenue
    FROM dbo.Orders AS o
    JOIN dbo.Payments AS pay ON pay.OrderID = o.OrderID
    WHERE pay.PaymentStatus = 'Succeeded'
    GROUP BY DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1);
GO

-- Highlight stock at or below its configured reorder threshold.
CREATE OR ALTER VIEW dbo.vw_LowStockProducts
AS
    SELECT p.ProductID, p.SKU, p.ProductName,
           c.CategoryName, i.QuantityOnHand, i.ReorderLevel,
           i.LastUpdatedAt
    FROM dbo.Inventory AS i
    JOIN dbo.Products AS p ON p.ProductID = i.ProductID
    JOIN dbo.Categories AS c ON c.CategoryID = p.CategoryID
    WHERE i.QuantityOnHand <= i.ReorderLevel;
GO

-- Include all customers, including customers with no settled orders yet.
CREATE OR ALTER VIEW dbo.vw_CustomerLifetimeValue
AS
    SELECT c.CustomerID, c.FirstName, c.LastName, c.Email,
           COUNT(DISTINCT CASE WHEN pay.PaymentStatus = 'Succeeded' THEN o.OrderID END) AS SuccessfulOrderCount,
           COALESCE(SUM(CASE WHEN pay.PaymentStatus = 'Succeeded' THEN pay.Amount END),
                    CONVERT(decimal(18,2), 0)) AS LifetimeRevenue
    FROM dbo.Customers AS c
    LEFT JOIN dbo.Orders AS o ON o.CustomerID = c.CustomerID
    LEFT JOIN dbo.Payments AS pay ON pay.OrderID = o.OrderID
    GROUP BY c.CustomerID, c.FirstName, c.LastName, c.Email;
GO
