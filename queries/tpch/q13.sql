-- TPC-H Q13: Customer Distribution
-- How many customers have 0, 1, 2… orders?
-- Tables: customer, orders
-- Parameters: the specification's validation values (as used by DuckDB's tpch extension).

SELECT
    c_count,
    count(*) AS custdist
FROM (
    SELECT
        c_custkey,
        count(o_orderkey)
    FROM
        customer
    LEFT OUTER JOIN orders ON c_custkey = o_custkey
    AND o_comment NOT LIKE '%special%requests%'
GROUP BY
    c_custkey) AS c_orders (c_custkey,
        c_count)
GROUP BY
    c_count
ORDER BY
    custdist DESC,
    c_count DESC;
