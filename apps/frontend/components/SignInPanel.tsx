"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/Button";
import { useAuthStore } from "@/lib/auth-store";
import { clearDevAccount, getOrCreateDevAccount, rotateDevAccount } from "@/lib/dev-account";
import { api, ApiError, detailMessage } from "@/lib/api";
import { signIn } from "@/lib/siwe";
import type { User } from "@/lib/types";

/**
 * Wallet "connect" + SIWE sign-in panel.
 *
 * For v0.6.0 the wallet is an in-browser ephemeral keypair (see
 * lib/dev-account.ts). The user clicks a single button which mints
 * (or reuses) the keypair, fetches a SIWE message from the backend,
 * signs it, posts the signed message back, and stores the resulting
 * JWT. The whole round-trip is what the S6 verify gate exercises.
 */
export function SignInPanel() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const sessionUser = useAuthStore((s) => s.user);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewAddress, setPreviewAddress] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      return getOrCreateDevAccount().address;
    } catch {
      return null;
    }
  });

  async function handleSignIn() {
    setBusy(true);
    setError(null);
    try {
      const account = getOrCreateDevAccount();
      const tokens = await signIn(account);
      // Hydrate api singleton so the immediately-following /whoami succeeds
      api.setToken(tokens.access);
      const me = await api.get<User>("/auth/whoami/");
      setSession(tokens.access, tokens.refresh, me);
      router.push("/app");
    } catch (e) {
      const message =
        e instanceof ApiError ? detailMessage(e.data) : (e as Error).message;
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function handleRotate() {
    const account = rotateDevAccount();
    setPreviewAddress(account.address);
    clearSession();
  }

  function handleClear() {
    clearDevAccount();
    setPreviewAddress(null);
    clearSession();
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-[10px] font-mono tracking-widest text-[#555]">
          {"// EPHEMERAL DEV WALLET"}
        </p>
        <p className="text-[11px] font-mono text-[#888] leading-relaxed">
          An in-browser keypair acts as your wallet for v0.6.0. It signs the SIWE
          message exactly like a real wallet would. Hardware-wallet and
          MetaMask support lands in a later patch.
        </p>
        <div className="border border-[#2a2a2a] bg-[#1a1a1a] p-3 font-mono text-[10px] text-[#888] break-all">
          {previewAddress ? (
            <>
              <span className="text-[#555]">address:</span>{" "}
              <span className="text-[#ccff00]">{previewAddress}</span>
            </>
          ) : (
            <span className="text-[#555]">no keypair yet — sign in to mint one</span>
          )}
        </div>
      </div>

      {sessionUser ? (
        <div className="border border-[#ccff0033] bg-[#1a1a1a] p-3 font-mono text-[10px] text-[#888]">
          <span className="text-[#555]">signed in as:</span>{" "}
          <span className="text-[#ccff00]">{sessionUser.wallet_address}</span>
        </div>
      ) : null}

      {error ? (
        <div
          className="border p-3 font-mono text-[10px] leading-relaxed"
          style={{ borderColor: "#ff3131", color: "#ff3131" }}
        >
          <span className="text-[#888]">[error]</span> {error}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button onClick={handleSignIn} disabled={busy}>
          {busy ? "signing..." : sessionUser ? "Re-authenticate" : "Sign in with wallet"}
        </Button>
        <Button variant="ghost" onClick={handleRotate} disabled={busy}>
          Rotate keypair
        </Button>
        {previewAddress ? (
          <Button variant="destructive" onClick={handleClear} disabled={busy}>
            Clear wallet
          </Button>
        ) : null}
      </div>
    </div>
  );
}
