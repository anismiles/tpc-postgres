# tpc-postgres

PostgreSQL in Docker, loaded with the two standard analytics benchmark datasets: TPC-H (a wholesale
parts supplier) and TPC-DS (a retailer selling through stores, a catalog and the web). One command
generates the data with the official TPC generators, loads it, declares every primary and foreign
key, and adds a description to every column. Every machine gets the same data. Use it to learn and
teach SQL, to test BI tools, semantic layers and text-to-SQL agents, to build demos, or to compare
PostgreSQL settings.

```bash
git clone https://github.com/anismiles/tpc-postgres.git && cd tpc-postgres
make load        # ~1 minute: starts PostgreSQL and loads both databases (~4 GB)
```

Connect to `localhost:5432`, database `tpch` or `tpcds`, user `reader`, password `reader`.
Open [erd.html](erd.html) in a browser to explore both schemas: every table, column, key and
description, with search.

## What's inside

Both datasets are synthetic. Their structure and statistics are realistic: skewed values,
seasonality, missing data, history. Their names and values are not (`Customer#000000001`, brand
`exportischolar #2`). Row counts are at the default size (scale factor 1).

### TPC-H: a wholesale parts supplier · database `tpch`

A company sells industrial parts worldwide. Customers belong to five market segments (automobile,
building, furniture, household, machinery) and place orders from 1992 to 1998. An order has one to
seven line items. Each line buys a quantity of one part from one of the four suppliers that stock it,
and records price, discount, tax, shipping mode (air, rail, truck, mail …) and the ship, promised and
received dates. Late deliveries and returns follow from these. Suppliers set their own cost and
available quantity per part. Customers and suppliers span 25 nations in 5 regions.

| Table | Rows | What it holds |
|---|---|---|
| `lineitem` | 6.0M | Order lines, the main fact table: quantity, price, discount, dates, return flag |
| `orders` | 1.5M | Order header: customer, date, status, priority, total |
| `partsupp` | 800k | Supplier cost and stock for each part |
| `part` | 200k | Product catalogue: brand, type, size, container, list price |
| `customer` | 150k | Buyers: nation, market segment, account balance |
| `supplier` | 10k | Suppliers: nation, account balance |
| `nation`, `region` | 25, 5 | Geography shared by customers and suppliers |

Typical questions:
- revenue and margin by region and year
- cheapest supplier for a part
- late orders and the suppliers behind them
- effect of discounts and promotions
- largest customers
- returned items and lost revenue

The 22 benchmark queries in [`queries/tpch/`](queries/tpch/) are reports of this kind.

### TPC-DS: a retailer selling through three channels · database `tpcds`

A retailer sells ten categories of goods (books, children, electronics, home, jewelry, men, music,
shoes, sports, women) through three channels: stores, a mail-order catalog with call centers and
warehouses, and web sites. Each sale records the item, customer, date and time, price, discounts and
coupons, tax, shipping and profit. Catalog and web orders record separate bill-to and ship-to
customers. Each return links to its sale and records a reason ("did not fit", "package was damaged"
…) and how the refund was paid. Customers have demographics (gender, marital status, education,
credit rating) and household profiles (income band, dependants, vehicles). Promotions record the
media they used (TV, radio, email, catalog …). Inventory is counted weekly per item and warehouse.
Sales run from 1998 to 2003 and peak at holidays. Products, stores and sites keep their history.

| Tables | Rows | What they hold |
|---|---|---|
| `store_sales`, `catalog_sales`, `web_sales` | 2.9M, 1.4M, 720k | Sales per channel, one row per item sold |
| `store_returns`, `catalog_returns`, `web_returns` | 288k, 144k, 72k | Returns per channel, linked to the sale |
| `inventory` | 11.7M | Weekly stock on hand per item and warehouse |
| `customer`, `customer_address`, `customer_demographics`, `household_demographics`, `income_band` | 100k, 50k, 1.9M, 7.2k, 20 | Who buys |
| `item`, `promotion` | 18k, 300 | What sells, and how it is promoted |
| `store`, `call_center`, `catalog_page`, `web_site`, `web_page`, `warehouse`, `ship_mode` | 12, 6, 12k, 30, 60, 5, 20 | Where and how it sells and ships |
| `date_dim`, `time_dim`, `reason` | 73k, 86k, 35 | Calendar, time of day, return reasons |

Typical questions:
- channel comparison by category and region
- best customers and what they buy
- promotion response by demographic
- return rates by item, store and reason
- stock-outs during promotions
- year-over-year growth and holiday peaks

The 99 benchmark queries in [`queries/tpcds/`](queries/tpcds/) cover these.

## Requirements

