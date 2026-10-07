"""The two benchmarks, and everything that differs between them.

The command modules (load, verify, indexes) are written once and take a Benchmark object; the
per-benchmark details live here: which DuckDB extension generates the data, how generation is split
into steps, which scale factors have official answers, and where its SQL and query files are.
"""

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .settings import REPO


def _tpch_steps(conn: duckdb.DuckDBPyConnection, scale: float) -> Iterator[None]:
    """Generate TPC-H into `conn`, yielding after each chunk.

    Generation is split into chunks of about one scale-factor unit (SF 3 -> 3 chunks), so memory use
    stays roughly constant at any scale. dbgen's `children` / `step` parameters split every table into
    disjoint slices that together are exactly the full data set, the same rows as a one-shot run.

    The caller decides what a chunk boundary means: load.py copies the chunk's tables to PostgreSQL and
    drops them before the next chunk; verify.py keeps them, and the next chunk appends to the same tables.
    """
    chunks = max(1, math.ceil(scale))
    for step in range(chunks):
        if chunks == 1:
            conn.execute(f"CALL dbgen(sf={scale})")
        else:
            conn.execute(f"CALL dbgen(sf={scale}, children={chunks}, step={step})")
        yield


def _tpcds_steps(conn: duckdb.DuckDBPyConnection, scale: float) -> Iterator[None]:
    """Generate TPC-DS into `conn` in one step.

    dsdgen has no chunking option. The callers use an on-disk DuckDB database with a memory limit, so
    at large scales DuckDB spills to disk instead of running out of memory.
    """
    conn.execute(f"CALL dsdgen(sf={scale})")
    yield


@dataclass(frozen=True)
class Benchmark:
    """One benchmark: how to generate it and where its files live."""

    name: str        # "tpch" / "tpcds": database name, sql/ and queries/ folder, DuckDB function prefix
    title: str       # "TPC-H" / "TPC-DS", for messages
    extension: str   # DuckDB extension that provides the generator, queries and answers
    # Generator: called with an open DuckDB connection and the scale factor; yields once per chunk.
    steps: Callable[[duckdb.DuckDBPyConnection, float], Iterator[None]]
    # Scale factors for which DuckDB ships the official TPC answer set (used by verify).
    answer_scales: tuple[float, ...]

    @property
    def sql_dir(self) -> Path:
        """sql/<name>/: schema.sql, constraints.sql, comments.sql."""
        return REPO / "sql" / self.name

    @property
    def queries_dir(self) -> Path:
        """queries/<name>/: the benchmark queries in PostgreSQL syntax."""
        return REPO / "queries" / self.name

    def query_files(self) -> list[Path]:
        """q01.sql, q02.sql, ... in order (the zero padding makes the sort numeric)."""
        return sorted(self.queries_dir.glob("q*.sql"))


BENCHMARKS = {
    # DuckDB's tpch extension ships answers for SF 0.01, 0.1 and 1 (tpch_answers()).
    "tpch": Benchmark(name="tpch", title="TPC-H", extension="tpch", steps=_tpch_steps, answer_scales=(0.01, 0.1, 1.0)),
    # tpcds_answers() exists but fails in DuckDB 1.5.2, so TPC-DS is always checked with a reference run.
    "tpcds": Benchmark(name="tpcds", title="TPC-DS", extension="tpcds", steps=_tpcds_steps, answer_scales=()),
}


def select(target: str) -> list[Benchmark]:
    """The benchmarks a command should act on: "tpch", "tpcds", or "all" (both, TPC-H first)."""
    if target == "all":
        return list(BENCHMARKS.values())
    if target not in BENCHMARKS:
        raise SystemExit(f"Unknown benchmark {target!r}: use tpch, tpcds or all.")
    return [BENCHMARKS[target]]
