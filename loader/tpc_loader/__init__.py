"""tpc_loader: generate TPC-H / TPC-DS data with DuckDB and load it into PostgreSQL.

This package is the program inside the `loader` container. You normally reach it through the
Makefile (`make load`, `make verify`, ...), which runs `docker compose run --rm loader <command>`;
the image's entrypoint is `python -m tpc_loader`, i.e. __main__.py in this package.

See loader/README.md for how the modules fit together.
"""

# Recorded in tpc_meta.load_info with every load, so a database says which loader produced it.
__version__ = "0.1.0"
