#!/bin/sh

# Exit on error
set -o errexit

# Wait for the database to be ready
until nc -z "$DB_HOST" "$DB_PORT"; do
  echo "Waiting for database..."
  sleep 1
done

echo "Database is ready."

# Run database migrations
python manage.py migrate

# Start Gunicorn
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
