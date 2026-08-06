# Production deployment runbook

## Preconditions

- CI is green for the exact commit being released.
- The image is built from that commit and stored in a private or access-controlled registry.
- PostgreSQL and Redis are reachable only from the application network.
- PostgreSQL TLS, encryption at rest, automated backups and point-in-time recovery are enabled.
- DNS, TLS certificate, reverse proxy and WAF are configured.
- An external security review has accepted the release.

## Secrets

Create independent random values for Django and JWT signing. Store them in a managed secret store,
not `.env` committed to Git. Restrict database credentials to the application database and rotate
all credentials under a rehearsed procedure.

## Release sequence

1. Back up PostgreSQL and verify the backup metadata.
2. Pull/build the immutable application image.
3. Run `python manage.py migrate --noinput` as one release task.
4. Start one canary replica with automatic migrations disabled.
5. Verify `/api/v1/health/live` and `/api/v1/health/ready` through the proxy.
6. Run `scripts/smoke_test.py` against a non-production test account or staging first.
7. Roll out remaining replicas and watch latency, 401, 403, 429 and 500 rates.
8. Retain the previous image for rollback.

Database rollback is migration-specific. Never blindly migrate backward after writes have used a
new schema. Prefer forward fixes unless the migration has a rehearsed reverse operation.

## Proxy requirements

- enforce HTTPS and modern TLS;
- preserve a validated `X-Request-ID` or let the app generate one;
- set `X-Forwarded-Proto: https`;
- overwrite, rather than append untrusted, forwarding headers;
- limit headers and request bodies before Gunicorn;
- add stricter limits to auth endpoints;
- never include authorization headers or query strings in access logs;
- expose only the application port, not PostgreSQL or Redis.

Set `TRUST_PROXY_HEADERS=true` only when requests can arrive solely through that trusted proxy.

## Scheduled work

Run daily:

```bash
python manage.py flushexpiredtokens
```

Schedule backup verification and restore drills independently from the application.

## Monitoring

Alert on sustained readiness failures, database saturation, Redis failures, 500 spikes, unusual
authentication denial rates and rate-limit surges. Correlate events with `X-Request-ID`. Do not
collect request bodies or credentials during incident debugging.
