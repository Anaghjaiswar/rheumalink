#!/bin/sh
set -e

# This script runs as root, so we can fix permissions.
# The 'app' user and group should own these directories.
echo "Updating permissions for mounted volumes..."
mkdir -p /vol/web/static /vol/web/media /core/logs
chown -R app:app /vol/web /core/logs
chmod 2775 /core/logs
chmod -R 755 /vol/web

# wait for the database to be ready
/py/bin/python manage.py wait_for_db

exec gosu app "$@"