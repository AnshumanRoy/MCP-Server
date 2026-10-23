FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2 (build-time gcc/libpq-dev cleaned up after install).
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        python3-dev \
    && pip install --no-cache-dir --upgrade pip \
    && apt-get purge -y --auto-remove gcc libpq-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8765

CMD ["uvicorn", "mcp_server.server:build_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
