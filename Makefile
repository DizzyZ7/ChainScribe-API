.PHONY: install lint format-check check test coverage migrate run compose-up compose-down smoke

install:
	python -m pip install --requirement requirements/dev.txt

lint:
	ruff check .

format-check:
	ruff format --check .

check:
	python manage.py makemigrations --check --dry-run
	python manage.py check

test:
	python manage.py test --verbosity=2

coverage:
	coverage run manage.py test
	coverage report --fail-under=90

migrate:
	python manage.py migrate

run:
	python manage.py runserver

compose-up:
	docker compose up --build

compose-down:
	docker compose down

smoke:
	python scripts/smoke_test.py
