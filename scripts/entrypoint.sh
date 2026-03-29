#!/bin/sh
set -e

# This script runs as root, so we can fix permissions.
# The 'app' user and group should own these directories.
echo "Updating permissions for mounted volumes..."
chown -R app:app /core/logs
chmod 2775 /core/logs
chown -R app:app /vol/web


# wait for the database to be ready
python manage.py wait_for_db

exec su-exec app "$@"