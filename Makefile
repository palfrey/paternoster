debug: sync
	./uv run uwsgi debug-uwsgi.ini

requirements.txt: requirements.in
	./uv pip compile --python-version 3.11 --no-strip-extras requirements.in -o requirements.txt

.venv/bin/activate:
	./uv venv

.PHONY: sync
sync: requirements.txt .venv/bin/activate
	./uv pip sync requirements.txt

db-make-migration: sync
	./uv run flask db migrate

install-pre-commit: sync
	./uv run pre-commit install