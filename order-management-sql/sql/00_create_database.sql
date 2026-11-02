/*
Purpose: Create the project database if it does not already exist.
How to run: Open this file in SSMS, connect to the target SQL Server, and execute it.
             Then execute 01_create_tables.sql in the same database connection.
Notes: Change the database name here only if you also change the USE statement below
       and the database name in the later project scripts and app configuration.
*/

USE [master];
GO

-- Dynamic SQL keeps CREATE DATABASE inside its own batch and avoids recreating it.
IF DB_ID(N'OrderManagementSalesAnalytics') IS NULL
BEGIN
    EXEC(N'CREATE DATABASE [OrderManagementSalesAnalytics];');
END;
GO

-- Select the project database for scripts run next in this SSMS query window.
USE [OrderManagementSalesAnalytics];
GO
