.PHONY: help install dev test lint format run dashboard docker-build docker-up docker-down

# Default target
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install production dependencies
	pip install -r requirements.txt

dev: ## Install all dependencies including dev tools
	pip install -e ".[all]"

# Development
run: ## Run the API server
	uvicorn interntrack.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run the background worker
	python -m interntrack.worker

dashboard: ## Run the Streamlit dashboard
	streamlit run dashboard/app.py --server.port 8501

# Testing
test: ## Run all tests with coverage
	pytest --cov=interntrack --cov-report=term-missing -v

test-unit: ## Run unit tests only
	pytest tests/unit -v

test-integration: ## Run integration tests only
	pytest tests/integration -v

test-cov: ## Generate HTML coverage report
	pytest --cov=interntrack --cov-report=html
	open htmlcov/index.html

# Code Quality
lint: ## Run linter (ruff)
	ruff check src/ tests/

format: ## Format code with ruff
	ruff format src/ tests/

format-check: ## Check formatting without making changes
	ruff format --check src/ tests/

typecheck: ## Run type checker (mypy)
	mypy src/interntrack

security: ## Run security scan (bandit)
	bandit -r src/ -ll -q

security-report: ## Generate HTML security report (bandit)
	bandit -r src/ -f html -o bandit-report.html

# Database
db-migrate: ## Run database migrations
	alembic upgrade head

db-revision: ## Create a new migration
	alembic revision --autogenerate -m "$(msg)"

db-reset: ## Reset database (WARNING: destroys data)
	rm -f data/interntrack.db
	alembic upgrade head

# Docker
docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down

docker-logs: ## View logs from all services
	docker-compose logs -f

docker-reset: ## Remove all containers and volumes
	docker-compose down -v

# Utilities
seed: ## Seed database with sample data
	python -m interntrack.scripts.seed

export-jobs: ## Export jobs to CSV
	python -m interntrack.scripts.export --format csv

clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .mypy_cache .pytest_cache htmlcov .coverage

setup: ## Initial project setup
	python -m venv venv
	@echo "Activate venv and run: make dev"
