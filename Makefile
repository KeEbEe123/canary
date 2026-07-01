.PHONY: help install install-sdk install-backend install-dashboard test test-sdk test-backend build dashboard dev seed clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-sdk install-backend install-dashboard ## Install everything

install-sdk: ## Install the SDK (editable, with dev extras)
	cd sdk && pip install -e ".[dev]"

install-backend: ## Install the backend (editable, with dev extras)
	cd backend && pip install -e ".[dev]"

install-dashboard: ## Install dashboard npm deps
	cd dashboard && npm install

test: test-sdk test-backend ## Run all Python tests

test-sdk: ## Run SDK tests
	cd sdk && pytest -q

test-backend: ## Run backend tests
	cd backend && pytest -q

dashboard: ## Build the dashboard and copy it into the backend's static dir
	cd dashboard && npm run build
	rm -rf backend/src/canary_server/static
	mkdir -p backend/src/canary_server/static
	cp -r dashboard/dist/* backend/src/canary_server/static/

build: dashboard ## Alias for building the dashboard bundle

dev: ## Run the backend server with the built dashboard on :8732
	cd backend && python -m canary_server

seed: ## Populate the local DuckDB with demo runs so the dashboard has data
	cd backend && python -m canary_server.seed

clean: ## Remove build artifacts and local databases
	rm -rf dashboard/dist dashboard/node_modules backend/src/canary_server/static/*
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.duckdb*' -delete
	touch backend/src/canary_server/static/.gitkeep
