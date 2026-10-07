"""`make status`: list the TPC databases on the server and how they were loaded.

Reads only: the database list from the server catalog, then each database's size and its
tpc_meta.load_info record (written by load.py at the end of a successful load).
"""

from .pg import connect
from .settings import Settings


def status(settings: Settings) -> None:
    """Print one line per TPC database: scale factor, size on disk, total rows and load time."""
    with connect(settings, "postgres") as conn:
        # tpch, tpcds, and the KEEP_SCALES variants such as tpch_sf0_1 or tpcds_sf10.
        databases = [r[0] for r in conn.execute(
            "SELECT datname FROM pg_database WHERE datname ~ '^tpc(h|ds)(_sf[0-9_]+)?$' ORDER BY datname"
        ).fetchall()]
    if not databases:
        print("No TPC databases loaded yet. Run `make load`.")
        return

    print(f"{'database':<18} {'scale':>7} {'size':>10} {'rows':>14}  loaded at")
    for database in databases:
        with connect(settings, database) as conn:
            size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
            # No load_info table means the load was interrupted before it finished.
            has_info = conn.execute("SELECT to_regclass('tpc_meta.load_info')").fetchone()[0]
            info = conn.execute(
                # Total rows = sum of the per-table counts stored as JSON at load time.
                "SELECT scale_factor, loaded_at, (SELECT sum(value::bigint) FROM jsonb_each_text(row_counts)) "
                "FROM tpc_meta.load_info ORDER BY loaded_at DESC LIMIT 1"
            ).fetchone() if has_info else None
        if info:
            # normalize() prints the numeric scale factor as 1 rather than 1.0000.
            print(f"{database:<18} {info[0].normalize():>7} {size:>10} {info[2]:>14,}  {info[1]:%Y-%m-%d %H:%M}")
        else:
            print(f"{database:<18} {'?':>7} {size:>10} {'?':>14}  (incomplete load)")
