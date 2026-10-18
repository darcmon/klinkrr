.PHONY: up down dev backend frontend install

# Start Postgres + MinIO in the background
up:
	docker compose up -d

# Stop them (keeps data)
down:
	docker compose down

# Install backend (venv) and frontend deps
install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	cd frontend && npm install

# Run backend + frontend together; Ctrl-C stops both
dev:
	@trap 'kill 0' INT; \
	.venv/bin/uvicorn backend.main:app --reload --port 8000 & \
	(cd frontend && npm run dev) & \
	wait

backend:
	.venv/bin/uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev
