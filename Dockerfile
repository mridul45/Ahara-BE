FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements /app/requirements

# Install Python packages
RUN pip install --no-cache-dir -r requirements/local.txt

# Copy application files
COPY . /app/

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Run entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
