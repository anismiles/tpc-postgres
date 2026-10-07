-- TPC-H Q17: Small-Quantity-Order Revenue
-- How much revenue would be lost by not filling small orders for a part?
-- Tables: lineitem, part
-- Parameters: the specification's validation values (as used by DuckDB's tpch extension).

SELECT
    sum(l_extendedprice) / 7.0 AS avg_yearly
FROM
    lineitem,
    part
WHERE
    p_partkey = l_partkey
    AND p_brand = 'Brand#23'
    AND p_container = 'MED BOX'
    AND l_quantity < (
        SELECT
            0.2 * avg(l_quantity)
        FROM
            lineitem
        WHERE
            l_partkey = p_partkey);
