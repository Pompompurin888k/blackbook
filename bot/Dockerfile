# Use a lightweight Python image
FROM python:3.11-slim

# Default timezone
ENV TZ=Africa/Nairobi

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install uv and Python dependencies from pyproject
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv export --no-dev --format requirements-txt > requirements.lock \
    && uv pip install --system --no-cache -r requirements.lock \
    && pip uninstall -y telegram || true \
    && python -c "from telegram import Update; from telegram.ext import JobQueue; print('python-telegram-bot import OK')"

# Copy the rest of the code
COPY . .

# Run the bot (using new modular entry point)
CMD ["python", "main.py"]
