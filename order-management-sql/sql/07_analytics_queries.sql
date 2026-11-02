/*
Purpose: Demonstrate CTEs and window functions for product, revenue, and customer analysis.
How to run: Execute after tables and data are loaded. Results are read-only.
*/

USE [OrderManagementSalesAnalytics];
GO
SET NOCOUNT ON;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO

-- Rank each product by booked item revenue inside its category; RANK preserves ties.
;WITH ProductRevenue AS
(
    SELECT p.CategoryID, c.CategoryName, p.ProductID, p.ProductName,
           SUM(CONVERT(decimal(19,2), oi.Quantity) * oi.UnitPrice) AS Revenue
    FROM dbo.Products AS p
    JOIN dbo.Categories AS c ON c.CategoryID = p.CategoryID
    JOIN dbo.OrderItems AS oi ON oi.ProductID = p.ProductID
    GROUP BY p.CategoryID, c.CategoryName, p.ProductID, p.ProductName
), RankedProducts AS
(
    SELECT *,
           RANK() OVER (PARTITION BY CategoryID ORDER BY Revenue DESC) AS RevenueRank,
           ROW_NUMBER() OVER (PARTITION BY CategoryID ORDER BY Revenue DESC, ProductID) AS RowNumber
    FROM ProductRevenue
)
SELECT CategoryName, ProductID, ProductName, Revenue, RevenueRank, RowNumber
FROM RankedProducts
WHERE RevenueRank <= 3
ORDER BY CategoryID, RevenueRank, ProductID;
GO

-- Add monthly revenue to all previous months with an explicit window frame.
;WITH MonthlyRevenue AS
(
    SELECT SalesMonth, SUM(Revenue) AS Revenue
    FROM dbo.vw_MonthlySales
    GROUP BY SalesMonth
)
SELECT SalesMonth, Revenue,
       SUM(Revenue) OVER
           (ORDER BY SalesMonth ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RunningRevenue
FROM MonthlyRevenue
ORDER BY SalesMonth;
GO

-- LAG compares each month with its previous available sales month.
;WITH MonthlyRevenue AS
(
    SELECT SalesMonth, SUM(Revenue) AS Revenue
    FROM dbo.vw_MonthlySales
    GROUP BY SalesMonth
), WithPreviousMonth AS
(
    SELECT SalesMonth, Revenue,
           LAG(Revenue) OVER (ORDER BY SalesMonth) AS PreviousMonthRevenue
    FROM MonthlyRevenue
)
SELECT SalesMonth, Revenue, PreviousMonthRevenue,
       CASE WHEN PreviousMonthRevenue IS NULL OR PreviousMonthRevenue = 0 THEN NULL
            ELSE (Revenue - PreviousMonthRevenue) * 100.0 / PreviousMonthRevenue
       END AS MonthOverMonthGrowthPercent
FROM WithPreviousMonth
ORDER BY SalesMonth;
GO

-- NTILE divides customers into four equal-sized groups by lifetime revenue.
;WITH CustomerValue AS
(
    SELECT CustomerID, FirstName, LastName, LifetimeRevenue
    FROM dbo.vw_CustomerLifetimeValue
), CustomerSegments AS
(
    SELECT *, NTILE(4) OVER (ORDER BY LifetimeRevenue DESC, CustomerID) AS RevenueQuartile
    FROM CustomerValue
)
SELECT RevenueQuartile, COUNT_BIG(*) AS CustomerCount,
       MIN(LifetimeRevenue) AS MinimumLifetimeRevenue,
       MAX(LifetimeRevenue) AS MaximumLifetimeRevenue
FROM CustomerSegments
GROUP BY RevenueQuartile
ORDER BY RevenueQuartile;
GO

-- Classify each customer-month as new or returning based on the first order date.
;WITH FirstOrder AS
(
    SELECT CustomerID, MIN(OrderDate) AS FirstOrderDate
    FROM dbo.Orders
    GROUP BY CustomerID
), CustomerMonths AS
(
    SELECT o.CustomerID,
           DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1) AS SalesMonth,
           COUNT_BIG(*) AS OrdersInMonth,
           f.FirstOrderDate
    FROM dbo.Orders AS o
    JOIN FirstOrder AS f ON f.CustomerID = o.CustomerID
    GROUP BY o.CustomerID, DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1), f.FirstOrderDate
)
SELECT SalesMonth,
       CASE WHEN FirstOrderDate >= SalesMonth
                  AND FirstOrderDate < DATEADD(MONTH, 1, SalesMonth)
            THEN 'New' ELSE 'Repeat' END AS CustomerType,
       COUNT_BIG(*) AS CustomerCount,
       SUM(OrdersInMonth) AS OrderCount
FROM CustomerMonths
GROUP BY SalesMonth,
         CASE WHEN FirstOrderDate >= SalesMonth
                   AND FirstOrderDate < DATEADD(MONTH, 1, SalesMonth)
              THEN 'New' ELSE 'Repeat' END
ORDER BY SalesMonth, CustomerType;
GO

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO
