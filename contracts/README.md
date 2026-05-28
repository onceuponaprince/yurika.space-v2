# Yurika Contracts

Foundry workspace for the on-chain primitives that back the Yurika
domain-fractionalization system. Pairs with the Django backend (off-
chain ledger), Neo4j knowledge graph, and Next.js frontend that live
elsewhere in this monorepo.

## Contracts

| Contract         | Role                                                      |
|------------------|-----------------------------------------------------------|
| `YurikaVault`    | Locks domain ownership credentials keyed by `bytes32 domainId`. Governance-gated pause + shard linking. |
| `ShardToken`     | ERC-20 fractional-ownership token + sale campaign. Payment-token-agnostic: ETH (`address(0)`) or any ERC-20. |
| `ShardFactory`   | Deploys one `ShardToken` per vaulted domain. The factory IS the vault's governance — only it can link shard contracts. |
| `MockUSDC`       | 6-decimal mock ERC-20 used for tests + testnet deploys. On mainnet, point ShardTokens at the canonical USDC address. |
| `YurikaGovernor` | Minimal on-chain governance bound to a single `ShardToken`. Voting weight = shard balance at vote time. |

## Quick start

Foundry must be installed (`forge --version`). Repo state is portable:
`git clone` then `forge build` works out of the box.

```bash
# Build
forge build

# Run all tests (51 cases across 4 suites)
forge test

# Verbose test output with gas tracking
forge test -vvv
```

## Local deploy (anvil)

```bash
# In one terminal:
anvil

# In another:
forge script script/Deploy.s.sol \
  --rpc-url http://127.0.0.1:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast
```

Anvil's first account key is deterministic and only valid for local
testing. Receipts land in `broadcast/Deploy.s.sol/31337/`.

## Testnet deploy (Base Sepolia)

```bash
# 1. Copy and fill in .env
cp .env.example .env
# Edit .env: BASE_SEPOLIA_RPC_URL, DEPLOYER_PRIVATE_KEY, BASESCAN_API_KEY

# 2. Fund the deployer wallet
#    Faucet: https://docs.base.org/docs/tools/network-faucets/

# 3. Deploy + verify
./deploy-base-sepolia.sh
```

Receipts land in `broadcast/Deploy.s.sol/84532/run-latest.json`.

Extract addresses for the backend's `vault_contract_address` /
`shard_contract_address` columns:

```bash
jq -r '.transactions[] | select(.contractAddress) | "\(.contractName)=\(.contractAddress)"' \
  broadcast/Deploy.s.sol/84532/run-latest.json
```

## Architecture notes

**Why a factory pattern?** The vault's `linkShardContract()` is
governance-only — it has to be, otherwise a malicious caller could
overwrite the legitimate shard-contract pointer for any vaulted
domain. The factory holds that privilege because it's the only thing
that should ever be creating shard contracts. Founders can't bypass
the factory to skip the link step.

**Why predict the factory address at vault deploy?** YurikaVault's
`governance` is `immutable`. To make the factory the only authorized
linker, we compute the factory's CREATE-nonce address before the
vault is deployed, then pass it as the vault's constructor arg.

**Why payment-token-agnostic ShardToken?** The off-chain marketplace
prices campaigns in USD. On-chain, this means USDC payments are
first-class. But early testnet deploys benefit from accepting native
ETH (no separate token approval step). One contract serving both
paths is cheaper bytecode + simpler operational story.

**Known v0.7.0 limitations** (deferred to later patches):

- `YurikaGovernor` reads voting weight at vote time, not at proposal
  snapshot. A holder can split shards across two wallets and vote
  twice. Snapshot voting (ERC-20Votes pattern) is a future ShardToken
  upgrade.
- No platform/referral fees on shard sales. The original `TaxManager`
  was cut from S7 scope; founder gets 100% of proceeds. Re-add when
  the off-chain accounting model is settled.
- `YurikaVault.withdraw()` is founder-only with no shard-holder
  approval gate. A real product would require shard-holder
  supermajority approval if shards are outstanding.
