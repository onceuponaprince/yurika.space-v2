# On-chain ↔ Off-chain Integration Plan

> Status: **design** (pre-S8). Nothing in this doc is wired yet. This is
> the contract between the Foundry layer (`contracts/`) and the Django
> backend (`apps/backend/`) that S8 will implement.

## 1. The seam today

The two ledgers were designed to reconcile but currently don't.

| Layer | What it tracks | Source of truth today |
|---|---|---|
| Postgres (`marketplace`, `domains`) | campaigns, holdings, funding raised, domain lifecycle | **everything** |
| Chain (`YurikaVault`, `ShardToken`) | custody, shard balances, sale proceeds | nothing reads it |

Concrete gaps:

- `Domain.vault_contract_address` / `shard_contract_address` / `chain_id`
  exist (`domains/models.py:69-71`) but **nothing writes them**.
- `marketplace.views.buy_shards` increments `funding_raised_usd` in
  Postgres and writes a `_mock_tx_hash()`. No chain call. The docstring
  admits it: *"Real on-chain tx hashes arrive in S7."*
- `ShardHolding.tx_hash` (`CharField(max_length=66)`) is the empty slot
  waiting for a real `0x…` hash.

## 2. Design decision: chain is the source of truth

**The DB is an index of chain state, not the authority.**

Rationale: `ShardToken` is a transferable ERC-20. A holder can move
shards peer-to-peer — a DEX, a direct `transfer()`, an OTC deal — with
**zero platform involvement**. Any design where Postgres is authoritative
goes stale the instant that happens, and the marketplace would show
ownership that no longer matches the chain. The only way the DB stays
correct is to derive holdings from chain events, including `Transfer`.

This makes the off-chain `buy_shards` write a *projection*, not a
*decision*. See §7 for what happens to the mock path.

## 3. The join key

The layers do **not** share an integer id. The vault keys everything by

```
domainId = keccak256(abi.encodePacked(fqdn))   // YurikaVault.domainIdOf(string)
```

So the indexer maps `domainId → Domain` by recomputing the hash off-chain
and matching against a stored column. **Schema add:** persist the hash so
the lookup is an indexed equality, not a full-table recompute.

```python
# domains/models.py — Domain
domain_id_hash = models.CharField(max_length=66, blank=True, db_index=True)
# populate on save: "0x" + keccak(fqdn.encode()).hex()  (eth_utils.keccak)
```

> The hash uses `encodePacked` of the raw FQDN string. The Python side
> MUST normalise the FQDN identically to whatever the founder signs
> (lowercase, no trailing dot) or the hashes won't match. Pin the
> normalisation in one shared helper and unit-test it against a
> `cast keccak` fixture.

## 4. Event catalog

Topic0 hashes computed with `cast keccak` against the deployed ABIs.
These are the log filters the indexer subscribes to.

| Event | Emitted by | topic0 | Drives |
|---|---|---|---|
| `DomainVaulted(bytes32,address,bytes32,uint256)` | YurikaVault | `0xdada3c54…26749c8` | set `vault_contract_address`, flip → VAULTED |
| `ShardTokenDeployed(bytes32,address,address,address)` | ShardFactory | `0xe0bc30e6…c9150b79` | set `shard_contract_address`, flip → SHARDING |
| `ShardsPurchased(address,uint256,uint256)` | ShardToken | `0x12271880…c6110169` | upsert holding, += funding_raised |
| `CampaignEnded(uint256,uint256)` | ShardToken | `0x5a31f5ed…ff8122b4f` | flip → COMPLETED |
| `Transfer(address,address,uint256)` | ShardToken | `0xddf252ad…f523b3ef` | reconcile holdings on **secondary** transfers |

Indexed (topic) params are recoverable without the ABI; non-indexed
params (`shards`, `paid`, `metadataHash`, `timestamp`) require ABI
decoding of the `data` field.

> `Transfer` fires on every shard movement, including the primary
> mint-on-purchase (`address(this) → buyer`). To avoid double-counting,
> the indexer treats `ShardsPurchased` as the primary-sale signal and
> only acts on `Transfer` when **neither** party is the ShardToken
> contract itself (i.e. a genuine secondary transfer).

## 5. Indexer architecture (the S8 backbone)

A Celery beat task per chain, polling in confirmed-block windows.

```
celery beat ──tick(15s)──▶ index_chain_events(chain_id)
                              │
                              ├─ from_block = ChainCursor.last_indexed + 1
                              ├─ to_block   = eth_blockNumber − CONFIRMATIONS
                              ├─ eth_getLogs(address=[known shard+vault], topics=[…])
                              ├─ for each log: dispatch by topic0 → handler
                              │      handler upserts in a transaction.atomic()
                              └─ ChainCursor.last_indexed = to_block
```

- **`CONFIRMATIONS`** (e.g. 5 on Base) buys reorg safety: only index logs
  that are deep enough that a reorg is implausible. Never index the head.
