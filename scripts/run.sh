#!/bin/sh

set -e

ls -la /vol/
ls -la /vol/web

whoami

python manage.py wait_for_db
python manage.py collectstatic --noinput
python manage.py migrate

python -m gunicorn --workers 4 --bind 0.0.0.0:8000  core.asgi:application -k uvicorn.workers.UvicornWorker