-- TPC-H Q6: Forecasting Revenue Change
-- How much revenue would we gain by removing small discounts?
-- Tables: lineitem
-- Parameters: the specification's validation values (as used by DuckDB's tpch extension).

SELECT
    sum(l_extendedprice * l_discount) AS revenue
FROM
    lineitem
WHERE
    l_shipdate >= CAST('1994-01-01' AS date)
    AND l_shipdate < CAST('1995-01-01' AS date)
    AND l_discount BETWEEN 0.05
    AND 0.07
    AND l_quantity < 24;
