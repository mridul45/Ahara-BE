# syntax=docker/dockerfile:1

# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gettext \
    python3-dev \
    zlib1g-dev \
    libpq-dev \
    libtiff5-dev \
    libjpeg8-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    graphviz-dev \
    netcat-openbsd \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./requirements/ /app/requirements/

RUN pip install --no-cache-dir -r requirements/production.txt
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir -r requirements/local.txt


# Copy project code
COPY . /app/

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

