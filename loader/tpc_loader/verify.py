"""`make verify` / `make verify-tpch` / `make verify-tpcds`: check that a loaded database is correct.

verify() runs three checks on one benchmark's database:

    1. Row counts   every table has the row count recorded in tpc_meta.load_info at load time.
    2. Keys         the number of primary and foreign keys matches constraints.sql, all validated.
    3. Queries      every file in queries/<benchmark>/ runs within QUERY_TIMEOUT, and its result is
                    compared with an expected result (skipped with --skip-queries).

Expected query results come from, in order of preference:

    a. the official TPC answer set, which DuckDB ships for TPC-H at SF 0.01, 0.1 and 1
       (_official_answers);
    b. otherwise a reference run (_reference_results): the data is generated again in DuckDB
       (generation is deterministic, so it is identical to what was loaded) and DuckDB's own copy of
       each query is run on it. Disabled with --no-reference, which then only checks that queries run.

verify() returns True/False rather than raising, so `verify all` checks both benchmarks before
__main__ turns a failure into a non-zero exit code.
"""

import csv
import io
import math
import re
import shutil
import time
from datetime import date, datetime
from decimal import Decimal

import duckdb
import psycopg
from psycopg import sql

from .benchmarks import Benchmark
from .pg import connect, database_exists, log
from .settings import WORK, Settings, format_scale

# Query results that legitimately differ from the reference, keyed by (benchmark, query number), with
# the reason. They are reported as "differs as expected: <reason>" and do not fail verification.
KNOWN_DIFFERENCES = {
    ("tpcds", 84): "names are CHAR(n) per the spec, and PostgreSQL keeps their padding when concatenating "
                   "('Benson                        , Floyd'); DuckDB stores them as VARCHAR ('Benson, Floyd')",
}


def _same_value(actual: object, expected: object) -> bool:
    """Compare one PostgreSQL value with one expected value.

    `expected` is a string when it comes from an official answer file, or a Python value when it comes
    from a DuckDB reference run, so the comparison is deliberately loose about representation:
    - NULL matches NULL, or an empty field in an answer file;
    - numbers match within a relative tolerance of 1e-6 (PostgreSQL NUMERIC vs. DuckDB DOUBLE averages);
    - dates compare as dates;
    - everything else compares as text with surrounding spaces removed (CHAR(n) values are padded).
    """
    if actual is None or expected is None:
        return (actual is None or actual == "") and (expected is None or expected in ("", "NULL"))
    if isinstance(actual, (int, float, Decimal)):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
        except (TypeError, ValueError):
            return False
    if isinstance(actual, (date, datetime)) and isinstance(expected, (date, datetime)):
        return actual == expected
    return str(actual).strip() == str(expected).strip()


def _same_rows(actual: list[tuple], expected: list) -> bool:
    """True if two result sets have the same rows, in the same order or (failing that) in any order.

    The unordered fallback covers rows that tie on the ORDER BY columns, which engines may return in
    a different order. It does not cover ties at a LIMIT boundary, where a different row is included.
    """
    if len(actual) != len(expected):
        return False

    def equal(a: list, b: list) -> bool:
        return all(len(x) == len(y) and all(_same_value(v, e) for v, e in zip(x, y, strict=True)) for x, y in zip(a, b, strict=True))

    if equal(actual, expected):
        return True
    # Ties in ORDER BY may come back in a different order; compare as sorted multisets.
    key = lambda row: ["" if v is None else str(v).strip() for v in row]  # noqa: E731
    return equal(sorted(actual, key=key), sorted(expected, key=key))


def _official_answers(benchmark: Benchmark, scale: float) -> dict[int, list]:
    """The official TPC answer set for `scale`, as {query number: rows of strings}.

    DuckDB's <benchmark>_answers() returns each answer as pipe-separated text with a header line.
    """
    duck = duckdb.connect()
    duck.execute(f"LOAD {benchmark.extension}")
    rows = duck.execute(f"SELECT query_nr, answer FROM {benchmark.name}_answers() WHERE scale_factor = ?", [scale]).fetchall()
    answers = {}
    for nr, answer in rows:
        header, *data = list(csv.reader(io.StringIO(answer), delimiter="|"))
        # A NULL-only row is written as an empty line (e.g. Q17 at SF 0.01): one empty field per column.
        answers[nr] = [row or [""] * len(header) for row in data]
    return answers


