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

- Subsystem 7 — Smart contracts (Foundry → Base Sepolia)
- Subsystem 8 — Celery + email + observability

## [0.6.0] — 2026-05-28 — Subsystem 6: Frontend (Neon Ledger UI)

### Added

- Frontend now ships the **Neon Ledger** terminal design system, ported
  from `~/code/yurika.space`. Yurika Lime (`#ccff00`) on The Void
  (`#0d0d0d`), Data Purple (`#9d00ff`) for shards/metrics, CRT scanline
  overlay, dithered patterns, blinking cursor, and the global
  `border-radius: 0` constraint (terminal aesthetic — sharp corners
  everywhere).
- Three typefaces wired via `next/font/google`: **Press Start 2P**
  (display), **JetBrains Mono** (data), **Inter** (body). Exposed as
  CSS variables `--font-display`, `--font-mono`, `--font-body`.
- Reusable CSS primitives: `.terminal-window` (the framed box with
  the `█ █ █` header), `.btn-primary` / `.btn-ghost` /
  `.btn-destructive`, `.terminal-input`, `.status-pill` (auto-colours
  by `data-status`), `.glow-lime` / `.glow-purple` / `.glow-red`.
- Lib layer:
  - `lib/api.ts` — typed `ApiClient` with `setToken()`, automatic
    Bearer header, asymmetric base URLs (browser hits
    `localhost:8000/api`, SSR hits `django:8000/api` over the docker
    network).
  - `lib/types.ts` — TS shapes matching every backend serializer.
  - `lib/auth-store.ts` — Zustand persist for JWT pair + user, with
    `hydrateApi()` that re-attaches the token to the api singleton
    after rehydration from localStorage.
  - `lib/siwe.ts` — full SIWE round-trip (`fetchSiweMessage`,
    `verifySiwe`, `signIn`). The backend is the source of truth for
    the nonce + canonical message; the client just signs what it
    receives. (The original frontend's client-minted nonce was a
    subtle bug — fixed here.)
  - `lib/dev-account.ts` — browser-side ephemeral keypair via viem
    (mirrors the dev panel approach). MetaMask / WalletConnect lands
    in a later patch.
- Pages:
  - `/` — landing with terminal hero, three feature cards (VAULT /
    SHARD / DISCOVER), stack overview.
  - `/login` — wallet connect + SIWE sign-in panel. Mints (or
    reuses) an ephemeral keypair, runs the full nonce → sign →
    verify → JWT cycle, hydrates the auth store, redirects to
    `/app`.
  - `/app` — Command Center. Auth-gated via `app/app/layout.tsx`
    (redirects to `/login` if no JWT after rehydration). Shows
    graph stats + launch task queue.
  - `/app/domains` — founder domain ledger: submit, view TXT-record
    instructions, verify DNS, force-vault (DEBUG-only shortcut),
    vault transition.
  - `/app/marketplace` — campaign creator (for vaulted domains) +
    marketplace browser + activate/buy + holdings ledger.
  - `/app/discover` — graph discovery feed with personalized /
    trending toggle.
- Reusable React components: `<Providers>` (React Query +
  auth-store hydration), `<Nav>` (active-route highlight + sign-out),
  `<TerminalWindow>`, `<Button>`, `<SignInPanel>`.
- `scripts/smoke.mjs` — end-to-end pipeline test that drives the
  same primitives (viem + fetch) the browser uses, against the live
  backend. Walks the entire user journey from ephemeral wallet →
  SIWE → JWT → domain → vault → campaign → activate → discovery in
  one pass. Useful as a regression gate before frontend releases.

### Changed

- Removed the placeholder home page that just rendered the backend
  health check JSON. Landing now shows the proper Yurika branding.
- `docker-compose.yml`: `INTERNAL_API_BASE_URL` now includes the
  `/api` suffix to mirror `NEXT_PUBLIC_API_BASE_URL`. The base URLs
  are now symmetric on both sides of the docker network.
- `tsconfig.json` auto-formatted by Next.js on first compile (added
  `jsx: "react-jsx"`, normalized array indentation). Harmless.
- New runtime deps: `viem 2.21.45`, `wagmi 2.13.5`, `zustand 5.0.2`,
  `@tanstack/react-query 5.62.0`. No third-party wallet provider
  yet (Dynamic.xyz deferred to a later patch).

### Scope notes

This subsystem deliberately scopes down from the original
`~/code/yurika.space` reference implementation:

- **In**: Neon Ledger design tokens, full lib layer, all 6
  user-facing pages, end-to-end pipeline working in browser.
- **Out (v0.6.x patches)**: Three.js marketing hero, Dynamic.xyz
  wallet provider, Radix UI overlays, Framer Motion animations,
  Supabase waitlist. None of these are blockers for the verify
  gate; they're polish that lands when there's a story for the
  memory budget and bundle size.

### Verify gate

