/**
 * TypeScript types mirroring the Django backend's serializer shapes.
 * Source of truth: apps/backend/apps/*/serializers.py and models.py.
 */

export interface User {
  id: number;
  wallet_address: string;
}

export type DomainStatus =
  | "pending"
  | "verified"
  | "vaulted"
  | "sharding"
  | "active"
  | "completed"
  | "withdrawn";

export interface Domain {
  id: string;
  owner: number;
  name: string;
  tld: string;
  fqdn: string;
  description: string;
  status: DomainStatus;
  verification_nonce: string;
  vault_contract_address: string;
  shard_contract_address: string;
  chain_id: number;
  created_at: string;
  updated_at: string;
}

export interface VerifyInstructions {
  record_name: string;
  record_value: string;
  fqdn: string;
}

export interface ShardCampaign {
  id: string;
  domain: string;
  title: string;
  thesis: string;
  total_shards: number;
  shards_available: number;
  price_per_shard_usd: string;
  funding_target_usd: string;
  funding_raised_usd: string;
  funding_percentage: number;
  starts_at: string | null;
  ends_at: string | null;
  governance_enabled: boolean;
  quorum_percentage: number;
  created_at: string;
}

export interface ShardHolding {
  id: string;
  campaign: string;
  holder: number;
  shards_held: number;
  purchase_price_usd: string;
  tx_hash: string;
  created_at: string;
}

export interface DiscoveryResult {
  uid: string;
  fqdn: string;
  status: DomainStatus;
  score: number;
}

export interface DiscoveryResponse {
  mode: "trending" | "personalized" | "stats";
  results?: DiscoveryResult[];
  stats?: {
    users: number;
    domains: number;
    projects: number;
    holds: number;
    owns: number;
  };
}

export interface TokenPair {
  access: string;
  refresh: string;
  wallet_address: string;
}

export interface NonceResponse {
  message: string;
  nonce: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
