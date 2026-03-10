# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv and Python dependencies from pyproject
RUN pip install --no-cache-dir uv
COPY web/pyproject.toml ./
RUN uv export --no-dev --format requirements-txt > requirements.lock \
    && uv pip install --system --no-cache -r requirements.lock

# Copy web app first, then shared (must come after to override the empty web/shared/ dir)
COPY web/ .
COPY shared/ ./shared/

# Expose port
EXPOSE 8080

# Run the web app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
