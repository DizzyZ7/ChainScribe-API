#!/bin/sh
set -eu

python manage.py wait_for_db

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
