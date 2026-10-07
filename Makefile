# Thin wrappers around docker compose. Settings come from .env (optional); any of them can be
# overridden per command, e.g. `make load-tpch TPCH_SCALE=0.1` or `make load PRESET=tiny`.

-include .env
export

COMPOSE := docker compose
LOADER  := $(COMPOSE) run --rm loader
PSQL    := $(COMPOSE) exec -e PGPASSWORD=$(or $(READER_PASSWORD),reader) postgres psql -h localhost -U $(or $(READER_USER),reader)

.DEFAULT_GOAL := help
.PHONY: help up down build load load-tpch load-tpcds verify verify-tpch verify-tpcds status \
        psql-tpch psql-tpcds index-fks logs reset

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

up: ## Start PostgreSQL (localhost:$POSTGRES_PORT, default 5432)
	$(COMPOSE) up -d --wait postgres

down: ## Stop PostgreSQL (data is kept)
	$(COMPOSE) down

build: ## Build the loader image
	$(COMPOSE) build loader

load: up ## Generate and load both benchmarks
	$(LOADER) load all

load-tpch: up ## Generate and load TPC-H only
	$(LOADER) load tpch

load-tpcds: up ## Generate and load TPC-DS only
	$(LOADER) load tpcds

verify: up ## Check row counts and keys, and run all benchmark queries
	$(LOADER) verify all

verify-tpch: up ## Verify TPC-H only
	$(LOADER) verify tpch

verify-tpcds: up ## Verify TPC-DS only
	$(LOADER) verify tpcds

status: up ## Show which databases are loaded, at what scale and size
	@$(LOADER) status

psql-tpch: ## Open psql on the tpch database (read-only login)
	$(PSQL) -d tpch

psql-tpcds: ## Open psql on the tpcds database (read-only login)
	$(PSQL) -d tpcds

index-fks: up ## Optional: index every foreign-key column (faster point lookups, more disk)
	$(LOADER) index-fks all

logs: ## Follow the PostgreSQL log
	$(COMPOSE) logs -f postgres

reset: ## Stop PostgreSQL and DELETE all loaded data
	$(COMPOSE) --profile tools down -v
