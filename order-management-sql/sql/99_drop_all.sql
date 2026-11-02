/*
Purpose: Remove project procedures, views, types, triggers, and tables for a clean reset.
How to run: Connect to the project database in SSMS and run only when you intentionally
             want to delete all project data and objects. This does not drop the database.
WARNING: Destructive. Back up anything you need before running this script.
*/

USE [OrderManagementSalesAnalytics];
GO

-- Drop stored procedures before their shared table-valued parameter type.
IF OBJECT_ID(N'dbo.usp_PlaceOrder', N'P') IS NOT NULL DROP PROCEDURE dbo.usp_PlaceOrder;
IF OBJECT_ID(N'dbo.usp_GetCustomerHistory', N'P') IS NOT NULL DROP PROCEDURE dbo.usp_GetCustomerHistory;
IF OBJECT_ID(N'dbo.usp_GetMonthlySalesReport', N'P') IS NOT NULL DROP PROCEDURE dbo.usp_GetMonthlySalesReport;
GO

-- Reporting views have no foreign keys, so they can be dropped before base tables.
IF OBJECT_ID(N'dbo.vw_MonthlySales', N'V') IS NOT NULL DROP VIEW dbo.vw_MonthlySales;
IF OBJECT_ID(N'dbo.vw_LowStockProducts', N'V') IS NOT NULL DROP VIEW dbo.vw_LowStockProducts;
IF OBJECT_ID(N'dbo.vw_CustomerLifetimeValue', N'V') IS NOT NULL DROP VIEW dbo.vw_CustomerLifetimeValue;
GO

-- Remove triggers before their tables.
IF OBJECT_ID(N'dbo.trg_OrderItems_ReduceInventory', N'TR') IS NOT NULL DROP TRIGGER dbo.trg_OrderItems_ReduceInventory;
IF OBJECT_ID(N'dbo.trg_Products_AuditPriceChange', N'TR') IS NOT NULL DROP TRIGGER dbo.trg_Products_AuditPriceChange;
GO

IF TYPE_ID(N'dbo.OrderProductList') IS NOT NULL DROP TYPE dbo.OrderProductList;
GO

-- Drop child tables first to satisfy the foreign-key dependencies.
IF OBJECT_ID(N'dbo.PriceAuditLog', N'U') IS NOT NULL DROP TABLE dbo.PriceAuditLog;
IF OBJECT_ID(N'dbo.Payments', N'U') IS NOT NULL DROP TABLE dbo.Payments;
IF OBJECT_ID(N'dbo.OrderItems', N'U') IS NOT NULL DROP TABLE dbo.OrderItems;
IF OBJECT_ID(N'dbo.Inventory', N'U') IS NOT NULL DROP TABLE dbo.Inventory;
IF OBJECT_ID(N'dbo.Orders', N'U') IS NOT NULL DROP TABLE dbo.Orders;
IF OBJECT_ID(N'dbo.Products', N'U') IS NOT NULL DROP TABLE dbo.Products;
IF OBJECT_ID(N'dbo.Categories', N'U') IS NOT NULL DROP TABLE dbo.Categories;
IF OBJECT_ID(N'dbo.Customers', N'U') IS NOT NULL DROP TABLE dbo.Customers;
GO
