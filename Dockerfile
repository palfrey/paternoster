FROM python:3.11
WORKDIR /app
RUN wget https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f17855a4dc21156cfe1694c31d7d1792e/wait-for-it.sh -O /usr/bin/wait-for-it && chmod +x /usr/bin/wait-for-it
RUN curl -LsSf https://astral.sh/uv/0.13.5/install.sh | sh
ENV UV_PROJECT_ENVIRONMENT=/usr/local
COPY pyproject.toml uv.lock /app/
RUN ~/.local/bin/uv sync
COPY . /app
CMD uwsgi debug-uwsgi.ini