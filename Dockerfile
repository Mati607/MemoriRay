FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      tini \
      curl \
      ca-certificates \
      libjpeg62-turbo \
      zlib1g \
      libfreetype6 \
      libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-ansi

COPY . .
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000 8501

ENTRYPOINT ["tini", "--", "/app/docker/entrypoint.sh"]
