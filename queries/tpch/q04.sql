-- TPC-H Q4: Order Priority Checking
-- How many orders per priority had at least one line received late?
-- Tables: lineitem, orders
-- Parameters: the specification's validation values (as used by DuckDB's tpch extension).

SELECT
    o_orderpriority,
    count(*) AS order_count
FROM
    orders
WHERE
    o_orderdate >= CAST('1993-07-01' AS date)
    AND o_orderdate < CAST('1993-10-01' AS date)
    AND EXISTS (
        SELECT
            *
        FROM
            lineitem
        WHERE
            l_orderkey = o_orderkey
            AND l_commitdate < l_receiptdate)
GROUP BY
    o_orderpriority
ORDER BY
    o_orderpriority;