def _reference_results(benchmark: Benchmark, scale: float, settings: Settings) -> dict[int, list]:
    """Regenerate the data in DuckDB and run DuckDB's own copy of each query on it.

    Returns {query number: rows}. The data is the same as what load.py put into PostgreSQL because the
    generators are deterministic for a given scale factor. Unlike load.py, chunks are not dropped: each
    TPC-H chunk appends to the same tables, giving the full data set. Takes ~15 s at SF 1.
    """
    work_dir = WORK / f"{benchmark.name}-reference"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True)
    duck = duckdb.connect(str(work_dir / "reference.duckdb"))
    try:
        duck.execute(f"SET memory_limit = '{settings.memory_limit}'")
        duck.execute(f"SET threads = {settings.threads}")
        duck.execute(f"SET temp_directory = '{work_dir / 'tmp'}'")
        duck.execute(f"LOAD {benchmark.extension}")
        started = time.monotonic()
        for _ in benchmark.steps(duck, scale):
            pass  # chunked steps append to the same tables
        results = {}
        # <benchmark>_queries() holds DuckDB's text of each query (same parameters as queries/ files).
        for nr, query in duck.execute(f"SELECT query_nr, query FROM {benchmark.name}_queries() ORDER BY 1").fetchall():
            results[nr] = duck.execute(query).fetchall()
        log(f"  Reference results computed in DuckDB ({time.monotonic() - started:.0f}s).")
        return results
    finally:
        duck.close()
        shutil.rmtree(work_dir, ignore_errors=True)


def _run_query_file(conn: psycopg.Connection, text: str) -> list[tuple]:
    """Run one query file and return the rows of its SELECT.

    Most files hold a single query. A few TPC-DS files wrap it in `BEGIN; SET LOCAL ...; <query>;
    COMMIT;` to change a planner setting for that query only, so the file is split into statements and
    the rows of the one statement that returns rows are kept. `--` comment lines (the header) are dropped.
    """
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    rows: list[tuple] = []
    for statement in (s.strip() for s in re.split(r";\s*\n", body + "\n")):
        if statement:
            cursor = conn.execute(statement)
            if cursor.description is not None:  # only statements that return rows have a description
                rows = cursor.fetchall()
    return rows


def _run_queries(benchmark: Benchmark, settings: Settings, database: str, scale: float, *, reference: bool) -> list[str]:
    """Check 3: run every query file, compare its result, log a line per query. Returns the problems found."""
    # Pick the source of expected results (see module docstring).
    if any(math.isclose(scale, s) for s in benchmark.answer_scales):
        expected, source = _official_answers(benchmark, scale), "official answer"
    elif reference:
        log(f"  No official answers at SF{format_scale(scale)}: computing reference results in DuckDB...")
        expected, source = _reference_results(benchmark, scale, settings), "DuckDB reference"
    else:
        expected, source = {}, ""
        log("  Reference check skipped: only checking that every query runs.")

    problems = []
    ran = matched = known = empty = 0
    with connect(settings, database) as conn:
        # Applies to every statement on this connection; a query running longer is cancelled.
        conn.execute(f"SET statement_timeout = '{settings.query_timeout_s}s'")
        for path in benchmark.query_files():
            number = int(path.stem[1:])  # "q07" -> 7
            started = time.monotonic()
            try:
                rows = _run_query_file(conn, path.read_text())
            except psycopg.errors.QueryCanceled:
                # A query file may have opened a transaction (BEGIN ...); close it so the next one runs.
                conn.execute("ROLLBACK")
                problems.append(f"{path.name}: timed out after {settings.query_timeout_s}s")
                log(f"  {path.name}  TIMEOUT after {settings.query_timeout_s}s")
                continue
            except psycopg.Error as error:
                conn.execute("ROLLBACK")
                problems.append(f"{path.name}: {str(error).splitlines()[0]}")
                log(f"  {path.name}  ERROR  {str(error).splitlines()[0]}")
                continue
            elapsed = time.monotonic() - started
            ran += 1
            empty += not rows  # an empty result is not an error: some queries legitimately return nothing
            verdict = ""
            if number in expected:
                if _same_rows(rows, expected[number]):
                    matched += 1
                    verdict = f"matches {source}"
                elif (benchmark.name, number) in KNOWN_DIFFERENCES:
                    known += 1
                    verdict = f"differs as expected: {KNOWN_DIFFERENCES[(benchmark.name, number)]}"
                else:
                    problems.append(f"{path.name}: result differs from the {source}")
                    verdict = f"DIFFERS from {source}"
            log(f"  {path.name}  {len(rows):>6} rows  {elapsed:7.2f}s  {verdict}")

    total = len(benchmark.query_files())
    summary = f"{ran}/{total} queries ran"
    if expected:
        summary += f", {matched} match the {source}s"
    if known:
        summary += f", {known} differ for a known reason"
    if empty:
        summary += f", {empty} returned no rows"
    log(f"  {summary}.")
    return problems


