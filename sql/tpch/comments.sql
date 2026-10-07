-- TPC-H table and column descriptions, based on the TPC-H specification.

COMMENT ON TABLE region IS 'The 5 world regions (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST). Fixed size at every scale factor.';
COMMENT ON COLUMN region.r_regionkey IS 'Region identifier (0-4).';
COMMENT ON COLUMN region.r_name IS 'Region name.';
COMMENT ON COLUMN region.r_comment IS 'Free-text comment (generated filler).';

COMMENT ON TABLE nation IS 'The 25 nations that customers and suppliers belong to. Fixed size at every scale factor.';
COMMENT ON COLUMN nation.n_nationkey IS 'Nation identifier (0-24).';
COMMENT ON COLUMN nation.n_name IS 'Nation name, e.g. GERMANY.';
COMMENT ON COLUMN nation.n_regionkey IS 'Region the nation belongs to.';
COMMENT ON COLUMN nation.n_comment IS 'Free-text comment (generated filler).';

COMMENT ON TABLE part IS 'Product catalogue: the parts the company sells. 200,000 x scale factor rows.';
COMMENT ON COLUMN part.p_partkey IS 'Part identifier.';
COMMENT ON COLUMN part.p_name IS 'Part name, made of five colour words, e.g. "goldenrod lavender spring chocolate lace".';
COMMENT ON COLUMN part.p_mfgr IS 'Manufacturer, Manufacturer#1 to Manufacturer#5.';
COMMENT ON COLUMN part.p_brand IS 'Brand, Brand#MN where M is the manufacturer number.';
COMMENT ON COLUMN part.p_type IS 'Part type: three words, e.g. "PROMO BURNISHED COPPER" (finish, process, material).';
COMMENT ON COLUMN part.p_size IS 'Part size, 1-50.';
COMMENT ON COLUMN part.p_container IS 'Packaging, e.g. "SM BOX", "LG CASE", "JUMBO PKG".';
COMMENT ON COLUMN part.p_retailprice IS 'List price of the part.';
COMMENT ON COLUMN part.p_comment IS 'Free-text comment (generated filler).';

COMMENT ON TABLE supplier IS 'Suppliers the company buys parts from. 10,000 x scale factor rows.';
COMMENT ON COLUMN supplier.s_suppkey IS 'Supplier identifier.';
COMMENT ON COLUMN supplier.s_name IS 'Supplier name, Supplier#000000001 style.';
COMMENT ON COLUMN supplier.s_address IS 'Address (generated random text).';
COMMENT ON COLUMN supplier.s_nationkey IS 'Nation the supplier is based in.';
COMMENT ON COLUMN supplier.s_phone IS 'Phone number; the leading digits encode the nation (country code = nationkey + 10).';
COMMENT ON COLUMN supplier.s_acctbal IS 'Account balance; can be negative.';
COMMENT ON COLUMN supplier.s_comment IS 'Free-text comment. A few contain "Customer ... Complaints" or "Customer ... Recommends" (used by Q16).';

COMMENT ON TABLE partsupp IS 'Which supplier offers which part, at what cost and with how much stock. Each part has 4 suppliers. 800,000 x scale factor rows.';
COMMENT ON COLUMN partsupp.ps_partkey IS 'Part offered.';
COMMENT ON COLUMN partsupp.ps_suppkey IS 'Supplier offering it.';
COMMENT ON COLUMN partsupp.ps_availqty IS 'Quantity the supplier has available.';
COMMENT ON COLUMN partsupp.ps_supplycost IS 'Cost of the part from this supplier (the company''s purchase price).';
COMMENT ON COLUMN partsupp.ps_comment IS 'Free-text comment (generated filler).';

