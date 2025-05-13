FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Redis client
RUN pip install --no-cache-dir redis

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV TZ=Asia/Jakarta

# Create a non-root user to run the application
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Command to run the application
CMD ["./run.sh"]
