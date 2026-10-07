# AGENTS.md

Guidance for coding agents working in this repository. It complements [README.md](README.md)
(what the project is and how to use it) and [loader/README.md](loader/README.md) (how the loader
works). Read those first.

## Layout

- `docker-compose.yml`, `Makefile`, `.env.example`: the PostgreSQL service, the loader service and every setting.
- `loader/`: the Python loader. It runs in a container with the repository mounted at `/repo`, so code
  edits need no image rebuild. Rebuild (`make build`) only after changing `loader/Dockerfile` or
  `loader/requirements.txt`.
- `sql/<benchmark>/`: `schema.sql` (tables), `constraints.sql` (keys and indexes, applied after loading),
  `comments.sql` (table and column descriptions).
- `queries/<benchmark>/`: the benchmark queries in PostgreSQL syntax, one per file.
- `erd.html`: the self-contained interactive ERD. Its `DATA` block is a copy of the schema.

## Change rules

- Changing anything in `sql/` also means updating the `DATA` block in `erd.html` by hand (tables,
  columns, keys, descriptions, row counts). A new table also needs a position in `LAYOUT`. No script
  generates it.
- `make verify` counts the keys in `constraints.sql` and expects the database to match. Keep one
  `ALTER TABLE ... PRIMARY KEY` or `FOREIGN KEY` statement per line.
- Query files keep the specification's query text. Add only comment headers, or a
  `BEGIN; SET LOCAL ...; COMMIT;` wrapper with a comment explaining it.
- A result that legitimately differs from the reference goes in `KNOWN_DIFFERENCES` in
  `loader/tpc_loader/verify.py`, with the reason.
- New settings go in `.env.example`, `docker-compose.yml` (loader environment), `settings.py`, and the
  configuration table in `README.md`.

## Deliberate choices: do not change

- Column types follow the TPC specifications, including space-padded `CHAR(n)`. Exceptions: TPC-H
  key columns are `BIGINT` (`o_orderkey` overflows `INTEGER` above SF ~89), and TPC-DS spells
  `s_tax_percentage` correctly (the kit has `s_tax_precentage`).
- Databases use `C` collation. The default `en_US.utf8` changes `ORDER BY ... LIMIT` results.
- `duckdb` is pinned to an exact version in `loader/requirements.txt`: it decides the generated data,
  the reference query texts and the TPC-H answer sets. After an upgrade, reload and verify at SF 1.
- TPC-DS queries 4, 11, 54, 74 and 95 set `enable_nestloop = off`. Without it, 4 and 11 run for more
  than 5 minutes.
- Keys are added after loading, not declared in `schema.sql`. Foreign keys are not indexed by default
  in TPC-DS (`make index-fks` adds them).

## Testing

`make load` replaces the user's scale-factor-1 databases. Test in separate databases instead:

```bash
ruff check loader/
make load KEEP_SCALES=true PRESET=tiny
make verify KEEP_SCALES=true PRESET=tiny
```

Run `make verify` (both benchmarks, about 4 minutes) at SF 1 before finishing a change to `sql/`,
`queries/` or the loader. Drop test databases afterwards
(`docker compose exec postgres psql -U postgres -c "DROP DATABASE tpch_sf0_01"`, and the same for
`tpcds_sf0_01`). Check `erd.html` changes in a browser, light and dark, desktop and phone width.

## Rules

- Never describe results from this repository as official TPC-H or TPC-DS benchmark results.
- Do not commit generated data, `.env`, or files with credentials.
- Documentation style: direct and professional, active voice, short sentences. No marketing words,
  emojis or decorative bold.