def verify(benchmark: Benchmark, settings: Settings, *, run_queries: bool, reference: bool = True) -> bool:
    """Run the checks for one benchmark (see module docstring). Returns True if everything passed."""
    database = settings.database_for(benchmark.name)
    log(f"Verifying {benchmark.title} in database '{database}'")
    if not database_exists(settings, database):
        log(f"  FAIL: database '{database}' does not exist. Run `make load-{benchmark.name}` first.")
        return False

    problems: list[str] = []
    with connect(settings, database) as conn:
        # The load record exists only if a load completed (load.py writes it last).
        has_info = conn.execute("SELECT to_regclass('tpc_meta.load_info')").fetchone()[0]
        info = conn.execute(
            "SELECT scale_factor, row_counts FROM tpc_meta.load_info ORDER BY loaded_at DESC LIMIT 1"
        ).fetchone() if has_info else None
        if info is None:
            log("  FAIL: no load record (tpc_meta.load_info). The last load did not finish; run it again.")
            return False
        # The scale comes from the load record, not from settings, so verify checks what is actually loaded.
        scale, expected_rows = float(info[0]), info[1]

        # Check 1: row counts.
        for table, expected in sorted(expected_rows.items()):
            actual = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
            if actual != expected:
                problems.append(f"{table}: {actual:,} rows, expected {expected:,}")
        log(f"  Row counts: {len(expected_rows)} tables checked at SF{format_scale(scale)}.")

        # Check 2: keys. The expected numbers are counted from constraints.sql, so they follow edits to it.
        text = (benchmark.sql_dir / "constraints.sql").read_text()
        pk_expected = len(re.findall(r"^ALTER TABLE .* PRIMARY KEY", text, re.M))
        fk_expected = len(re.findall(r"^ALTER TABLE .* FOREIGN KEY", text, re.M))
        pk, fk, invalid = conn.execute(
            "SELECT count(*) FILTER (WHERE contype = 'p'), count(*) FILTER (WHERE contype = 'f'), "
            "count(*) FILTER (WHERE NOT convalidated) FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
        ).fetchone()
        if (pk, fk, invalid) != (pk_expected, fk_expected, 0):
            problems.append(f"keys: {pk} primary / {fk} foreign / {invalid} not validated; "
                            f"expected {pk_expected} / {fk_expected} / 0")
        log(f"  Keys: {pk} primary, {fk} foreign ({invalid} not validated).")

    # Check 3: queries.
    if run_queries:
        log(f"  Running {len(benchmark.query_files())} queries (timeout {settings.query_timeout_s}s each):")
        problems += _run_queries(benchmark, settings, database, scale, reference=reference)

    if problems:
        log(f"  {benchmark.title}: FAILED")
        for problem in problems:
            log(f"    - {problem}")
        return False
    log(f"  {benchmark.title}: OK")
    return True
