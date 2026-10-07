"""Settings, read from environment variables.

Where the values come from: the `loader` service in docker-compose.yml lists each variable with a
default (e.g. `TPCH_SCALE: ${TPCH_SCALE:-1}`); Compose fills them from your shell environment, then
.env, then that default. The Makefile `export`s its variables, so `make load-tpch TPCH_SCALE=0.1`
reaches this module as TPCH_SCALE=0.1. Every variable is documented in .env.example.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# The repository is mounted at /repo inside the container (see docker-compose.yml), so the loader
# reads sql/ and queries/ from your checkout: edits take effect without rebuilding the image.
REPO = Path(os.environ.get("REPO_DIR", "/repo"))

# Scratch space for DuckDB's on-disk work files: the `loader-work` Docker volume. Emptied after each run.
WORK = Path(os.environ.get("WORK_DIR", "/work"))

# Named sizes accepted wherever a scale factor is (TPCH_SCALE, TPCDS_SCALE, PRESET).
PRESETS = {"tiny": 0.01, "small": 0.1, "standard": 1.0, "large": 10.0}

# Above this scale factor a load needs FORCE=1 (tens of GB of disk, long load times).
FORCE_ABOVE_SCALE = 10.0


def parse_scale(value: str) -> float:
    """Turn "0.1", "3" or a preset name ("tiny", "standard", ...) into a scale factor.

    Exits with a readable message (rather than a traceback) on a bad value, since this is user input.
    """
    value = value.strip().lower()
    if value in PRESETS:
        return PRESETS[value]
    try:
        scale = float(value)
    except ValueError:
        raise SystemExit(f"Invalid scale factor {value!r}: use a number or one of {', '.join(PRESETS)}.") from None
    if scale <= 0:
        raise SystemExit(f"Scale factor must be positive, got {value!r}.")
    return scale


def format_scale(scale: float) -> str:
    """Scale factor for display and database names: 1.0 -> "1", 0.01 -> "0.01"."""
    return f"{scale:g}"


def _flag(name: str) -> bool:
    """True if the environment variable is set to 1 / true / yes / on (any case)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Everything the commands need to know, read once at start-up by Settings.from_env()."""

    host: str              # PostgreSQL host: the `postgres` service name on the Compose network
    port: int              # port inside that network (always 5432; POSTGRES_PORT is only the host-side port)
    admin_user: str        # owner login: creates databases, loads data
    admin_password: str
    reader_user: str       # read-only login created for everyone else
    reader_password: str
    tpch_scale: float
    tpcds_scale: float
    keep_scales: bool      # name databases by scale (tpch_sf0_1) so several sizes can coexist
    force: bool            # allow scale factors above FORCE_ABOVE_SCALE
    memory_limit: str      # DuckDB memory cap while generating, e.g. "4GB"; beyond it DuckDB spills to WORK
    threads: int           # DuckDB threads
    query_timeout_s: int   # per-query statement_timeout used by `verify`

    @classmethod
    def from_env(cls) -> "Settings":
        """Build the settings from environment variables, applying the same defaults as .env.example."""
        # PRESET, when set, overrides both scale factors.
        preset = os.environ.get("PRESET", "").strip()
        return cls(
            host=os.environ.get("PGHOST", "postgres"),
            port=int(os.environ.get("PGPORT", "5432")),
            admin_user=os.environ.get("POSTGRES_USER", "postgres"),
            admin_password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
            reader_user=os.environ.get("READER_USER", "reader"),
            reader_password=os.environ.get("READER_PASSWORD", "reader"),
            tpch_scale=parse_scale(preset or os.environ.get("TPCH_SCALE", "1")),
            tpcds_scale=parse_scale(preset or os.environ.get("TPCDS_SCALE", "1")),
            keep_scales=_flag("KEEP_SCALES"),
            force=_flag("FORCE"),
            memory_limit=os.environ.get("LOADER_MEMORY_LIMIT", "4GB"),
            # An empty LOADER_THREADS means "all CPUs the container can see".
            threads=int(os.environ.get("LOADER_THREADS") or os.cpu_count() or 4),
            query_timeout_s=int(os.environ.get("QUERY_TIMEOUT", "300")),
        )

    def scale_for(self, benchmark: str) -> float:
        """The scale factor configured for "tpch" or "tpcds"."""
        return self.tpch_scale if benchmark == "tpch" else self.tpcds_scale

    def database_for(self, benchmark: str) -> str:
        """Database name for a benchmark: `tpch`, or `tpch_sf0_1` style when KEEP_SCALES is on.

        Every command (load, verify, index-fks) goes through this, so with KEEP_SCALES=true they
        all address the database for the scale currently configured.
        """
        if not self.keep_scales:
            return benchmark
        return f"{benchmark}_sf{format_scale(self.scale_for(benchmark)).replace('.', '_')}"

    def dsn(self, database: str, *, user: str | None = None, password: str | None = None) -> str:
        """libpq connection string for `database`, as the admin login unless another is given.

        Used by psycopg (pg.connect) and by DuckDB's postgres extension (ATTACH ... TYPE postgres).
        """
        return (
            f"host={self.host} port={self.port} dbname={database} "
            f"user={user or self.admin_user} password={password or self.admin_password}"
        )
