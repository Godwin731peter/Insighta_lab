#!/bin/bash

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding profiles..."
python manage.py seed_profiles

echo "Starting server..."
exec "$@"