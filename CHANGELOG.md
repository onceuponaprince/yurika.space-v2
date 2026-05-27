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

- Subsystem 5 — Knowledge Graph (Neo4j sync + discovery)
- Subsystem 6 — Frontend pages (App Router + wallet UX)
- Subsystem 7 — Smart contracts (Foundry → Base Sepolia)
- Subsystem 8 — Celery + email + observability

## [0.4.1] — 2026-05-27 — Dev panel slash-normalization fix

### Fixed

- Dev panel's "authenticated request" section now auto-appends a
  trailing slash to relative URLs that lack one. Django's
  `APPEND_SLASH=True` (default) redirects GET via 301 but raises
  `RuntimeError` on POST/PUT/DELETE because the request body can't
  survive a redirect, surfacing as a 500. Client-side normalization
  is cheaper than disabling `APPEND_SLASH` server-wide and less
  surprising than the 500. Absolute URLs (http://...) are left alone.

## [0.4.0] — 2026-05-27 — Subsystem 4: Shards / Marketplace

### Added

- `apps.marketplace` — new app introducing `ShardCampaign` (one per
  Domain, OneToOne) and `ShardHolding` (per `(campaign, holder)`
  pair, unique-together).
- `ShardCampaign` integrates with Domain's existing 7-state lifecycle.
  Creating a campaign transitions the parent Domain `VAULTED →
  SHARDING`; calling `/activate/` moves `SHARDING → ACTIVE`; hitting
  `funding_target_usd` during a purchase auto-transitions
  `ACTIVE → COMPLETED`.
- `ShardCampaign.funding_percentage` and `.total_cap_usd` derived
  properties. `clean()` enforces `total_shards > 0`, `price > 0`,
  `funding_target ≤ total_shards * price`, `shards_available ≤
  total_shards`, and `ends_at > starts_at` when both set.
- `Project.campaign` OneToOne to `ShardCampaign` — completes the
  founder-side coupling deferred in S3.
- Endpoints:
  - `GET  /api/campaigns/`               public marketplace listing
                                          (filterable by `?status=`)
  - `POST /api/campaigns/`               founder creates a campaign for
                                          their VAULTED domain
  - `GET  /api/campaigns/<id>/`          public detail
  - `PATCH /api/campaigns/<id>/`         owner edit; only while in
                                          SHARDING (pre-activation)
  - `POST /api/campaigns/<id>/activate/` owner moves SHARDING → ACTIVE
  - `POST /api/campaigns/<id>/buy/`      curator purchases shards;
                                          atomic via `select_for_update`
  - `GET  /api/holdings/`                authenticated user's own
                                          holdings across all campaigns
- Atomic purchase flow: campaign row locked for the transaction;
  `shards_available` decremented, `funding_raised_usd` incremented,
  `ShardHolding` upserted via `get_or_create` then incremented on
  repeat buys. Each purchase records a mock 32-byte `tx_hash` (real
  on-chain tx hashes land in S7).
- 28 new pytest cases: model defaults + validators + unique
  constraints, campaign creation gated on Domain state + ownership,
  marketplace list is public, activation is owner-only, full buy flow
  (happy path, oversold rejection, wrong-state rejection, repeat-buy
  upsert, two-curator isolation, auto-COMPLETED when target hit,
  unauthenticated rejection), holdings list isolation, plus the S4
  verify-gate end-to-end test walking a founder + curator through
  the whole pipeline.

### Verify gate

`TestS4VerifyGate.test_curator_can_buy_shards_end_to_end` exercises:
founder vaults domain → founder creates campaign (SHARDING) →
founder activates (ACTIVE) → curator buys 250 shards →
`funding_raised_usd = $2500` and the curator's `/holdings/` reflects
the purchase. Whole flow through DRF's `APIClient` over real HTTP.

## [0.3.0] — 2026-05-27 — Subsystem 3: Domains + DNS verify + vaulting

### Added

- `apps.core` — shared `BaseModel` (UUID PK + `created_at` / `updated_at`)
  inherited by every domain-layer model from here on.
- `apps.domains.models.Domain` — root asset of the Yurika ecosystem.
  Web domain (`name` + `tld`) owned by a founder, with a 7-state
  lifecycle (`pending → verified → vaulted → sharding → active →
  completed`, plus `withdrawn` from any non-terminal state).
- `Domain.transition_to(new_status)` — enforces an allowed-transitions
  table so the lifecycle can only move forward (or to `withdrawn`).
  Cannot skip states (e.g. `pending → vaulted` is rejected).
- `Domain.verification_nonce` — per-domain secret published by the
  founder in a DNS TXT record at `_yurika-verify.<fqdn>`. Auto-
  generated via `secrets.token_urlsafe(16)`.
- `apps.domains.models.Project` — founder's project artifact
  (pitch deck, repository, media URLs). Standalone for now; OneToOne
  to `ShardCampaign` lands in S4.
- `apps.domains.dns.lookup_txt(record_name)` — thin wrapper around
  `dnspython` with explicit `DNSLookupError` for non-NXDOMAIN
  resolver failures. Kept in its own module so tests can monkeypatch
  the function without touching the network.
- CRUD endpoints under `/api/domains/` and `/api/projects/`. Owner-
  isolated via DRF `IsOwner` permission + queryset filter (defense
  in depth). Domain `DELETE` soft-deletes via transition to
  `withdrawn`; Project `DELETE` is a hard delete.
- `GET  /api/domains/<id>/verify-instructions/` — returns the TXT
  record name and value the founder must publish.
- `POST /api/domains/<id>/verify/` — backend resolves the TXT record,
  matches against the stored nonce, transitions `pending → verified`.
  Returns 400 on missing/wrong TXT, 424 on DNS resolver failure,
  409 if the domain isn't in `pending`.
- `POST /api/domains/<id>/vault/` — transitions `verified → vaulted`
  and writes mock contract addresses for `vault_contract_address`
  and `shard_contract_address`. Real contract deployment lands in S7
  per `contracts/README.md`.
- `dnspython>=2.7` pinned in `pyproject.toml`.
- 42 new pytest cases covering: model defaults + nonce generation +
  unique constraint, 7-state transition table (including terminal-
  state rejection), CRUD with owner isolation, DNS verify happy path
  + missing-TXT + wrong-value + resolver-error + idempotency, vault
  endpoint correctness, full end-to-end `pending → verified →
  vaulted` lifecycle through HTTP.

### Verify gate

`TestS3VerifyGate.test_full_lifecycle_pending_verified_vaulted` walks
the entire founder flow through DRF's `APIClient`: POST create domain,
GET verify-instructions, POST verify (with mocked DNS), POST vault.
Live curl smoke against the container confirms `/api/domains/` and
`/api/domains/<id>/verify-instructions/` respond as documented.

## [0.2.1] — 2026-05-27 — Dev tools

### Added

- `GET /api/auth/whoami/` — JWT-protected endpoint returning the
  authenticated user's `id` and `wallet_address`. Pairs with the dev
  panel for round-trip verification of issued tokens.
- `GET /dev/panel/` (DEBUG-only) — single-page HTML+JS panel for
  walking the SIWE flow end-to-end without MetaMask. Generates an
  ephemeral keypair in-browser via ethers.js, mints a nonce, signs,
  verifies, and lets you fire arbitrary authenticated requests with
  the resulting Bearer token. 404s when DEBUG=False.
- 4 tests for `/whoami/` covering happy path, missing-auth 401,
  malformed-bearer 401, and multi-user discrimination.

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

[Unreleased]: https://github.com/onceuponaprince/yurika.space/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.4.1
[0.4.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.4.0
[0.3.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.3.0
[0.2.1]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.2.1
[0.2.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.2.0
[0.1.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.1.0
