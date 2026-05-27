/**
 * Subsystem 6 end-to-end smoke test.
 *
 * Drives the same primitives the browser uses (viem + fetch) against
 * the live Django backend, exercising every public-facing endpoint
 * the frontend hits. If this passes, the browser flow works too —
 * the only thing the script doesn't render is the CSS.
 *
 * Usage (from the running nextjs container):
 *   docker compose exec nextjs node scripts/smoke.mjs
 */

import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const BASE = process.env.INTERNAL_API_BASE_URL || "http://django:8000/api";

let accessToken = null;

async function call(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${path} -> ${JSON.stringify(body)}`);
  }
  return body;
}

function header(label) {
  console.log(`\n=== ${label} ===`);
}

async function main() {
  // 1. Generate a fresh ephemeral keypair, mirroring lib/dev-account.ts.
  const key = generatePrivateKey();
  const account = privateKeyToAccount(key);
  console.log("ephemeral wallet:", account.address);

  // 2. Mint a SIWE nonce + canonical message.
  header("SIWE nonce");
  const { message } = await call(
    `/auth/wallet/nonce/?address=${account.address.toLowerCase()}`,
  );
  console.log("got message (", message.length, "chars)");

  // 3. Sign + verify -> JWT pair.
  header("SIWE verify");
  const signature = await account.signMessage({ message });
  const { access, refresh, wallet_address } = await call(
    "/auth/wallet/verify/",
    {
      method: "POST",
      body: JSON.stringify({ message, signature }),
    },
  );
  accessToken = access;
  console.log("signed in as:", wallet_address);
  console.log("access token:", access.slice(0, 30), "...");

  // 4. /whoami round-trip.
  header("whoami");
  const me = await call("/auth/whoami/");
  console.log("whoami:", me);

  // 5. Create a domain.
  header("domain create");
  const domain = await call("/domains/", {
    method: "POST",
    body: JSON.stringify({
      name: `smoke-${Date.now()}`,
      tld: "test",
      description: "S6 frontend smoke",
    }),
  });
  console.log("created:", domain.fqdn, "status =", domain.status);

  // 6. Force-vault (skip DNS in dev).
  header("domain force-vault");
  const vaulted = await call(`/domains/${domain.id}/dev-force-vault/`, {
    method: "POST",
  });
  console.log("vaulted:", vaulted.fqdn, "status =", vaulted.status);

  // 7. Create a campaign on the vaulted domain.
  header("campaign create");
  const campaign = await call("/campaigns/", {
    method: "POST",
    body: JSON.stringify({
      domain: domain.id,
      title: `Smoke campaign for ${domain.fqdn}`,
      thesis: "S6 smoke test",
      total_shards: 100,
      price_per_shard_usd: "1",
      funding_target_usd: "100",
    }),
  });
  console.log("campaign created, funding %", campaign.funding_percentage);

  // 8. Activate -> SHARDING -> ACTIVE.
  header("campaign activate");
  const active = await call(`/campaigns/${campaign.id}/activate/`, {
    method: "POST",
  });
  console.log("activated, campaign id:", active.id);

  // 9. Discovery — trending mode (public).
  header("discover · trending");
  const trending = await call("/graph/discover/?mode=trending");
  console.log("trending results:", trending.results.length);

  // 10. Discovery — personalized mode (authenticated).
  header("discover · personalized");
  const personalized = await call("/graph/discover/?mode=personalized");
  console.log("personalized mode:", personalized.mode, "results:", personalized.results?.length ?? 0);

  // 11. Graph stats.
  header("discover · stats");
  const stats = await call("/graph/discover/?mode=stats");
  console.log("graph stats:", stats.stats);

  console.log("\nOK — full lib + backend pipeline works end-to-end.");
}

main().catch((err) => {
  console.error("\nSMOKE FAILED:", err.message);
  process.exit(1);
});
