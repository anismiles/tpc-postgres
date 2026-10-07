"""Small PostgreSQL helpers shared by the command modules: connecting, running SQL files, logins."""

import re
import time
from pathlib import Path

import psycopg
from psycopg import sql

from .settings import Settings


def log(message: str) -> None:
    """Print a timestamped progress line; flushed at once so `docker compose run` shows it live."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def connect(settings: Settings, database: str, *, autocommit: bool = True) -> psycopg.Connection:
    """Open a connection to `database` as the admin login.

    Autocommit is the default because several statements we run cannot be inside a transaction
    (CREATE / DROP DATABASE, VACUUM), and each DDL statement should take effect on its own.
    """
    return psycopg.connect(settings.dsn(database), autocommit=autocommit)


def database_exists(settings: Settings, database: str) -> bool:
    """True if `database` exists on the server (checked from the always-present `postgres` database)."""
    with connect(settings, "postgres") as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone() is not None


def statements(path: Path) -> list[str]:
    """Split a SQL file into individual statements.

    Lines starting with `--` are dropped, then the text is split on a semicolon at the end of a line.
    That simple rule is enough for our own files in sql/, where a semicolon inside a string literal is
    never followed by a newline. psycopg sends one statement per call, hence the splitting.
    """
    text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*\n", text + "\n") if s.strip()]


def run_file(conn: psycopg.Connection, path: Path, *, verbose: bool = False) -> None:
    """Execute every statement in a SQL file, stopping at the first error.

    With verbose=True each statement's first line and duration are logged (used for constraints.sql,
    where adding keys and indexes to the big tables is the slow part of a load).
    """
    for statement in statements(path):
        started = time.monotonic()
        conn.execute(statement)
        if verbose:
            log(f"  {statement.splitlines()[0][:90]}  ({time.monotonic() - started:.1f}s)")


def ensure_reader(settings: Settings) -> None:
    """Create the read-only login if it does not exist, or reset its password if it does.

    Running this on every load means a changed READER_PASSWORD in .env applies at the next load.
    Roles are server-wide, so this connects to the `postgres` database.
    """
    with connect(settings, "postgres") as conn:
        role = sql.Identifier(settings.reader_user)
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.reader_user,)).fetchone()
        verb = sql.SQL("ALTER") if exists else sql.SQL("CREATE")
        # sql.Identifier / sql.Literal quote the name and password safely.
        conn.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(verb, role, sql.Literal(settings.reader_password)))


def grant_reader(conn: psycopg.Connection, settings: Settings, database: str) -> None:
    """Let the read-only login connect to `database` and SELECT from its tables (public and tpc_meta).

    Grants only cover tables that exist when they run, so this is called at the end of a load.
    The reader gets no CREATE rights: it cannot create or change anything.
    """
    role = sql.Identifier(settings.reader_user)
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public, tpc_meta TO {}").format(role))
    conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public, tpc_meta TO {}").format(role))
