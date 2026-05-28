#!/usr/bin/env bash
#
# Deploy YurikaVault + ShardFactory + MockUSDC to Base Sepolia.
#
# Required env vars (from contracts/.env):
#   BASE_SEPOLIA_RPC_URL    public endpoint or your own
#   DEPLOYER_PRIVATE_KEY    funded with Base Sepolia ETH
#   BASESCAN_API_KEY        for source verification
#
# Faucet: https://docs.base.org/docs/tools/network-faucets/

set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${BASE_SEPOLIA_RPC_URL:?missing BASE_SEPOLIA_RPC_URL}"
: "${DEPLOYER_PRIVATE_KEY:?missing DEPLOYER_PRIVATE_KEY}"

VERIFY_FLAGS=""
if [[ -n "${BASESCAN_API_KEY:-}" ]]; then
  VERIFY_FLAGS="--verify --etherscan-api-key ${BASESCAN_API_KEY}"
else
  echo "(no BASESCAN_API_KEY set — skipping source verification)"
fi

forge script script/Deploy.s.sol \
  --rpc-url "$BASE_SEPOLIA_RPC_URL" \
  --private-key "$DEPLOYER_PRIVATE_KEY" \
  --broadcast \
  $VERIFY_FLAGS

echo ""
echo "=== Deploy complete ==="
echo "Broadcast receipts: broadcast/Deploy.s.sol/84532/"
echo ""
echo "Extract addresses for the backend:"
echo "  jq -r '.transactions[] | select(.contractAddress) | \"\\(.contractName)=\\(.contractAddress)\"' \\"
echo "    broadcast/Deploy.s.sol/84532/run-latest.json"
