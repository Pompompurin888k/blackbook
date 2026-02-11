# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y telegram || true \
    && pip install --no-cache-dir --force-reinstall python-telegram-bot==21.0 \
    && python -c "from telegram import Update; print('python-telegram-bot import OK')"

# Copy the rest of the code
COPY . .

# Run the bot (using new modular entry point)
CMD ["python", "main.py"]
