# loader

The program that generates the TPC-H and TPC-DS data and loads it into PostgreSQL, plus the
`verify`, `status` and `index-fks` commands. It runs in its own container, so nobody needs
Python, DuckDB or a C compiler on their machine.

```
loader/
├── Dockerfile          the loader image: Python 3.12 + DuckDB + psycopg, DuckDB extensions pre-installed
├── requirements.txt    duckdb (pinned exactly) and psycopg
└── tpc_loader/         the Python package
    ├── __init__.py     package version (recorded with every load)
    ├── __main__.py     command line: parses the command and calls the module below
    ├── settings.py     settings from environment variables (.env), scale factors, presets
    ├── benchmarks.py   what differs between TPC-H and TPC-DS: generator, answers, file locations
    ├── pg.py           PostgreSQL helpers: connect, run a SQL file, the read-only login
    ├── load.py         `load`:      generate the data and load it into a fresh database
    ├── verify.py       `verify`:    row counts, keys, and query results against expected answers
    ├── status.py       `status`:    what is loaded, at what scale and size
    └── indexes.py      `index-fks`: optional indexes on foreign-key columns
```

## How a `make` command reaches the Python code

```
make load-tpch TPCH_SCALE=0.1
  │  Makefile: `export`s its variables, then runs
  ▼
docker compose run --rm loader load tpch
  │  docker-compose.yml: starts postgres if needed, passes TPCH_SCALE etc. as environment variables,
  │  mounts the repository at /repo and the `loader-work` volume at /work
  ▼
python -m tpc_loader load tpch          (the image's ENTRYPOINT)
  │  __main__.py: Settings.from_env() reads the variables; select("tpch") picks the benchmark
  ▼
load.load(BENCHMARKS["tpch"], settings)
```

| Make target | Loader command | Module · function |
|---|---|---|
| `make load` | `load all` | `load.py` · `load()` for TPC-H, then TPC-DS |
| `make load-tpch` / `make load-tpcds` | `load tpch` / `load tpcds` | `load.py` · `load()` |
| `make verify` | `verify all` | `verify.py` · `verify()` for each |
| `make verify-tpch` / `make verify-tpcds` | `verify tpch` / `verify tpcds` | `verify.py` · `verify()` |
| `make status` | `status` | `status.py` · `status()` |
| `make index-fks` | `index-fks all` | `indexes.py` · `index_foreign_keys()` |

The other targets (`up`, `down`, `build`, `psql-*`, `logs`, `reset`) call Docker directly and never
run the loader.

You can also run the loader yourself, which gives access to options the Makefile does not expose:

```bash
docker compose run --rm loader --help
docker compose run --rm loader verify tpcds --skip-queries        # row counts and keys only
docker compose run --rm loader verify tpch --no-reference         # run queries without comparing results
docker compose run --rm -e TPCDS_SCALE=0.1 loader load tpcds      # settings as environment variables
```

## Modules

### `__main__.py`: command line

Defines the commands with `argparse`, builds the `Settings`, and loops over the selected benchmarks
(`tpch`, `tpcds`, or `all`, which means both, TPC-H first). Command modules are imported only when
used. `load` stops at the first failure; `verify` checks every benchmark and then exits with code 1 if
any failed, which is what makes `make verify` and CI fail.

### `settings.py`: configuration

All configuration is environment variables, documented in `.env.example`. `Settings.from_env()`
reads them once. Notable pieces:

- `parse_scale()` accepts numbers or the presets `tiny` (0.01), `small` (0.1), `standard` (1),
  `large` (10). `PRESET` overrides both `TPCH_SCALE` and `TPCDS_SCALE`.
- `database_for()` gives the database name: `tpch` / `tpcds`, or `tpch_sf0_1` style with
  `KEEP_SCALES=true`. Every command uses it, so they all address the same database.
- `dsn()` builds the connection string used both by psycopg and by DuckDB's postgres extension.
- `REPO` (`/repo`) and `WORK` (`/work`) are the mounted repository and the scratch volume.

### `benchmarks.py`: the two benchmarks

A `Benchmark` describes one benchmark: its DuckDB extension, its generator, the scale factors with
official answers, and the `sql/` and `queries/` folders. The generator is a Python generator function
that yields once per chunk:

- TPC-H (`_tpch_steps`): split into about one chunk per scale-factor unit with dbgen's
  `children`/`step` parameters, so memory stays flat at large scales. The chunks are disjoint slices
  that add up to exactly the full data set.
