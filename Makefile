.PHONY: dev api web test test-api test-web build

# Run API (port 8000) and web dev server (port 5173, proxies /api to 8000) together.
dev:
	@trap 'kill 0' INT TERM; \
	$(MAKE) api & \
	$(MAKE) web & \
	wait

api:
	cd api && .venv/bin/uvicorn innesto.main:app --reload --port 8000

web:
	cd web && npm run dev -- --host

test: test-api test-web

test-api:
	cd api && .venv/bin/pytest -q

test-web:
	cd web && npx vitest run

build:
	cd web && npm run build
