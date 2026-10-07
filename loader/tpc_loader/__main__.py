"""Command-line entry point: `python -m tpc_loader <command> [tpch|tpcds|all]`.

The container's ENTRYPOINT is `python -m tpc_loader`, so everything after the service name in
`docker compose run --rm loader ...` arrives here as arguments. The Makefile maps its targets to
these commands:

    make load / load-tpch / load-tpcds        -> load   all / tpch / tpcds    (load.py)
    make verify / verify-tpch / verify-tpcds  -> verify all / tpch / tpcds    (verify.py)
    make status                               -> status                       (status.py)
    make index-fks                            -> index-fks all                (indexes.py)

Settings (scale factors, passwords, timeouts, ...) are not command-line flags: they come from
environment variables, which docker-compose fills from .env and the make command line
(see settings.py).
"""

import argparse

from .benchmarks import select
from .settings import Settings


def main() -> None:
    """Parse the command, read the settings, and run the command for each selected benchmark."""
    parser = argparse.ArgumentParser(prog="tpc_loader", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    # The three commands that act on benchmarks all take an optional benchmark name (default: all).
    for name, help_text in [
        ("load", "generate the data and (re)create the database"),
        ("verify", "check row counts and keys, and run the benchmark queries"),
        ("index-fks", "create an index on every foreign key that lacks one"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("benchmark", nargs="?", default="all", choices=["tpch", "tpcds", "all"])
        if name == "verify":
            # Not exposed as make targets; use them directly, e.g.
            # `docker compose run --rm loader verify tpcds --skip-queries`.
            command.add_argument("--skip-queries", action="store_true", help="only check row counts and keys")
            command.add_argument("--no-reference", action="store_true",
                                 help="without official answers, only check that queries run (skip the DuckDB reference run)")
    # `status` reports on every TPC database on the server, so it takes no benchmark argument.
    commands.add_parser("status", help="show what is loaded")

    args = parser.parse_args()
    settings = Settings.from_env()

    if args.command == "status":
        from .status import status
        status(settings)
        return

    # Each command module is imported only when needed, so e.g. `status` never loads DuckDB.
    failed = False
    for benchmark in select(args.benchmark):
        if args.command == "load":
            from .load import load
            load(benchmark, settings)  # raises SystemExit on failure, stopping the remaining benchmarks
        elif args.command == "verify":
            from .verify import verify
            # verify returns False instead of raising, so every benchmark is checked before we fail.
            failed |= not verify(benchmark, settings, run_queries=not args.skip_queries, reference=not args.no_reference)
        elif args.command == "index-fks":
            from .indexes import index_foreign_keys
            index_foreign_keys(benchmark, settings)

    # A non-zero exit code makes `make verify` (and therefore CI) fail.
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
