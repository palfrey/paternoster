debug: sync
	uv run uwsgi debug-uwsgi.ini

.venv/bin/activate:
	uv venv

.PHONY: sync
sync: pyproject.toml .venv/bin/activate
	uv sync

db-make-migration: sync
	uv run flask db migrate

install-pre-commit: sync
	uv run pre-commit install