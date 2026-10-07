"""`make index-fks`: add an index on every foreign key that no existing index covers.

PostgreSQL indexes primary keys automatically but not foreign keys. For the analytic queries in this
repo that rarely matters (they scan and hash-join whole tables), so the loader does not create them
by default. They help point lookups and nested-loop plans, at the cost of disk space and load time.

TPC-H's constraints.sql already indexes its foreign keys, so in practice this adds TPC-DS's (95 at
the time of writing). The indexes are lost when the database is reloaded; run this again afterwards.
"""

from psycopg import sql

from .benchmarks import Benchmark
from .pg import connect, log
from .settings import Settings

# Foreign keys in the public schema for which no index starts with the key's columns, in key order.
# An index on (a, b) covers a foreign key on (a) or (a, b), but not one on (b).
# conkey is the key's column numbers; indkey (cast to an array) is the index's, compared as a prefix.
UNINDEXED_FKS = """
SELECT c.conrelid::regclass::text AS table_name,
       array_agg(a.attname ORDER BY k.ord) AS columns
FROM pg_constraint c
CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
WHERE c.contype = 'f'
  AND c.connamespace = 'public'::regnamespace
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i
      WHERE i.indrelid = c.conrelid
        AND (i.indkey::int2[])[0:cardinality(c.conkey) - 1] = c.conkey
  )
GROUP BY c.oid, c.conrelid
ORDER BY 1, 2
"""


def index_foreign_keys(benchmark: Benchmark, settings: Settings) -> None:
    """Create the missing foreign-key indexes in the benchmark's database, then refresh statistics."""
    database = settings.database_for(benchmark.name)
    with connect(settings, database) as conn:
        missing = conn.execute(UNINDEXED_FKS).fetchall()
        log(f"{benchmark.title}: {len(missing)} foreign keys without an index.")
        for table, columns in missing:
            # PostgreSQL truncates identifiers to 63 bytes; truncate ourselves so the name is predictable.
            name = f"{table}_{'_'.join(columns)}_idx"[:63]
            # IF NOT EXISTS makes re-running harmless.
            conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({})").format(
                sql.Identifier(name), sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
            ))
            log(f"  created {name}")
        # New indexes change the planner's options; refresh its statistics.
        conn.execute("ANALYZE")
        size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    log(f"{benchmark.title}: done, database is now {size}.")
