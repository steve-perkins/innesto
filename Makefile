.PHONY: dev api web test test-api test-web build check-ports

# Run API (port 8000) and web dev server (port 5173, proxies /api to 8000) together.
dev: check-ports
	@trap 'kill 0' INT TERM; \
	$(MAKE) api & \
	$(MAKE) web & \
	wait

# Refuse to start on top of another instance: a silent port clash makes the
# web app proxy /api to a server that is not ours (or to nothing).
check-ports:
	@for p in 8000 5173; do \
	  if lsof -nP -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "Port $$p is already in use:"; lsof -nP -iTCP:$$p -sTCP:LISTEN | tail -n +2; \
	    echo "Stop that process (or a previous 'make dev') first."; exit 1; \
	  fi; \
	done

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
