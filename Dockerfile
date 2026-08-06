FROM python:3.12.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements/base.txt requirements/base.txt
RUN python -m pip wheel --wheel-dir /wheels --requirement requirements/base.txt


FROM python:3.12.13-slim-bookworm AS runtime

ENV DJANGO_SETTINGS_MODULE=config.settings.production \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/chainscribe/.local/bin:$PATH

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 chainscribe \
    && useradd --uid 10001 --gid chainscribe --create-home --shell /usr/sbin/nologin chainscribe

COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/* && rm -rf /wheels

WORKDIR /app
COPY --chown=chainscribe:chainscribe . /app
RUN chmod 0755 /app/scripts/entrypoint.sh

USER chainscribe
EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
