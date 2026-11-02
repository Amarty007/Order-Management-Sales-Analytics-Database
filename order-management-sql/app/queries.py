"""Static, parameterized SQL statements used by the dashboard."""

KPI_SQL = """
SELECT
    (SELECT COALESCE(SUM(Amount), CONVERT(decimal(18,2), 0))
     FROM dbo.Payments WHERE PaymentStatus = 'Succeeded') AS TotalRevenue,
    (SELECT COUNT_BIG(*) FROM dbo.Orders) AS TotalOrders,
    (SELECT COUNT_BIG(*) FROM dbo.Customers) AS TotalCustomers;
"""

MONTHLY_REVENUE_SQL = """
SELECT SalesMonth, Revenue
FROM dbo.vw_MonthlySales
ORDER BY SalesMonth;
"""

TOP_PRODUCTS_SQL = """
SELECT TOP (10) p.ProductName,
       SUM(CONVERT(decimal(19,2), oi.Quantity) * oi.UnitPrice) AS Revenue
FROM dbo.Products AS p
JOIN dbo.OrderItems AS oi ON oi.ProductID = p.ProductID
JOIN dbo.Orders AS o ON o.OrderID = oi.OrderID
WHERE o.OrderStatus IN ('Paid', 'Shipped', 'Delivered')
GROUP BY p.ProductID, p.ProductName
ORDER BY Revenue DESC, p.ProductName;
"""

LOW_STOCK_SQL = """
SELECT ProductID, SKU, ProductName, CategoryName, QuantityOnHand, ReorderLevel, LastUpdatedAt
FROM dbo.vw_LowStockProducts
ORDER BY QuantityOnHand, ProductName;
"""

CUSTOMER_HISTORY_SQL = "EXEC dbo.usp_GetCustomerHistory @CustomerID = ?;"
