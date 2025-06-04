FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.7.10 /uv /uvx /bin/

ADD pyproject.toml .
ADD uv.lock .
ADD selfa.ini .
ADD selfa-token.json .
ADD app app
RUN uv sync --locked
CMD ["uv", "run", "app/main.py", "--config", "selfa.ini"]
