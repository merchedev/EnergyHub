.PHONY: install dev-backend dev-frontend test lint build

install:
	python3 -m venv .venv
	.venv/bin/pip install -r energyhub/backend/requirements-dev.txt
	cd energyhub/frontend && npm install

test:
	cd energyhub/backend && ../../.venv/bin/pytest

lint:
	cd energyhub/backend && ../../.venv/bin/ruff check app tests
	cd energyhub/frontend && npm run build

dev-backend:
	cd energyhub/backend && ENERGYHUB_DATA_DIR=../../.tmpdata ENERGYHUB_DEMO=1 ENERGYHUB_DEV=1 ../../.venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd energyhub/frontend && npm run dev

build:
	cd energyhub/frontend && npm run build
