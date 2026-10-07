# The loader image: Python + DuckDB + psycopg. It holds no code of its own: docker-compose mounts the
# repository at /repo, and PYTHONPATH points at /repo/loader, so `python -m tpc_loader` runs the code
# in your checkout. Rebuild (`make build`) only after changing this file or requirements.txt.
FROM python:3.12-slim

# PYTHONUNBUFFERED: print progress immediately instead of in blocks.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/repo/loader

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Bake the DuckDB extensions into the image so loading works without downloading them at run time:
# tpch / tpcds are the data generators (and ship the queries and TPC-H answers), postgres writes to PostgreSQL.
RUN python -c "import duckdb; c = duckdb.connect(); [c.execute(f'INSTALL {e}') for e in ('tpch', 'tpcds', 'postgres')]"

WORKDIR /repo
# `docker compose run --rm loader verify tpch` runs `python -m tpc_loader verify tpch`.
ENTRYPOINT ["python", "-m", "tpc_loader"]