- TPC-DS (`_tpcds_steps`): one step; dsdgen cannot be chunked, so DuckDB spills to disk instead.

### `pg.py`: PostgreSQL helpers

`connect()` (autocommit, as the admin login), `database_exists()`, `run_file()` (splits a SQL file on
end-of-line semicolons and runs each statement), `ensure_reader()` / `grant_reader()` (the read-only
login), and `log()` (timestamped progress output).

### `load.py`: `load`

For one benchmark:

1. Refuse scale factors above 10 unless `FORCE=1`.
2. Drop and recreate the database with C (byte-order) collation, which the benchmarks' sorted answers assume.
3. Create the tables from `sql/<benchmark>/schema.sql`.
4. Generate with DuckDB into an on-disk work file in `/work`, `ATTACH` PostgreSQL through DuckDB's
   postgres extension, and copy each table with `INSERT INTO pg.public.<table> SELECT ...` (binary
   COPY under the hood, no CSV files). For chunked TPC-H, each chunk is copied and dropped before
   the next one is generated.
5. Add keys and indexes (`constraints.sql`) after the data: faster than loading into constrained
   tables, and adding each foreign key validates every row.
6. Add descriptions (`comments.sql`), then `VACUUM ANALYZE`.
7. Compare PostgreSQL's row counts with what DuckDB generated.
8. Write `tpc_meta.load_info` (scale, time, generator version, row counts per table). It is written
   last, so a database without it is an incomplete load.
9. Create or update the `reader` login and grant it read access.

### `verify.py`: `verify`

1. Row counts against `tpc_meta.load_info`.
2. Primary and foreign key counts against `constraints.sql`, all validated.
3. Every file in `queries/<benchmark>/`, with `statement_timeout = QUERY_TIMEOUT`, compared with:
   - the official TPC answers (`tpch_answers()`) for TPC-H at SF 0.01, 0.1 and 1, or otherwise
   - a reference run: the data is generated again in DuckDB, which is deterministic and so
     identical, and DuckDB's own text of each query is run on it.

Values are compared loosely about representation: numbers within a relative 1e-6, text ignoring
surrounding spaces, and rows in any order if they tie on the ORDER BY. Results that differ for an
understood reason are listed in `KNOWN_DIFFERENCES` with that reason; they are reported but do not
fail. Query files may wrap the query in `BEGIN; SET LOCAL ...; COMMIT;`; `_run_query_file` runs each
statement and keeps the rows of the SELECT.

### `status.py`: `status`

Lists the TPC databases on the server with their scale factor, size, total rows and load time, read
from `tpc_meta.load_info`. Databases without that record are shown as an incomplete load.

### `indexes.py`: `index-fks`

Finds foreign keys whose columns are not the leading columns of any index, creates an index for each,
and runs `ANALYZE`. Optional: the analytic queries mostly scan whole tables, so these mainly help
point lookups. A reload removes them.


## Data flow

```
                DuckDB (in the loader container)                         PostgreSQL
 ┌────────────────────────────────────────────────────────┐        ┌─────────────────────┐
 │ tpch / tpcds extension ──generate──▶ /work/*.duckdb    │        │ database tpch/tpcds │
 │                                          │             │ binary │  tables (schema.sql)│
 │ postgres extension: ATTACH ... AS pg ◀───┘  INSERT ... ├──COPY─▶│  + keys, comments   │
 └────────────────────────────────────────────────────────┘        │  + tpc_meta         │
                                                                   └─────────────────────┘
 verify: tpch_answers() / regenerated data + tpch_queries()/tpcds_queries()  ◀──compare──  queries/*.sql
```

## Changing things

| To change… | Edit | Then |
|---|---|---|
| Python code | `tpc_loader/*.py` | nothing: the code is mounted, the next `make …` uses it |
| Dependencies or the DuckDB version | `requirements.txt` | `make build`, then `make load verify` |
| Tables, keys or descriptions | `sql/<benchmark>/*.sql` | `make load`, `make verify`; update the `DATA` block in `erd.html` |
| A query | `queries/<benchmark>/qNN.sql` | `make verify` |
| A default setting | `.env.example`, `settings.py` and `docker-compose.yml` together | |

The DuckDB version is pinned exactly because it decides the generated data, the query texts used by
the reference run, and the answer sets. After upgrading it, run `make load` and `make verify` at SF1.

Lint with `ruff check loader/` (configuration in `ruff.toml` at the repository root; CI runs it).
