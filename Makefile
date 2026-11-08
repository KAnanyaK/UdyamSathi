.PHONY: dev backend frontend test seed
dev:
	@powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
backend:
	uvicorn backend.main:app --reload --port 8000
frontend:
	cd frontend && npm run dev
test:
	pytest -q
seed:
	python scripts/seed_demo.py
