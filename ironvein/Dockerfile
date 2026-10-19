FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY ironvein ./ironvein
COPY sim ./sim
RUN pip install --no-cache-dir ".[dev]"
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

# Миграции применяются при каждом старте (идемпотентно), затем запускается бот с фоновыми задачами.
CMD ["sh", "-c", "alembic upgrade head && python -m ironvein.bot"]
