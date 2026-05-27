/**
 * Browser-side ephemeral keypair generation, mirroring the dev panel.
 *
 * For S6.0 we don't ship Dynamic.xyz or MetaMask integration — wallet
 * UX upgrade is a later subsystem. To keep the verify gate exercisable
 * (a curator can SIWE in via the UI), we let the user mint a fresh
 * ephemeral keypair in-browser. Persisted to localStorage so a refresh
 * doesn't sign them out.
 *
 * This is NOT a production wallet model. It exists so the rest of the
 * frontend stack can be built and tested today. Real wallet connect
 * lands in a later patch.
 */
"use client";

import { privateKeyToAccount, generatePrivateKey } from "viem/accounts";
import type { Account, Hex } from "viem";

const STORAGE_KEY = "yurika-dev-account";

function loadPrivateKey(): Hex | null {
  if (typeof window === "undefined") return null;
  return (localStorage.getItem(STORAGE_KEY) as Hex | null) ?? null;
}

function savePrivateKey(key: Hex): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, key);
}

export function getOrCreateDevAccount(): Account {
  let key = loadPrivateKey();
  if (!key) {
    key = generatePrivateKey();
    savePrivateKey(key);
  }
  return privateKeyToAccount(key);
}

export function rotateDevAccount(): Account {
  const key = generatePrivateKey();
  savePrivateKey(key);
  return privateKeyToAccount(key);
}

export function clearDevAccount(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}