`apps/frontend/scripts/smoke.mjs` walks the complete pipeline end-
to-end in under 3 seconds against the live docker compose stack.
All 6 frontend routes (`/`, `/login`, `/app`, `/app/domains`,
`/app/marketplace`, `/app/discover`) render with the design system
applied. The user can sign in with a fresh wallet, vault a domain,
create + activate a campaign, and see live graph statistics —
entirely through the UI, no curl required.

## [0.5.0] — 2026-05-27 — Subsystem 5: Knowledge Graph

### Added

- `apps.graph` — new app that mirrors Postgres entities into Neo4j
  and exposes a discovery API. neomodel 6.1 wired against the bolt URL
  Django already knew about (the container has been running healthy
  since S1 with zero nodes; S5 finally writes to it).
- Three `StructuredNode` types — `UserNode`, `DomainNode`, `ProjectNode`
  — keyed on the Postgres UUID (`StringProperty(unique_index=True)`,
  not `UniqueIdProperty`, so the SQL UUID is the single source of
  truth and the Neo4j store can't diverge into its own identity space).
- Relationships: `(User)-[:OWNS]->(Domain)`, `(User)-[:HOLDS]->(Domain)`,
  `(Domain)-[:HAS_PROJECT]->(Project)`.
- `apps.graph.sync` — idempotent upsert functions (`_upsert_user`,
  `_upsert_domain`, `_upsert_project`, `_upsert_holding`). Each
  wraps its body in a broad try/except and returns `None` on failure
  instead of raising — Neo4j outage degrades to "graph view is stale"
  rather than "user request 500s".
- `apps.graph.signals` — `post_save` receivers on `User`, `Domain`,
  `Project`, and `ShardHolding` that drive the sync. Registered in
  `GraphConfig.ready()` so target apps are guaranteed loaded.
- Discovery endpoint at `GET /api/graph/discover/` with three modes:
  - `?mode=trending`     — public; ranks domains by distinct holder
                            count. Defaults for anonymous callers.
  - `?mode=personalized` — auth required; 1-hop peer-curator graph
                            traversal. Defaults for authenticated
                            callers.
  - `?mode=stats`        — public; coarse node/edge counts. Useful
                            for the dev panel and as a fallback.
- Personalized discovery Cypher implements three product decisions:
  - **Peer definition**: Jaccard-style — every user sharing ≥1
    holding counts as a peer, weighted by overlap count.
  - **Ranking**: sum of peer weights per candidate domain
    (collaborative-filter score; both popularity-within-tribe and
    single-very-aligned-peer contribute).
  - **Exclusions**: drops domains the caller already holds, domains
    they own as founder, and any in `withdrawn` or `completed` status.
- 31 new pytest cases covering: sync layer (upserts, idempotency,
  silent failure on Neo4j outage), signal-driven sync, trending and
  stats Cypher queries, endpoint mode dispatch + default routing,
  personalized discovery exercising each of the three design
  decisions individually, plus the S5 verify-gate end-to-end test.

### Changed

- `apps.graph` added to `INSTALLED_APPS`; `/api/graph/` mounted in
  `config/urls.py`.
- Test isolation: graph tests use an autouse `clean_neo4j` fixture
  (clear before + after each test) so prior runs from other apps
  don't pollute results. Other apps' tests are unaffected — their
  signal-driven Neo4j writes happen but don't impact assertions.

### Verify gate

`TestS5VerifyGate.test_holdings_flow_through_to_discovery` walks the
full pipeline: create founder + curator + active campaign in Postgres,
let signals mirror to Neo4j automatically, then hit
`GET /api/graph/discover/?mode=trending` and confirm the domain comes
back as `{fqdn: "yurika.space", score: 1}`. Live curl smoke against
the container confirms all three modes respond as documented.

## [0.4.2] — 2026-05-27 — Guided dev panel

### Added

- Dev panel rewritten as a top-to-bottom guided flow with state
  carried across sections: ① health → ② one-click SIWE auth →
  ③ submit domain → ④ create + activate campaign → ⑤ buy shards →
  ⑥ list holdings → ⑦ advanced (custom request). Each section
  enables the next only when its prerequisite is met; a sticky
  state bar at the top shows wallet, JWT status, current domain,
  and campaign funding %.
- `POST /api/domains/<id>/dev-force-vault/` — DEBUG-only shortcut
  that skips DNS verification and jumps a domain straight to
  VAULTED with mock contract addresses. 404s when `DEBUG=False`.
  Exists so the panel can exercise S3 → S4 → onward without
  publishing real DNS TXT records.
- 3 new pytest cases for the force-vault endpoint, including a
  test that confirms it 404s when DEBUG is disabled (the only
  thing standing between this shortcut and a production attack
  surface).

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

[Unreleased]: https://github.com/onceuponaprince/yurika.space/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.6.0
[0.5.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.5.0
[0.4.2]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.4.2
[0.4.1]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.4.1
[0.4.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.4.0
[0.3.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.3.0
[0.2.1]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.2.1
[0.2.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.2.0
[0.1.0]: https://github.com/onceuponaprince/yurika.space/releases/tag/v0.1.0