COMMENT ON TABLE customer IS 'Customers who place orders. 150,000 x scale factor rows; about a third never place an order.';
COMMENT ON COLUMN customer.c_custkey IS 'Customer identifier.';
COMMENT ON COLUMN customer.c_name IS 'Customer name, Customer#000000001 style.';
COMMENT ON COLUMN customer.c_address IS 'Address (generated random text).';
COMMENT ON COLUMN customer.c_nationkey IS 'Nation the customer is based in.';
COMMENT ON COLUMN customer.c_phone IS 'Phone number; the first two digits are the country code (nationkey + 10), used by Q22.';
COMMENT ON COLUMN customer.c_acctbal IS 'Account balance; can be negative.';
COMMENT ON COLUMN customer.c_mktsegment IS 'Market segment: AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD or MACHINERY.';
COMMENT ON COLUMN customer.c_comment IS 'Free-text comment (generated filler). Some contain "special ... requests" (used by Q13).';

COMMENT ON TABLE orders IS 'Order headers: one row per customer order. 1,500,000 x scale factor rows, dated 1992-01-01 to 1998-08-02.';
COMMENT ON COLUMN orders.o_orderkey IS 'Order identifier. Sparse: only the first 8 of every 32 key values are used.';
COMMENT ON COLUMN orders.o_custkey IS 'Customer who placed the order.';
COMMENT ON COLUMN orders.o_orderstatus IS 'F = all line items shipped (fulfilled), O = none shipped yet (open), P = partially shipped.';
COMMENT ON COLUMN orders.o_totalprice IS 'Order total: sum over lines of extendedprice x (1 + tax) x (1 - discount).';
COMMENT ON COLUMN orders.o_orderdate IS 'Date the order was placed.';
COMMENT ON COLUMN orders.o_orderpriority IS 'Priority: 1-URGENT, 2-HIGH, 3-MEDIUM, 4-NOT SPECIFIED or 5-LOW.';
COMMENT ON COLUMN orders.o_clerk IS 'Clerk who took the order, Clerk#000000001 style.';
COMMENT ON COLUMN orders.o_shippriority IS 'Shipping priority; always 0 in generated data.';
COMMENT ON COLUMN orders.o_comment IS 'Free-text comment (generated filler).';

COMMENT ON TABLE lineitem IS 'Order lines: the main fact table. One row per part per order, 1-7 lines per order, about 6,000,000 x scale factor rows.';
COMMENT ON COLUMN lineitem.l_orderkey IS 'Order the line belongs to.';
COMMENT ON COLUMN lineitem.l_partkey IS 'Part ordered.';
COMMENT ON COLUMN lineitem.l_suppkey IS 'Supplier the part is sourced from; (l_partkey, l_suppkey) is a partsupp row.';
COMMENT ON COLUMN lineitem.l_linenumber IS 'Line number within the order, starting at 1.';
COMMENT ON COLUMN lineitem.l_quantity IS 'Quantity ordered, 1-50.';
COMMENT ON COLUMN lineitem.l_extendedprice IS 'Gross line amount: quantity x part retail price, before discount and tax.';
COMMENT ON COLUMN lineitem.l_discount IS 'Discount rate, 0.00-0.10. Revenue = l_extendedprice x (1 - l_discount).';
COMMENT ON COLUMN lineitem.l_tax IS 'Tax rate, 0.00-0.08.';
COMMENT ON COLUMN lineitem.l_returnflag IS 'R = returned, A = accepted (received, not returned), N = not yet received.';
COMMENT ON COLUMN lineitem.l_linestatus IS 'F = shipped (fulfilled), O = not yet shipped (open).';
COMMENT ON COLUMN lineitem.l_shipdate IS 'Date the line was shipped.';
COMMENT ON COLUMN lineitem.l_commitdate IS 'Date the company committed to deliver by.';
COMMENT ON COLUMN lineitem.l_receiptdate IS 'Date the customer received the line. Later than l_commitdate means it arrived late.';
COMMENT ON COLUMN lineitem.l_shipinstruct IS 'Shipping instruction: DELIVER IN PERSON, COLLECT COD, NONE or TAKE BACK RETURN.';
COMMENT ON COLUMN lineitem.l_shipmode IS 'Shipping mode: REG AIR, AIR, RAIL, SHIP, TRUCK, MAIL or FOB.';
COMMENT ON COLUMN lineitem.l_comment IS 'Free-text comment (generated filler).';
