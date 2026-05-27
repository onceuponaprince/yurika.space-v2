# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each minor version corresponds to one completed subsystem in the
[rebuild roadmap](./README.md#rebuild-roadmap). Subsystems land as
atomic commits; the version tag points at the commit that closed the
subsystem's verify gate.

## [Unreleased]

### Pending

- Subsystem 3 — Domains (CRUD + PENDING → VAULTED lifecycle)
- Subsystem 4 — Shards / Marketplace
- Subsystem 5 — Knowledge Graph (Neo4j sync + discovery)
- Subsystem 6 — Frontend pages (App Router + wallet UX)
- Subsystem 7 — Smart contracts (Foundry → Base Sepolia)
- Subsystem 8 — Celery + email + observability

## [0.2.0] — 2026-05-27 — Subsystem 2: SIWE + JWT auth

### Added

- `apps/users/` Django app with custom `User` model — `AbstractUser`
  extension keyed on `wallet_address` (EIP-55 lowercase, 0x-prefixed,
  40-hex validator).
- Redis-backed nonce service (`apps/users/nonce.py`) — 5-min TTL,
  consume-once semantics for replay protection.
- `GET /api/auth/wallet/nonce/?address=…` — returns a canonical
  EIP-4361 SIWE message + nonce.
- `POST /api/auth/wallet/verify/` — validates the signed SIWE message,
  auto-creates the user on first sign-in, returns SimpleJWT access +
  refresh pair.
- `apps/users/auth_flow.py` — separates SIWE verify-flow policy
  (nonce consumption + user resolution) from HTTP plumbing so it can
  be unit-tested without an HTTP client.
- SimpleJWT configured with 30-minute access / 14-day refresh.
- `SIWE_CHAIN_ID` (default 8453 — Base mainnet) + `SIWE_STATEMENT`
  settings overridable via env vars.
- pytest suite: 27 cases across model validators, nonce lifecycle,
  HTTP endpoints, replay rejection, returning-user idempotency,
  malformed inputs.

### Changed

- `DEFAULT_AUTHENTICATION_CLASSES` adds
  `rest_framework_simplejwt.authentication.JWTAuthentication` ahead of
  `SessionAuthentication`.
- `AUTH_USER_MODEL = "users.User"`.

### Verify gate

`POST /api/auth/wallet/verify/` issues a JWT pair.

## [0.1.0] — 2026-05-27 — Subsystem 1: infrastructure + skeletons

### Added

- Docker Compose stack with explicit per-service memory caps (3.5 GB
  total worst case): Postgres 16, Neo4j 5, Redis 7, Django 5, Next.js
  16.
- Django backend skeleton (`apps/backend/`) — uv-managed,
  `config.settings.{base,local}` split, `/health/` endpoint probing
  Postgres + Redis.
- Next.js frontend skeleton (`apps/frontend/`) — App Router, Tailwind
  4 beta, Turbopack dev server, home page rendering backend health
  status.
- Healthchecks on every service; `depends_on: service_healthy` so the
  dependency tree comes up in order.
- Port remapping to avoid host collisions: Postgres 5433, Redis 6380,
  Next.js 3001. Django stays on 8000.
- `.env.example` documenting all environment variables.
- `contracts/` placeholder (populated in subsystem 7).

### Verify gate

`docker compose up -d`; all services reach `healthy` within ~60s;
`curl http://localhost:8000/health/` returns
`{"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}`;
`curl http://localhost:3001/` returns 200.

[Unreleased]: https://github.com/onceuponaprince/yurika.space/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.2.0
[0.1.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.1.0
