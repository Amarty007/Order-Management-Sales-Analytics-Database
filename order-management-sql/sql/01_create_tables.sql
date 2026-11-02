/*
Purpose: Create the normalized project tables and core data-integrity constraints.
How to run: Execute 00_create_database.sql first, then run this file in SSMS.
             It is safe to rerun: existing tables are left unchanged.
Design: Each table stores one entity or relationship. OrderItems stores the price
        charged at order time so later product-price changes do not rewrite history.
*/

USE [OrderManagementSalesAnalytics];
GO

-- One row per shopper. A unique email prevents duplicate customer accounts.
IF OBJECT_ID(N'dbo.Customers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Customers
    (
        CustomerID  int IDENTITY(1,1) NOT NULL,
        FirstName   nvarchar(80) NOT NULL,
        LastName    nvarchar(80) NOT NULL,
        Email       nvarchar(320) NOT NULL,
        Phone       nvarchar(30) NULL,
        CreatedAt   datetime2(0) NOT NULL
            CONSTRAINT DF_Customers_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Customers PRIMARY KEY CLUSTERED (CustomerID),
        CONSTRAINT UQ_Customers_Email UNIQUE (Email),
        CONSTRAINT CK_Customers_Email_NotBlank
            CHECK (LEN(LTRIM(RTRIM(Email))) > 0)
    );
END;
GO

-- Categories are reference data used to group products.
IF OBJECT_ID(N'dbo.Categories', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Categories
    (
        CategoryID   int IDENTITY(1,1) NOT NULL,
        CategoryName nvarchar(100) NOT NULL,
        Description  nvarchar(500) NULL,
        IsActive     bit NOT NULL
            CONSTRAINT DF_Categories_IsActive DEFAULT (1),
        CONSTRAINT PK_Categories PRIMARY KEY CLUSTERED (CategoryID),
        CONSTRAINT UQ_Categories_CategoryName UNIQUE (CategoryName),
        CONSTRAINT CK_Categories_CategoryName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(CategoryName))) > 0)
    );
END;
GO

-- Product facts live here; category details stay in Categories to avoid duplication.
IF OBJECT_ID(N'dbo.Products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Products
    (
        ProductID   int IDENTITY(1,1) NOT NULL,
        CategoryID  int NOT NULL,
        SKU         nvarchar(40) NOT NULL,
        ProductName nvarchar(160) NOT NULL,
        Price       decimal(12,2) NOT NULL,
        IsActive    bit NOT NULL
            CONSTRAINT DF_Products_IsActive DEFAULT (1),
        CreatedAt   datetime2(0) NOT NULL
            CONSTRAINT DF_Products_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Products PRIMARY KEY CLUSTERED (ProductID),
        CONSTRAINT UQ_Products_SKU UNIQUE (SKU),
        CONSTRAINT FK_Products_Categories
            FOREIGN KEY (CategoryID) REFERENCES dbo.Categories (CategoryID),
        CONSTRAINT CK_Products_Price_NonNegative CHECK (Price >= 0),
        CONSTRAINT CK_Products_SKU_NotBlank
            CHECK (LEN(LTRIM(RTRIM(SKU))) > 0),
        CONSTRAINT CK_Products_ProductName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(ProductName))) > 0)
    );
END;
GO

