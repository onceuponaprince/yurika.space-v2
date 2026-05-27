/**
 * SIWE sign-in flow against the Yurika backend.
 *
 * The backend is the source of truth for the nonce + canonical SIWE
 * message. We just fetch, sign with viem, post back. This avoids the
 * common bug where clients mint their own nonces (defeats replay
 * protection).
 */
import type { Account } from "viem";

import { api } from "@/lib/api";
import type { NonceResponse, TokenPair } from "@/lib/types";

export async function fetchSiweMessage(walletAddress: string): Promise<NonceResponse> {
  return api.get<NonceResponse>(
    `/auth/wallet/nonce/?address=${encodeURIComponent(walletAddress)}`,
  );
}

export async function verifySiwe(message: string, signature: string): Promise<TokenPair> {
  return api.post<TokenPair>("/auth/wallet/verify/", { message, signature });
}

/**
 * Full sign-in cycle: nonce → sign → verify.
 *
 * Given a viem Account (which abstracts over private-key, mnemonic,
 * or wallet-injected accounts), this returns the JWT pair on success.
 * Throws on signature failure or backend rejection.
 */
export async function signIn(account: Account): Promise<TokenPair> {
  if (!account.address) {
    throw new Error("Account has no address");
  }
  if (!account.signMessage) {
    throw new Error("Account does not support signing messages");
  }
  const address = account.address.toLowerCase();
  const { message } = await fetchSiweMessage(address);
  const signature = await account.signMessage({ message });
  return verifySiwe(message, signature);
}
