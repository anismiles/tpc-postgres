-- TPC-H keys and indexes for PostgreSQL. Applied after the data is loaded.

-- Primary keys (from the TPC-H specification).
ALTER TABLE region   ADD CONSTRAINT region_pkey   PRIMARY KEY (r_regionkey);
ALTER TABLE nation   ADD CONSTRAINT nation_pkey   PRIMARY KEY (n_nationkey);
ALTER TABLE part     ADD CONSTRAINT part_pkey     PRIMARY KEY (p_partkey);
ALTER TABLE supplier ADD CONSTRAINT supplier_pkey PRIMARY KEY (s_suppkey);
ALTER TABLE partsupp ADD CONSTRAINT partsupp_pkey PRIMARY KEY (ps_partkey, ps_suppkey);
ALTER TABLE customer ADD CONSTRAINT customer_pkey PRIMARY KEY (c_custkey);
ALTER TABLE orders   ADD CONSTRAINT orders_pkey   PRIMARY KEY (o_orderkey);
ALTER TABLE lineitem ADD CONSTRAINT lineitem_pkey PRIMARY KEY (l_orderkey, l_linenumber);

-- Foreign keys (the 8 relationships in the TPC-H kit's dss.ri).
ALTER TABLE nation   ADD CONSTRAINT nation_n_regionkey_fkey   FOREIGN KEY (n_regionkey) REFERENCES region (r_regionkey);
ALTER TABLE supplier ADD CONSTRAINT supplier_s_nationkey_fkey FOREIGN KEY (s_nationkey) REFERENCES nation (n_nationkey);
ALTER TABLE customer ADD CONSTRAINT customer_c_nationkey_fkey FOREIGN KEY (c_nationkey) REFERENCES nation (n_nationkey);
ALTER TABLE partsupp ADD CONSTRAINT partsupp_ps_partkey_fkey  FOREIGN KEY (ps_partkey)  REFERENCES part (p_partkey);
ALTER TABLE partsupp ADD CONSTRAINT partsupp_ps_suppkey_fkey  FOREIGN KEY (ps_suppkey)  REFERENCES supplier (s_suppkey);
ALTER TABLE orders   ADD CONSTRAINT orders_o_custkey_fkey     FOREIGN KEY (o_custkey)   REFERENCES customer (c_custkey);
ALTER TABLE lineitem ADD CONSTRAINT lineitem_l_orderkey_fkey  FOREIGN KEY (l_orderkey)  REFERENCES orders (o_orderkey);
ALTER TABLE lineitem ADD CONSTRAINT lineitem_partsupp_fkey    FOREIGN KEY (l_partkey, l_suppkey) REFERENCES partsupp (ps_partkey, ps_suppkey);

-- Direct links from lineitem to part and supplier. Implied by lineitem_partsupp_fkey, but declared
-- so that tools which discover joins from foreign keys find the obvious paths.
ALTER TABLE lineitem ADD CONSTRAINT lineitem_l_partkey_fkey   FOREIGN KEY (l_partkey)   REFERENCES part (p_partkey);
ALTER TABLE lineitem ADD CONSTRAINT lineitem_l_suppkey_fkey   FOREIGN KEY (l_suppkey)   REFERENCES supplier (s_suppkey);

-- Indexes on foreign-key columns. PostgreSQL does not create these automatically; without the
-- lineitem ones, the correlated subqueries in Q17 and Q20 rescan lineitem once per outer row.
CREATE INDEX lineitem_l_partkey_l_suppkey_idx ON lineitem (l_partkey, l_suppkey);
CREATE INDEX lineitem_l_suppkey_idx           ON lineitem (l_suppkey);
CREATE INDEX orders_o_custkey_idx             ON orders (o_custkey);
CREATE INDEX partsupp_ps_suppkey_idx          ON partsupp (ps_suppkey);
CREATE INDEX customer_c_nationkey_idx         ON customer (c_nationkey);
CREATE INDEX supplier_s_nationkey_idx         ON supplier (s_nationkey);
CREATE INDEX nation_n_regionkey_idx           ON nation (n_regionkey);