- **Idempotency:** every handler keys on `(tx_hash, log_index)`. Re-running
  the same window must be a no-op. Store processed events in a
  `ChainEvent` table with a unique constraint on `(chain_id, tx_hash,
  log_index)`.
- **Cursor:** `ChainCursor(chain_id, last_indexed_block)` — one row per
  chain. The whole loop is resumable from this single integer.

New models:

```python
# marketplace/models.py (or a new `chain` app)
class ChainCursor(BaseModel):
    chain_id = models.IntegerField(unique=True)
    last_indexed_block = models.BigIntegerField(default=0)

class ChainEvent(BaseModel):
    chain_id   = models.IntegerField(db_index=True)
    tx_hash    = models.CharField(max_length=66)
    log_index  = models.IntegerField()
    block_number = models.BigIntegerField()
    topic0     = models.CharField(max_length=66, db_index=True)
    payload    = models.JSONField()          # decoded args
    processed_at = models.DateTimeField(null=True)
    class Meta:
        unique_together = [("chain_id", "tx_hash", "log_index")]
```

## 6. The optimistic buy flow (UX layer on top of §5)

The indexer guarantees *eventual* correctness; this gives the buyer
*immediate* feedback without making the DB authoritative.

```
1. POST /campaigns/{id}/buy/intent   → backend returns the calldata +
                                        shard_contract_address + chain_id
2. frontend signs+sends via wagmi    → gets tx_hash, POSTs it back
3. ShardHolding row created PENDING with the real tx_hash
4. indexer sees ShardsPurchased(tx)  → flips PENDING → CONFIRMED,
                                        sets authoritative shards_held
5. (sweep) PENDING older than N min   → mark ABANDONED, don't count funding
```

**Schema add:** `ShardHolding.status` ∈ {PENDING, CONFIRMED, ABANDONED}.
`funding_raised_usd` is recomputed from CONFIRMED holdings only — never
incremented optimistically.

## 7. Migration: what happens to the mock path

`buy_shards` and `_mock_tx_hash()` are removed (or gated behind a
`SETTLEMENT_MODE=mock` dev flag). Production buys go through §6. Any
holdings created before the contract was live carry a sentinel
`tx_hash=""` and are handled by the conflict policy below.

## 8. ⬚ DECISION LEFT TO YOU — conflict-resolution policy

When the indexer reads chain reality that disagrees with an existing
off-chain row, what wins? This single policy shapes the whole reconciler.
It lives in one function; everything else is mechanical.

```python
# marketplace/reconcile.py
def resolve_holding_conflict(
    db_holding: ShardHolding,       # what Postgres currently believes
    chain_shards: int,              # authoritative balance from chain events
    event: ChainEvent,              # the event that triggered reconciliation
) -> ShardHolding:
    """Return the holding as it should be persisted after reconciliation.

    Cases to weigh:
      - db_holding.tx_hash == ""          → legacy mock row, never on-chain
      - chain_shards == 0 and db > 0      → holder sold/transferred away
      - chain_shards != db_holding.shards_held (drift)
      - a PENDING row whose tx never confirmed
    """
    # TODO(you): the 5-10 lines that decide who wins. See guidance below.
    raise NotImplementedError
```

Guidance — the trade-offs:

- **Chain-always-wins (strict):** simplest, trustless, but silently
  deletes legacy mock holdings that represent real off-chain commitments
  from before launch. Honest but potentially user-hostile.
- **Chain-wins-but-flag:** overwrite `shards_held` from chain, but if the
  row was a non-empty mock (`tx_hash == ""` and `shards_held > 0`), mark
  it `RECONCILE_REVIEW` instead of zeroing — a human (or migration script)
  decides. Safer for the launch boundary, more states to manage.
- **Refuse-to-shrink:** only ever raise `shards_held` to match chain,
  never lower it. Protects holders but lets the DB over-report ownership
  after a transfer-out — which is exactly the staleness §2 warns about.
  Tempting and wrong for an ownership product.

Recommendation: **chain-wins-but-flag** for the launch window, then a
follow-up patch that drops the flag path once all legacy mock rows are
migrated and switches to strict chain-always-wins.

## 9. S8 task breakdown (derived from the above)

1. `domain_id_hash` column + shared FQDN-normalise+keccak helper + fixture test
2. `ChainCursor` + `ChainEvent` models + migrations
3. Web3 client config (RPC URL per chain, `CONFIRMATIONS` constant)
4. `index_chain_events` Celery beat task + per-topic handlers (idempotent)
5. `ShardHolding.status` + `funding_raised` recompute-from-CONFIRMED
6. `/buy/intent` endpoint (returns calldata) + tx_hash callback endpoint
7. `resolve_holding_conflict` (§8) + reconcile sweep task
8. retire/gate the mock `buy_shards` path
9. Sentry on the indexer loop; alert on cursor stall (no advance in N min)

> Items 3-4 and 9 are the Celery + observability core of S8. The seam and
> the last subsystem are the same work.
