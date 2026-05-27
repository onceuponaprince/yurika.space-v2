"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { TerminalWindow } from "@/components/TerminalWindow";
import { api, ApiError, detailMessage } from "@/lib/api";
import type {
  Domain,
  PaginatedResponse,
  VerifyInstructions,
} from "@/lib/types";

export default function DomainsPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newTld, setNewTld] = useState("space");
  const [newDescription, setNewDescription] = useState("");

  const refresh = useCallback(async () => {
    try {
      const resp = await api.get<PaginatedResponse<Domain>>("/domains/");
      setDomains(resp.results);
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post<Domain>("/domains/", {
        name: newName,
        tld: newTld,
        description: newDescription,
      });
      setNewName("");
      setNewDescription("");
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? detailMessage(err.data) : (err as Error).message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <TerminalWindow
        label="// FOUNDER · DOMAIN LEDGER"
        heading={<>YOUR DOMAINS<span className="cursor" /></>}
      >
        <form
          onSubmit={handleCreate}
          className="grid grid-cols-1 gap-3 md:grid-cols-[2fr_1fr_3fr_auto] md:items-end"
        >
          <Field
            label="NAME"
            value={newName}
            onChange={setNewName}
            placeholder="yurika"
            required
          />
          <Field
            label="TLD"
            value={newTld}
            onChange={setNewTld}
            placeholder="space"
            required
          />
          <Field
            label="DESCRIPTION"
            value={newDescription}
            onChange={setNewDescription}
            placeholder="what this domain is about"
          />
          <Button type="submit" disabled={busy}>
            {busy ? "..." : "Submit"}
          </Button>
        </form>
        {error ? (
          <p className="mt-3 font-mono text-[10px]" style={{ color: "#ff3131" }}>
            [error] {error}
          </p>
        ) : null}
      </TerminalWindow>

      {domains.length === 0 ? (
        <TerminalWindow label="// EMPTY">
          <p className="font-mono text-[11px] text-[#555]">
            No domains yet. Submit one above to start the lifecycle.
          </p>
        </TerminalWindow>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {domains.map((d) => (
            <DomainCard key={d.id} domain={d} onChanged={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="block text-[9px] font-mono tracking-widest text-[#555]">
        {label}
      </span>
      <input
        className="terminal-input mt-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
      />
    </label>
  );
}

function DomainCard({
  domain,
  onChanged,
}: {
  domain: Domain;
  onChanged: () => Promise<void>;
}) {
  const [instructions, setInstructions] = useState<VerifyInstructions | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadInstructions() {
    setBusy(true);
    setError(null);
    try {
      const i = await api.get<VerifyInstructions>(
        `/domains/${domain.id}/verify-instructions/`,
      );
      setInstructions(i);
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doAction(action: "verify" | "vault" | "dev-force-vault") {
    setBusy(true);
    setError(null);
    try {
      await api.post<Domain>(`/domains/${domain.id}/${action}/`);
      await onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border border-[#2a2a2a] bg-[#141414] p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-[14px] text-[#ccff00] glow-lime">
            {domain.fqdn}
          </p>
          <p className="mt-1 break-all font-mono text-[10px] text-[#555]">
            id {domain.id.slice(0, 8)}…
          </p>
        </div>
        <span className="status-pill" data-status={domain.status}>
          {domain.status}
        </span>
      </header>

      {domain.description ? (
        <p className="mt-3 font-mono text-[11px] text-[#888]">
          {domain.description}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {domain.status === "pending" ? (
          <>
            <Button variant="ghost" onClick={loadInstructions} disabled={busy}>
              Show TXT record
            </Button>
            <Button onClick={() => doAction("verify")} disabled={busy}>
              Verify DNS
            </Button>
            <Button
              variant="ghost"
              onClick={() => doAction("dev-force-vault")}
              disabled={busy}
              title="DEBUG-only shortcut; skips DNS + vault transition"
            >
              Force-vault (dev)
            </Button>
          </>
        ) : null}
        {domain.status === "verified" ? (
          <Button onClick={() => doAction("vault")} disabled={busy}>
            Vault
          </Button>
        ) : null}
        {domain.status === "vaulted" ? (
          <p className="font-mono text-[10px] text-[#888]">
            → next: create a campaign in <span className="text-[#ccff00]">/app/marketplace</span>
          </p>
        ) : null}
      </div>

      {instructions ? (
        <div className="mt-4 border border-[#2a2a2a] bg-[#1a1a1a] p-3 font-mono text-[10px] leading-relaxed">
          <p className="text-[#555]">
            Publish this DNS TXT record, then click{" "}
            <span className="text-[#ccff00]">Verify DNS</span>:
          </p>
          <div className="mt-2 space-y-1">
            <p>
              <span className="text-[#555]">name:</span>{" "}
              <span className="text-[#ccff00]">{instructions.record_name}</span>
            </p>
            <p>
              <span className="text-[#555]">value:</span>{" "}
              <span className="text-[#9d00ff]">{instructions.record_value}</span>
            </p>
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="mt-3 font-mono text-[10px]" style={{ color: "#ff3131" }}>
          [error] {error}
        </p>
      ) : null}
    </div>
  );
}
