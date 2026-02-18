# EZ Solutions — developer convenience targets
# Usage: make <target>
# On Windows use: python manage.py ... directly, or WSL for make support.

PYTHON   := ./venv/Scripts/python.exe
PIP      := ./venv/Scripts/pip.exe
MANAGE   := $(PYTHON) manage.py --settings=config.settings.dev
PYTEST   := ./venv/Scripts/pytest.exe
RUFF     := ./venv/Scripts/ruff.exe
BLACK    := ./venv/Scripts/black.exe
CELERY   := ./venv/Scripts/celery.exe

.DEFAULT_GOAL := help

.PHONY: help install dev migrate seed test lint format security check-all \
        run shell superuser clean \
        worker worker-provisioning beat periodic-tasks

help:
	@echo ""
	@echo "EZ Solutions — available make targets"
	@echo "────────────────────────────────────────────────────────"
	@echo "  install           Install all dev dependencies"
	@echo "  dev               Install deps + migrate + seed plans"
	@echo "  migrate           Run migrations"
	@echo "  seed              Seed sample service plans"
	@echo "  test              Run test suite with coverage"
	@echo "  lint              Run ruff + black check"
	@echo "  format            Auto-format with ruff + black"
	@echo "  security          Run bandit + pip-audit"
	@echo "  check-all         lint + test + security"
	@echo "  run               Start dev server on :7000"
	@echo "  shell             Django shell"
	@echo "  superuser         Create superuser interactively"
	@echo "  clean             Remove cache / compiled files"
	@echo "  worker            Start Celery worker (default + provisioning queues)"
	@echo "  worker-provisioning Start dedicated provisioning queue worker"
	@echo "  beat              Start Celery Beat scheduler"
	@echo "  periodic-tasks    Manually register periodic tasks in the DB"
	@echo ""

install:
	$(PIP) install -r requirements/dev.txt

dev: install migrate seed
	@echo "✅ Dev environment ready — run 'make run' to start the server"

migrate:
	$(MANAGE) migrate

seed:
	$(MANAGE) seed_plans

test:
	$(PYTEST) tests/ --tb=short -q

test-cov:
	$(PYTEST) tests/ --cov --cov-report=term-missing --cov-report=html

lint:
	$(RUFF) check .
	$(BLACK) --check .

format:
	$(RUFF) check . --fix
	$(BLACK) .

security:
	$(PYTHON) -m bandit -r . -x ./venv,./tests -c pyproject.toml --severity-level medium
	$(PIP) install pip-audit -q
	$(PYTHON) -m pip_audit -r requirements/base.txt

check-all: lint test security
	@echo "✅ All checks passed!"

run:
	$(MANAGE) runserver 7000

shell:
	$(MANAGE) shell

superuser:
	$(MANAGE) createsuperuser

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml bandit-report.json
	@echo "✅ Cleaned up"

# ── Celery ────────────────────────────────────────────────────────────────────

worker:
	$(CELERY) -A config worker \
		--loglevel=info \
		--queues=default,provisioning,periodic \
		--concurrency=4 \
		--hostname=worker@%h

worker-provisioning:
	$(CELERY) -A config worker \
		--loglevel=info \
		--queues=provisioning \
		--concurrency=2 \
		--hostname=worker-provisioning@%h

beat:
	$(CELERY) -A config beat \
		--loglevel=info \
		--scheduler django_celery_beat.schedulers:DatabaseScheduler

periodic-tasks:
	$(MANAGE) setup_periodic_tasks

