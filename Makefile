.PHONY: up down logs test lint
up:
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f
test:
	docker compose run --rm api-gateway pytest
	docker compose run --rm identity-service pytest
	docker compose run --rm fraud-service pytest
	docker compose run --rm recovery-service pytest
	python -m unittest discover packages/shared/tests -v
	python -m unittest discover tests -v
lint:
	docker compose run --rm api-gateway ruff check .
	docker compose run --rm identity-service ruff check .
	docker compose run --rm fraud-service ruff check .
	docker compose run --rm recovery-service ruff check .
	docker compose build web
