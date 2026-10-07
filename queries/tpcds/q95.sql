-- TPC-DS query 95
-- Tables: customer_address, date_dim, web_returns, web_sales, web_site
-- Parameters: the specification's validation values (as used by DuckDB's tpcds extension).
-- PostgreSQL note: the planner underestimates this query's joins and picks nested loops; turning them
-- off for this query only (SET LOCAL) takes it from 27 s to 2.1 s at SF1. The query text is unchanged.

BEGIN;
SET LOCAL enable_nestloop = off;

WITH ws_wh AS
  (SELECT ws1.ws_order_number,
          ws1.ws_warehouse_sk wh1,
          ws2.ws_warehouse_sk wh2
   FROM web_sales ws1,
        web_sales ws2
   WHERE ws1.ws_order_number = ws2.ws_order_number
     AND ws1.ws_warehouse_sk <> ws2.ws_warehouse_sk)
SELECT count(DISTINCT ws_order_number) AS "order count" ,
       sum(ws_ext_ship_cost) AS "total shipping cost" ,
       sum(ws_net_profit) AS "total net profit"
FROM web_sales ws1 ,
     date_dim ,
     customer_address ,
     web_site
WHERE d_date BETWEEN '1999-02-01' AND cast('1999-04-02' AS date)
  AND ws1.ws_ship_date_sk = d_date_sk
  AND ws1.ws_ship_addr_sk = ca_address_sk
  AND ca_state = 'IL'
  AND ws1.ws_web_site_sk = web_site_sk
  AND web_company_name = 'pri'
  AND ws1.ws_order_number IN
    (SELECT ws_order_number
     FROM ws_wh)
  AND ws1.ws_order_number IN
    (SELECT wr_order_number
     FROM web_returns,
          ws_wh
     WHERE wr_order_number = ws_wh.ws_order_number)
ORDER BY count(DISTINCT ws_order_number)
LIMIT 100;

COMMIT;
