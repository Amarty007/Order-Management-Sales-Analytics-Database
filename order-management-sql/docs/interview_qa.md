# Project Interview Questions and Answers

These answers describe the implementation in this repository. Be ready to explain and demonstrate the code rather than memorizing the wording.

1. **Why did you choose an e-commerce order database?**  
   It has realistic relationships across customers, products, orders, payments, and inventory, so one project can demonstrate schema design, transactions, reporting, and tuning.

2. **How did you apply 3NF?**  
   I keep each entity's descriptive facts in its own table. Order/product relationships and quantities belong in `OrderItems`; customer and category descriptions are not repeated on every order line.

3. **Why is `UnitPrice` stored in `OrderItems` when `Products` already has `Price`?**  
   It records the price agreed at checkout. If the catalog price changes later, past order totals must remain unchanged.

4. **What does a foreign key provide here?**  
   It prevents orphan rows, such as an order for a customer that does not exist or an order line for a missing product.

5. **How does `usp_PlaceOrder` keep an order atomic?**  
   It starts a transaction, validates the customer and every requested stock quantity, then inserts the order, lines, and payment. The CATCH block rolls back and rethrows errors.

6. **Why does the procedure accept a table-valued parameter?**  
   A product list is naturally a set of product/quantity rows. A TVP passes that set to one procedure call without building dynamic SQL or making one call per product.

7. **How do you prevent overselling under concurrency?**  
   The procedure locks the requested inventory rows while it checks stock and keeps those locks through the transaction. The trigger then deducts the requested quantities in the same transaction.

8. **What is `XACT_ABORT` used for?**  
   It tells SQL Server to abort the transaction for many run-time errors. The explicit TRY/CATCH rollback still makes the failure path visible and rethrows the original error.

9. **Why is the inventory trigger set-based?**  
   SQL Server fires a DML trigger once per statement. Aggregating `inserted` by product makes one-row and multi-row inserts behave correctly.

10. **How does the price audit trigger find the old and new values?**  
    `deleted` contains the pre-update rows and `inserted` contains the post-update rows. Joining them by `ProductID` gives the old/new price pair.

11. **What are risks of using triggers?**  
    They can hide work from callers and make write behavior harder to trace. This project keeps them focused on mandatory inventory and audit rules, and tests the multi-row behavior.

12. **Why keep Payments separate from Orders?**  
    An order can have multiple payment attempts or methods. Separating them preserves that history and lets reports count only succeeded payments as settled revenue.

13. **What does the lifetime value view calculate?**  
    It returns every customer and aggregates only successful payment amounts, including zero revenue for customers without settled payments.

14. **What makes a predicate SARGable?**  
    A SARGable predicate lets SQL Server search an index key directly. A half-open `OrderDate >= @Start AND OrderDate < @End` range is preferable to wrapping the column in `YEAR()` and `MONTH()`.

15. **When would you use `RANK` instead of `ROW_NUMBER`?**  
    `RANK` preserves ties and can return more than three products when tied at rank three. `ROW_NUMBER` assigns a unique sequence and returns exactly three when filtered to three.

16. **What does `LAG` do in the monthly report?**  
    It reads the previous row's monthly revenue without a self-join, allowing a month-over-month comparison.

17. **What does `NTILE(4)` do in customer segmentation?**  
    It divides the ordered customer rows into four roughly equal groups. The project orders by lifetime revenue to create revenue quartiles.

18. **What is a covering index?**  
    It contains the search/join keys and any additional columns a query needs, often with `INCLUDE`, so SQL Server may answer the query without looking up the base row.

19. **How did you evaluate the tuning changes?**  
    The scripts enable `STATISTICS IO` and `STATISTICS TIME`; I compare logical reads, elapsed time, and actual execution plans before and after on the same data and parameters.

20. **What performance improvement did the project achieve?**  
    I would report only the values I measured on my own SQL Server. The repository deliberately leaves the results table blank so no unverified improvement is claimed.
