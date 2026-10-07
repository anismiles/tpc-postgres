-- TPC-DS query 84
-- Tables: customer, customer_address, customer_demographics, household_demographics, income_band, store_returns
-- Parameters: the specification's validation values (as used by DuckDB's tpcds extension).
-- PostgreSQL note: c_last_name and c_first_name are CHAR(n) per the specification, so the
-- concatenation keeps their padding ('Benson                        , Floyd'). Use rtrim() for tidy output.

SELECT c_customer_id AS customer_id ,
       concat(concat(coalesce(c_last_name, '') , ', '), coalesce(c_first_name, '')) AS customername
FROM customer ,
     customer_address ,
     customer_demographics ,
     household_demographics ,
     income_band ,
     store_returns
WHERE ca_city = 'Edgewood'
  AND c_current_addr_sk = ca_address_sk
  AND ib_lower_bound >= 38128
  AND ib_upper_bound <= 38128 + 50000
  AND ib_income_band_sk = hd_income_band_sk
  AND cd_demo_sk = c_current_cdemo_sk
  AND hd_demo_sk = c_current_hdemo_sk
  AND sr_cdemo_sk = cd_demo_sk
ORDER BY c_customer_id NULLS FIRST
LIMIT 100;
