"""`make load` / `make load-tpch` / `make load-tpcds`: generate a benchmark and load it into PostgreSQL.

The flow of load(), for one benchmark:

    1. _preflight            refuse very large scale factors unless FORCE=1
    2. _recreate_database    DROP + CREATE the database (C collation)
    3. sql/<b>/schema.sql    create the empty tables
    4. _generate_and_copy    DuckDB generates the data and copies each table into PostgreSQL
    5. constraints.sql       primary keys, foreign keys, indexes (after the data: faster, and validates it)
    6. comments.sql          table and column descriptions
    7. VACUUM ANALYZE        statistics for the query planner
    8. row-count check       PostgreSQL vs. what the generator produced
    9. tpc_meta.load_info    record of this load (read by verify and status)
   10. reader login          create/update it and grant read access

Any failure raises, leaving the database without a tpc_meta.load_info row, which `status` shows as
"incomplete load" and `verify` refuses. Re-running the load starts from step 2 again.
"""

import json
import shutil
import time

import duckdb
from psycopg import sql

from . import __version__
from .benchmarks import Benchmark
from .pg import connect, ensure_reader, grant_reader, log, run_file
from .settings import FORCE_ABOVE_SCALE, WORK, Settings, format_scale

# Created in every loaded database. One row per load; the row_counts column ({"lineitem": 6001215, ...})
# is what `verify` later compares the tables against.
META_DDL = """
CREATE SCHEMA tpc_meta;
CREATE TABLE tpc_meta.load_info (
    benchmark         text        NOT NULL,
    scale_factor      numeric     NOT NULL,
    database          text        NOT NULL,
    loaded_at         timestamptz NOT NULL DEFAULT now(),
    duration_seconds  numeric     NOT NULL,
    generator         text        NOT NULL,
    loader_version    text        NOT NULL,
    row_counts        jsonb       NOT NULL
);
COMMENT ON TABLE tpc_meta.load_info IS 'How and when this database was loaded; read by `make verify` and `make status`.';
"""


def _preflight(benchmark: Benchmark, scale: float, settings: Settings) -> None:
    """Stop before doing anything if the scale factor is above the FORCE threshold and FORCE is not set.

    The disk figure is a rough guide (about 2 GB per scale-factor unit, as measured at SF 1 and 2).
    """
    if scale > FORCE_ABOVE_SCALE and not settings.force:
        raise SystemExit(
            f"{benchmark.title} at scale factor {format_scale(scale)} needs roughly {scale * 2:.0f}+ GB of disk "
            f"and a long load. Re-run with FORCE=1 if that is intended."
        )


def _recreate_database(settings: Settings, database: str) -> None:
    """Drop the database if it exists and create it empty, with C (byte-order) collation.

    WITH (FORCE) disconnects any open sessions (e.g. a psql left open) so the drop cannot hang.
    C collation is what the benchmarks' ORDER BY ... LIMIT answers assume: the image's default
    en_US.utf8 ignores spaces when sorting ("Mountain View" before "Mount Pleasant"), which changes
    which rows make a top-100 cut. template0 is required when choosing a locale different from the
    server default.
    """
    with connect(settings, "postgres") as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LOCALE 'C'").format(sql.Identifier(database)))


