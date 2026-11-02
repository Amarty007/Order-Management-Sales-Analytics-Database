/*
Purpose: Load the generated UTF-8 CSV files into an empty project database.
How to run: Run 02_seed_reference_data.sql, run data/generate_data.py, replace the
             six placeholder paths below with paths readable by the SQL Server service,
             then execute this script in SSMS.
Important: BULK INSERT runs on the SQL Server host, not on the SSMS client. Grant the
           SQL Server service account read access to the folder. FORMAT='CSV' requires
           SQL Server 2017 or newer. This script preserves generated identity values.
*/

USE [OrderManagementSalesAnalytics];
GO

-- Avoid duplicate loads. Use the reset script only when you intentionally want to reload.
IF EXISTS (SELECT 1 FROM dbo.Customers)
   OR EXISTS (SELECT 1 FROM dbo.Products)
   OR EXISTS (SELECT 1 FROM dbo.Inventory)
   OR EXISTS (SELECT 1 FROM dbo.Orders)
   OR EXISTS (SELECT 1 FROM dbo.OrderItems)
   OR EXISTS (SELECT 1 FROM dbo.Payments)
BEGIN
    THROW 51010, 'Target data tables are not empty. Load was stopped to prevent duplicates.', 1;
END;
GO

-- Point to the SQL Server-visible CSV directory inside the local Docker container.
BULK INSERT dbo.Customers
FROM '/var/opt/mssql/data/project_csv/Customers.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

BULK INSERT dbo.Products
FROM '/var/opt/mssql/data/project_csv/Products.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

BULK INSERT dbo.Inventory
FROM '/var/opt/mssql/data/project_csv/Inventory.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

BULK INSERT dbo.Orders
FROM '/var/opt/mssql/data/project_csv/Orders.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

BULK INSERT dbo.OrderItems
FROM '/var/opt/mssql/data/project_csv/OrderItems.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

BULK INSERT dbo.Payments
FROM '/var/opt/mssql/data/project_csv/Payments.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', KEEPIDENTITY, TABLOCK, BATCHSIZE = 50000);
GO

-- These checks make missing or partial loads visible immediately.
SELECT 'Customers' AS TableName, COUNT_BIG(*) AS TableRowCount FROM dbo.Customers
UNION ALL SELECT 'Products', COUNT_BIG(*) FROM dbo.Products
UNION ALL SELECT 'Inventory', COUNT_BIG(*) FROM dbo.Inventory
UNION ALL SELECT 'Orders', COUNT_BIG(*) FROM dbo.Orders
UNION ALL SELECT 'OrderItems', COUNT_BIG(*) FROM dbo.OrderItems
UNION ALL SELECT 'Payments', COUNT_BIG(*) FROM dbo.Payments;
GO
