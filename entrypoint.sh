#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Execute the main command
exec "$@"
