# Architecture decisions

## Finish line

The critical journey is registration, authenticated article creation/update, authenticated
comment creation, owner-only deletion and logout that immediately invalidates the current token.
Completion requires executable tests, PostgreSQL-backed CI and a container smoke journey.

## ADR-001: opaque token and JWT remain separate

The assignment explicitly requires a 256-character random token and awards additional credit for
`django-ninja-jwt`. A JWT is signed structured data and cannot truthfully substitute for that
random opaque credential. ChainScribe therefore accepts two unambiguous authorization schemes:

- `Token` for a 256-character random credential stored only as a digest;
- `Bearer` for a short-lived JWT access token.

Logout revokes the presented opaque token. JWT refresh logout uses the blacklist endpoint.

## ADR-002: authorship is never an input

Article/comment schemas forbid extra fields. The authenticated user is assigned in the
transactional service. Update code loads the object under a row lock and rechecks owner identity,
which prevents both straightforward IDOR and a check/use race.

## ADR-003: drafts are filtered before request filters

The selector starts with the caller's visibility boundary and only then applies category, status
and author filters. Anonymous users cannot infer draft existence through counts or filter values.

## ADR-004: operational and security records are separate

Structured stdout logs are optimized for diagnostics and aggregation. Database audit events are
optimized for who/what/outcome evidence and intentionally exclude content and credentials. The
audit model and Admin reject mutation; high-assurance deployments should additionally export
events to external write-once storage.

## ADR-005: PostgreSQL is authoritative

PostgreSQL provides the tested constraints, UUID indexing, row locks and transactions. An explicit
SQLite test switch exists only for constrained developer diagnostics; CI and production do not use
it.

## Data lifecycle

- Users are normally deactivated rather than deleted.
- User deletion is protected while authored content exists.
- Category deletion is protected while referenced.
- Article deletion cascades its comments.
- Opaque-token logout sets `revoked_at`; it does not delete evidence.
- Expired JWT blacklist records are cleaned by `flushexpiredtokens`.

## Trust boundaries

The reverse proxy terminates public TLS and applies coarse WAF/rate policies. Gunicorn receives
bounded HTTP requests. Django validates origins, input shapes, credentials and ownership. Redis is
trusted only for disposable throttling state. PostgreSQL is the system of record. Secrets enter
only through the runtime environment or platform secret manager.
