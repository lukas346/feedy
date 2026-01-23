FROM python:3.14-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev dependencies in production)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Copy application code
COPY src/ ./src/

# Write git commit hash to file (passed as build arg)
ARG GIT_COMMIT=unknown
RUN echo "${GIT_COMMIT}" > /app/src/GIT_COMMIT

# Copy alembic configuration and migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create data directory for SQLite and logs directory
RUN mkdir -p /app/data /app/logs

ENV PYTHONPATH=/app/src
ENV DATABASE_URL=sqlite:////app/data/reader.db

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