-- A single inventory row per product makes stock independently maintainable.
IF OBJECT_ID(N'dbo.Inventory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Inventory
    (
        ProductID      int NOT NULL,
        QuantityOnHand int NOT NULL
            CONSTRAINT DF_Inventory_QuantityOnHand DEFAULT (0),
        ReorderLevel   int NOT NULL
            CONSTRAINT DF_Inventory_ReorderLevel DEFAULT (10),
        LastUpdatedAt  datetime2(0) NOT NULL
            CONSTRAINT DF_Inventory_LastUpdatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Inventory PRIMARY KEY CLUSTERED (ProductID),
        CONSTRAINT FK_Inventory_Products
            FOREIGN KEY (ProductID) REFERENCES dbo.Products (ProductID),
        CONSTRAINT CK_Inventory_QuantityOnHand_NonNegative
            CHECK (QuantityOnHand >= 0),
        CONSTRAINT CK_Inventory_ReorderLevel_NonNegative
            CHECK (ReorderLevel >= 0)
    );
END;
GO

-- One order belongs to one customer; status is limited to known workflow values.
IF OBJECT_ID(N'dbo.Orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Orders
    (
        OrderID     bigint IDENTITY(1,1) NOT NULL,
        CustomerID  int NOT NULL,
        OrderDate   datetime2(0) NOT NULL
            CONSTRAINT DF_Orders_OrderDate DEFAULT (SYSUTCDATETIME()),
        OrderStatus varchar(20) NOT NULL
            CONSTRAINT DF_Orders_OrderStatus DEFAULT ('Pending'),
        CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED (OrderID),
        CONSTRAINT FK_Orders_Customers
            FOREIGN KEY (CustomerID) REFERENCES dbo.Customers (CustomerID),
        CONSTRAINT CK_Orders_OrderStatus
            CHECK (OrderStatus IN ('Pending', 'Paid', 'Shipped', 'Delivered', 'Cancelled'))
    );
END;
GO

-- Order lines preserve the quantity and unit price agreed to at checkout.
IF OBJECT_ID(N'dbo.OrderItems', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderItems
    (
        OrderItemID bigint IDENTITY(1,1) NOT NULL,
        OrderID     bigint NOT NULL,
        ProductID   int NOT NULL,
        Quantity    int NOT NULL,
        UnitPrice   decimal(12,2) NOT NULL,
        CONSTRAINT PK_OrderItems PRIMARY KEY CLUSTERED (OrderItemID),
        CONSTRAINT FK_OrderItems_Orders
            FOREIGN KEY (OrderID) REFERENCES dbo.Orders (OrderID),
        CONSTRAINT FK_OrderItems_Products
            FOREIGN KEY (ProductID) REFERENCES dbo.Products (ProductID),
        CONSTRAINT UQ_OrderItems_Order_Product UNIQUE (OrderID, ProductID),
        CONSTRAINT CK_OrderItems_Quantity_Positive CHECK (Quantity > 0),
        CONSTRAINT CK_OrderItems_UnitPrice_NonNegative CHECK (UnitPrice >= 0)
    );
END;
GO

-- Separate payment rows allow an order to have multiple payment attempts or methods.
IF OBJECT_ID(N'dbo.Payments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Payments
    (
        PaymentID          bigint IDENTITY(1,1) NOT NULL,
        OrderID            bigint NOT NULL,
        PaymentMethod      nvarchar(30) NOT NULL,
        Amount             decimal(12,2) NOT NULL,
        PaymentStatus      varchar(20) NOT NULL
            CONSTRAINT DF_Payments_PaymentStatus DEFAULT ('Pending'),
        TransactionReference nvarchar(100) NULL,
        PaidAt             datetime2(0) NULL,
        CreatedAt          datetime2(0) NOT NULL
            CONSTRAINT DF_Payments_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_Payments PRIMARY KEY CLUSTERED (PaymentID),
        CONSTRAINT FK_Payments_Orders
            FOREIGN KEY (OrderID) REFERENCES dbo.Orders (OrderID),
        CONSTRAINT CK_Payments_Amount_NonNegative CHECK (Amount >= 0),
        CONSTRAINT CK_Payments_PaymentMethod_NotBlank
            CHECK (LEN(LTRIM(RTRIM(PaymentMethod))) > 0),
        CONSTRAINT CK_Payments_PaymentStatus
            CHECK (PaymentStatus IN ('Pending', 'Succeeded', 'Failed', 'Refunded'))
    );
END;
GO

-- Price changes are recorded separately so the current product row stays normalized.
IF OBJECT_ID(N'dbo.PriceAuditLog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PriceAuditLog
    (
        PriceAuditID bigint IDENTITY(1,1) NOT NULL,
        ProductID    int NOT NULL,
        OldPrice     decimal(12,2) NOT NULL,
        NewPrice     decimal(12,2) NOT NULL,
        ChangedAt    datetime2(0) NOT NULL
            CONSTRAINT DF_PriceAuditLog_ChangedAt DEFAULT (SYSUTCDATETIME()),
        ChangedBy    sysname NOT NULL
            CONSTRAINT DF_PriceAuditLog_ChangedBy DEFAULT (SUSER_SNAME()),
        CONSTRAINT PK_PriceAuditLog PRIMARY KEY CLUSTERED (PriceAuditID),
        CONSTRAINT FK_PriceAuditLog_Products
            FOREIGN KEY (ProductID) REFERENCES dbo.Products (ProductID),
        CONSTRAINT CK_PriceAuditLog_OldPrice_NonNegative CHECK (OldPrice >= 0),
        CONSTRAINT CK_PriceAuditLog_NewPrice_NonNegative CHECK (NewPrice >= 0)
    );
END;
GO

-- Confirm the expected table count after creating the schema.
SELECT COUNT_BIG(*) AS ProjectTableCount
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'dbo'
  AND t.name IN
      (N'Customers', N'Categories', N'Products', N'Orders', N'OrderItems',
       N'Payments', N'Inventory', N'PriceAuditLog');
GO