def _generate_and_copy(benchmark: Benchmark, scale: float, settings: Settings, database: str) -> dict[str, int]:
    """Generate the data in DuckDB and copy every table into the (already created) PostgreSQL tables.

    DuckDB works in an on-disk file in the `loader-work` volume, so it can spill to disk past its
    memory limit. Its postgres extension ATTACHes the PostgreSQL database as `pg`; an
    `INSERT INTO pg.public.<table> SELECT ...` is then streamed with binary COPY, with no CSV files.

    Returns the number of rows generated per table, summed over chunks. load() checks PostgreSQL
    against it and stores it in tpc_meta.load_info for `verify`.
    """
    work_dir = WORK / benchmark.name
    shutil.rmtree(work_dir, ignore_errors=True)  # leftovers from an interrupted run
    work_dir.mkdir(parents=True)
    duck = duckdb.connect(str(work_dir / "generate.duckdb"))
    try:
        duck.execute(f"SET memory_limit = '{settings.memory_limit}'")
        duck.execute(f"SET threads = {settings.threads}")
        duck.execute(f"SET temp_directory = '{work_dir / 'tmp'}'")
        # Row order inside a table does not matter, and not preserving it lets DuckDB use less memory.
        duck.execute("SET preserve_insertion_order = false")
        # The extensions are installed in the image (see the Dockerfile); LOAD just activates them.
        duck.execute(f"LOAD {benchmark.extension}")
        duck.execute("LOAD postgres")
        duck.execute(f"ATTACH '{settings.dsn(database)}' AS pg (TYPE postgres)")

        counts: dict[str, int] = {}
        # benchmark.steps() generates the data, yielding once per chunk (TPC-H at SF > 1) or once in total.
        for step, _ in enumerate(benchmark.steps(duck, scale), start=1):
            # The tables this step generated, smallest first so progress shows up quickly.
            tables = [r[0] for r in duck.execute(
                "SELECT table_name FROM duckdb_tables() WHERE database_name = current_database() ORDER BY estimated_size"
            ).fetchall()]
            for table in tables:
                # Explicit column lists, so the copy does not depend on column order matching schema.sql.
                columns = [r[0] for r in duck.execute(
                    "SELECT column_name FROM duckdb_columns() WHERE database_name = current_database() "
                    "AND table_name = ? ORDER BY column_index", [table],
                ).fetchall()]
                column_list = ", ".join(columns)
                rows = duck.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                started = time.monotonic()
                duck.execute(f"INSERT INTO pg.public.{table} ({column_list}) SELECT {column_list} FROM {table}")
                # Drop the copied chunk so the next chunk starts with empty tables (and frees disk).
                duck.execute(f"DROP TABLE {table}")
                counts[table] = counts.get(table, 0) + rows
                prefix = f"chunk {step}: " if scale > 1 and benchmark.name == "tpch" else ""
                log(f"  {prefix}{table:<24} {rows:>12,} rows  ({time.monotonic() - started:.1f}s)")
            # Return the dropped tables' space in the work file before the next chunk.
            duck.execute("CHECKPOINT")
        return counts
    finally:
        # Always remove the work file: it is as large as the data set and is never reused.
        duck.close()
        shutil.rmtree(work_dir, ignore_errors=True)


def load(benchmark: Benchmark, settings: Settings) -> None:
    """Generate `benchmark` at the configured scale and load it into a fresh database (see module docstring)."""
    scale = settings.scale_for(benchmark.name)
    database = settings.database_for(benchmark.name)
    _preflight(benchmark, scale, settings)
    started = time.monotonic()
    log(f"{benchmark.title} at scale factor {format_scale(scale)} -> database '{database}'")

    # Steps 2-3: empty database with empty tables (no keys yet: loading into unconstrained tables is fastest).
    _recreate_database(settings, database)
    with connect(settings, database) as conn:
        run_file(conn, benchmark.sql_dir / "schema.sql")
    log("Tables created. Generating and copying data:")

    # Step 4.
    counts = _generate_and_copy(benchmark, scale, settings, database)
    log(f"Copied {sum(counts.values()):,} rows. Adding keys and indexes:")

    with connect(settings, database) as conn:
        # Steps 5-7. Adding a foreign key checks every existing row, so a broken relationship fails here.
        run_file(conn, benchmark.sql_dir / "constraints.sql", verbose=True)
        run_file(conn, benchmark.sql_dir / "comments.sql")
        log("Descriptions added. Running VACUUM ANALYZE...")
        conn.execute("VACUUM ANALYZE")

        # Step 8: every generated row must have arrived.
        actual = {t: conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0] for t in counts}
        mismatched = {t: (counts[t], actual[t]) for t in counts if counts[t] != actual[t]}
        if mismatched:
            raise SystemExit(f"Row counts differ between generator and PostgreSQL (generated, loaded): {mismatched}")

        # Step 9: written last among the data steps, so its presence means the load completed.
        for statement in META_DDL.split(";\n"):
            if statement.strip():
                conn.execute(statement)
        conn.execute(
            "INSERT INTO tpc_meta.load_info (benchmark, scale_factor, database, duration_seconds, generator, loader_version, row_counts) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (benchmark.name, scale, database, round(time.monotonic() - started, 1),
             f"duckdb {duckdb.__version__} ({benchmark.extension} extension)", __version__, json.dumps(counts)),
        )

        # Step 10: after every table (including tpc_meta.load_info) exists, so the grants cover them all.
        ensure_reader(settings)
        grant_reader(conn, settings, database)
        size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]

    log(f"Done: {benchmark.title} SF{format_scale(scale)} loaded into '{database}' ({size}) in {time.monotonic() - started:.0f}s.")