- Docker with Compose and at least 4 GB of memory:
  - macOS (Apple Silicon or Intel): [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
    (set memory in Settings → Resources), or [OrbStack](https://orbstack.dev)
  - Linux: [Docker Engine](https://docs.docker.com/engine/install/) with the Compose plugin
  - Windows: [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with WSL 2; run the commands in a WSL terminal
- `make` and `git`: on macOS, `xcode-select --install`; on Linux, your package manager
  (`sudo apt install make git`)
- About 5 GB of free disk at the default size (see [Choosing a size](#choosing-a-size))

The data is generated inside a container. Your machine needs no Python, database server or compiler.

## Using it

### Commands

| Command | What it does |
|---|---|
| `make load` | Generates and loads both databases (`make load-tpch` / `make load-tpcds` for one). Replaces existing data. |
| `make verify` | Checks row counts and keys, runs every benchmark query and compares its result with the official answers (TPC-H) or a reference run (TPC-DS) |
| `make status` | Shows what is loaded: scale, size, rows, load time |
| `make psql-tpch` / `make psql-tpcds` | Opens psql as the read-only `reader` (`\dt` lists tables, `\d+ <table>` shows column descriptions) |
| `make index-fks` | Adds an index on every foreign key (optional) |
| `make up` / `make down` | Starts / stops PostgreSQL and keeps the data |
| `make reset` | Stops PostgreSQL and deletes all loaded data |
| `make logs` / `make build` | Follows the PostgreSQL log / rebuilds the loader image |

### Connecting

`make psql-tpch` and `make psql-tpcds` open `psql` on a database as the read-only user. They run
inside the PostgreSQL container, so you install nothing.

```bash
make psql-tpch
make psql-tpcds
```

In psql, `\dt` lists the tables, `\d+ lineitem` shows a table's columns and descriptions, `\x`
toggles vertical output and `\q` quits.

Other SQL and BI clients (DBeaver, DataGrip, pgAdmin, …) connect with these defaults:

| Setting | Default |
|---|---|
| Host / port | `localhost` / `5432` |
| Databases | `tpch`, `tpcds` |
| Read-only user / password | `reader` / `reader` |
| Admin user / password | `postgres` / `postgres` |

### Choosing a size

Each database has a scale factor (SF). Set it in `.env` or on the command line:

| Preset | SF | Load time (both) | Disk (both) |
|---|---|---|---|
| `tiny` | 0.01 | ~4 s | 80 MB |
| `small` | 0.1 | ~10 s | 370 MB |
| `standard` (default) | 1 | ~1 min | 3.9 GB |
| `large` | 10 | ~10–15 min (estimate) | ~40 GB (estimate) |

```bash
make load PRESET=small            # both databases at SF 0.1
make load-tpch TPCH_SCALE=3       # any number; above 10 needs FORCE=1
```

TPC-DS needs SF 1 or more to be representative. Smaller sizes have a single store.

### Configuration

Every setting has a default. To change one, copy the template and edit `.env`. Command-line values
(`make load TPCH_SCALE=3`) override `.env`.

```bash
cp .env.example .env
```

| Setting | Default | What it does |
|---|---|---|
| `POSTGRES_PORT` | `5432` | Port on your machine. Change it if another PostgreSQL uses 5432. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | `postgres` / `postgres` | Admin login, used by the loader. Set on the first start; change it before the first `make up`, or run `make reset` (deletes the data). |
| `READER_USER` / `READER_PASSWORD` | `reader` / `reader` | Read-only login for everyone else. Applied on every load. |
| `POSTGRES_VERSION` | `17` | PostgreSQL image version |
| `TPCH_SCALE` / `TPCDS_SCALE` | `1` | Size of each database: a number or a preset (see [Choosing a size](#choosing-a-size)) |
| `PRESET` | – | Sets both sizes: `tiny`, `small`, `standard`, `large` |
| `KEEP_SCALES` | `false` | `true` names databases by size (`tpch_sf1`, `tpch_sf10`, …) so several sizes coexist |
| `FORCE` | – | `1` allows sizes above 10 |
| `LOADER_MEMORY_LIMIT` | `4GB` | Generator memory before it spills to disk. Lower it if large loads get killed. |
| `LOADER_THREADS` | all CPUs | Generator threads |
| `QUERY_TIMEOUT` | `300` | Seconds per query in `make verify` |
| `PG_SHARED_BUFFERS`, `PG_EFFECTIVE_CACHE_SIZE`, `PG_WORK_MEM`, `PG_MAINTENANCE_WORK_MEM`, `PG_PARALLEL_WORKERS` | laptop-sized | PostgreSQL memory and parallelism |

The default passwords suit local use. Change them before you expose the port. If a load stops
halfway, run it again: each load starts from a fresh database.

[loader/README.md](loader/README.md) explains how the loader works.

## Licence and TPC notice

The code is MIT-licensed ([LICENSE](LICENSE)). TPC-H and TPC-DS are trademarks of the Transaction
Processing Performance Council. The data comes from the TPC generators embedded in DuckDB, and the
schemas and queries follow the TPC specifications. Results from this repository are not official TPC
benchmark results. See [tpc.org](https://www.tpc.org).
