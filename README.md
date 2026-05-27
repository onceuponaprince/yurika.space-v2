# yurika.space

Rebuild of [yurika.space](https://yurika.space) from `~/code/yurika.space` (frontend) + `~/code/yurika` (backend + contracts), assembled as a single monorepo with strict memory budgets for local development.

## Repository layout

```
yurika.space/
├── apps/
│   ├── backend/        # Django 5 + DRF + SimpleJWT + Celery
│   └── frontend/       # Next.js 16 App Router + TS + Tailwind + shadcn
├── contracts/          # Foundry (Solidity) — subsystem 7
├── docker-compose.yml  # Local stack with memory caps
└── .env.example
```

## Quick start (subsystem 1 verify gate)

```bash
cp .env.example .env          # fill in nothing yet — defaults work for local dev
docker compose up -d --build  # first build takes ~5 min
docker compose ps             # all services should reach "healthy" within ~60s

# Verify the gate:
curl -s http://localhost:8000/health/ | jq   # -> {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3001/   # -> 200
```

Stop the stack: `docker compose down`. Wipe volumes too: `docker compose down -v`.

## Memory budget

All services are explicitly capped. Total worst-case allocation: **3.5 GB**.

| Service | Cap | Internal tuning |
|---|---|---|
| Postgres 16 | 512 MB | Postgres auto-tunes |
| Neo4j 5 | 1024 MB | heap 512 MB + pagecache 256 MB |
| Redis 7 | 128 MB | `maxmemory 100mb`, eviction `allkeys-lru` |
| Django | 512 MB | runserver in dev |
| Next.js (dev) | 1024 MB | Turbopack, `--max-old-space-size=768` |
| Celery worker | 384 MB | commented out — uncomment for subsystem 8 |

To inspect actual usage: `docker stats`.

## Ports (host → container)

| Service | Host | Reason for shift |
|---|---|---|
| Postgres | 5433 → 5432 | Avoid collision with native Postgres |
| Neo4j HTTP | 7474 → 7474 | — |
| Neo4j Bolt | 7687 → 7687 | — |
| Redis | 6380 → 6379 | Avoid collision with native Redis |
| Django | 8000 → 8000 | — |
| Next.js | 3001 → 3000 | Keep 3000 free for ad-hoc tools |

## Rebuild roadmap

| # | Subsystem | Status | Verify gate |
|---|---|---|---|
| 1 | Infra (Postgres + Neo4j + Redis + Django/Next.js skeletons) | done | All services healthy, `/health/` returns 200 |
| 2 | Auth (`users` app + SIWE + JWT) | done | `POST /api/auth/wallet/verify/` issues JWT |
| 3 | Domains (CRUD + status flow) | done | Full domain lifecycle PENDING → VAULTED |
| 4 | Shards / Marketplace (campaigns + invest) | done | Curator can buy shards |
| 5 | Knowledge Graph (Neo4j sync + discovery) | pending | `/api/graph/discover/` returns nodes |
| 6 | Frontend pages (App Router + wallet UX) | pending | End-to-end flow in browser |
| 7 | Smart contracts (Foundry → Base Sepolia) | pending | `forge test` passes, vault deploy works |
| 8 | Celery + email + observability | pending | Background jobs run, Sentry receives events |

See [CHANGELOG.md](./CHANGELOG.md) for per-subsystem release notes.
Current version: **v0.4.1** (yurika.space-v2).
