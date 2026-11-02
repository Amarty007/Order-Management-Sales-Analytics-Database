# Performance Results

Do not fill these cells with estimates. Record actual measurements from your SQL Server instance after running the scripts against the same loaded dataset.

## Measurement Steps

1. Load at least 100,000 orders and keep the data unchanged between runs.
2. Run `performance/01_slow_queries_before.sql` before creating the tuning indexes.
3. For each query, capture elapsed time from SSMS Messages (`SET STATISTICS TIME ON`) and logical reads (`SET STATISTICS IO ON`). Use the same parameters for the matching after-query.
4. Run `performance/02_indexes_and_rewrites.sql`, then `performance/03_slow_queries_after.sql`.
5. Record actual execution plans and note whether the expected index was used. Repeat each query consistently; disclose your measurement method and do not clear a shared server cache.
6. Replace the placeholder cells below with measured values only. SQL Server version, machine, caching, concurrent activity, and data distribution affect results.

| Query | Time before | Time after | Logical reads before | Logical reads after |
|---|---:|---:|---:|---:|
| Q1: Recent orders and customers | [X ms] | [Y ms] | [X reads] | [Y reads] |
| Q2: Product revenue by category | [X ms] | [Y ms] | [X reads] | [Y reads] |
| Q3: Monthly settled revenue | [X ms] | [Y ms] | [X reads] | [Y reads] |

## Notes

- No performance result is pre-populated because the scripts have not been measured on your SQL Server environment.
- A new index can improve reads while increasing storage and write cost. Keep it only when the measured workload justifies it.
