"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { TerminalWindow } from "@/components/TerminalWindow";
import { api, ApiError, detailMessage } from "@/lib/api";
import type {
  Domain,
  PaginatedResponse,
  ShardCampaign,
  ShardHolding,
} from "@/lib/types";

interface CreateForm {
  domain: string;
  title: string;
  thesis: string;
  total_shards: string;
  price_per_shard_usd: string;
  funding_target_usd: string;
}

const EMPTY_FORM: CreateForm = {
  domain: "",
  title: "",
  thesis: "",
  total_shards: "1000",
  price_per_shard_usd: "5",
  funding_target_usd: "5000",
};

export default function MarketplacePage() {
  const [campaigns, setCampaigns] = useState<ShardCampaign[]>([]);
  const [vaultedDomains, setVaultedDomains] = useState<Domain[]>([]);
  const [holdings, setHoldings] = useState<ShardHolding[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);

  const refresh = useCallback(async () => {
    try {
      const [campaignsResp, domainsResp, holdingsResp] = await Promise.all([
        api.get<PaginatedResponse<ShardCampaign>>("/campaigns/"),
        api.get<PaginatedResponse<Domain>>("/domains/"),
        api.get<PaginatedResponse<ShardHolding>>("/holdings/"),
      ]);
      setCampaigns(campaignsResp.results);
      setVaultedDomains(
        domainsResp.results.filter((d) => d.status === "vaulted"),
      );
      setHoldings(holdingsResp.results);
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
      await api.post<ShardCampaign>("/campaigns/", {
        ...form,
        total_shards: Number(form.total_shards),
        price_per_shard_usd: form.price_per_shard_usd,
        funding_target_usd: form.funding_target_usd,
      });
      setForm({ ...EMPTY_FORM, domain: "" });
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? detailMessage(err.data) : (err as Error).message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function activate(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/campaigns/${id}/activate/`);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function buy(id: string) {
    const raw = window.prompt("How many shards to buy?", "10");
    if (!raw) return;
    const n = Number(raw);
    if (!Number.isFinite(n) || n <= 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/campaigns/${id}/buy/`, { shards: n });
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <TerminalWindow
        label="// FOUNDER · CREATE CAMPAIGN"
        heading={<>SHARD CAMPAIGNS<span className="cursor" /></>}
      >
        {vaultedDomains.length === 0 ? (
          <p className="font-mono text-[11px] text-[#555]">
            You need a domain in <span className="text-[#9d00ff]">VAULTED</span>{" "}
            status to create a campaign. Visit{" "}
            <a className="text-[#ccff00] hover:underline" href="/app/domains">
              /app/domains
            </a>
            .
          </p>
        ) : (
          <form
            onSubmit={handleCreate}
            className="grid grid-cols-1 gap-3 md:grid-cols-2"
          >
            <label className="block">
              <span className="block text-[9px] font-mono tracking-widest text-[#555]">
                VAULTED DOMAIN
              </span>
              <select
                className="terminal-input mt-1"
                value={form.domain}
                onChange={(e) => setForm({ ...form, domain: e.target.value })}
                required
              >
                <option value="">— pick one —</option>
                {vaultedDomains.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.fqdn}
                  </option>
                ))}
              </select>
            </label>
            <FormField
              label="TITLE"
              value={form.title}
              onChange={(v) => setForm({ ...form, title: v })}
              required
            />
            <label className="block md:col-span-2">
              <span className="block text-[9px] font-mono tracking-widest text-[#555]">
                THESIS
              </span>
              <textarea
                className="terminal-input mt-1 min-h-[80px]"
                value={form.thesis}
                onChange={(e) => setForm({ ...form, thesis: e.target.value })}
                required
              />
            </label>
            <FormField
              label="TOTAL SHARDS"
              value={form.total_shards}
              onChange={(v) => setForm({ ...form, total_shards: v })}
            />
            <FormField
              label="PRICE PER SHARD (USD)"
              value={form.price_per_shard_usd}
              onChange={(v) => setForm({ ...form, price_per_shard_usd: v })}
            />
            <FormField
              label="FUNDING TARGET (USD)"
              value={form.funding_target_usd}
              onChange={(v) => setForm({ ...form, funding_target_usd: v })}
            />
            <div className="flex items-end">
              <Button type="submit" disabled={busy}>
                {busy ? "..." : "Create campaign"}
              </Button>
            </div>
          </form>
        )}
        {error ? (
          <p className="mt-3 font-mono text-[10px]" style={{ color: "#ff3131" }}>
            [error] {error}
          </p>
        ) : null}
      </TerminalWindow>

      <TerminalWindow
        label="// CURATOR · MARKETPLACE"
        heading={<>OPEN CAMPAIGNS<span className="cursor" /></>}
      >
        {campaigns.length === 0 ? (
          <p className="font-mono text-[11px] text-[#555]">
            No campaigns yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {campaigns.map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-start justify-between gap-3 border border-[#2a2a2a] bg-[#1a1a1a] p-4"
              >
                <div className="min-w-0 grow">
                  <p className="font-display text-[12px] text-[#ccff00] glow-lime">
                    {c.title}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[#888]">
                    {c.thesis}
                  </p>
                  <p className="mt-2 font-mono text-[10px] text-[#555]">
                    <span className="text-[#9d00ff]">
                      ${Number(c.funding_raised_usd).toLocaleString()} /
                      ${Number(c.funding_target_usd).toLocaleString()}
                    </span>{" "}
                    raised ·{" "}
                    <span className="text-[#ccff00]">
                      {c.shards_available}
                    </span>{" "}
                    shards left @{" "}
                    <span className="text-[#ccff00]">
                      ${c.price_per_shard_usd}
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" onClick={() => activate(c.id)} disabled={busy}>
                    Activate
                  </Button>
                  <Button onClick={() => buy(c.id)} disabled={busy}>
                    Buy shards
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </TerminalWindow>

      <TerminalWindow
        label="// CURATOR · YOUR HOLDINGS"
        heading="HOLDINGS LEDGER"
      >
        {holdings.length === 0 ? (
          <p className="font-mono text-[11px] text-[#555]">
            No holdings yet. Buy from a campaign above.
          </p>
        ) : (
          <ul className="space-y-2 font-mono text-[11px]">
            {holdings.map((h) => (
              <li
                key={h.id}
                className="flex items-center justify-between border border-[#2a2a2a] bg-[#1a1a1a] px-3 py-2 text-[#888]"
              >
                <span>
                  <span className="text-[#ccff00]">{h.shards_held}</span> shards
                  in <span className="text-[#9d00ff]">{h.campaign.slice(0, 8)}…</span>
                </span>
                <span className="text-[#555]">${h.purchase_price_usd}/shard</span>
              </li>
            ))}
          </ul>
        )}
      </TerminalWindow>
    </div>
  );
}

function FormField({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
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
        required={required}
      />
    </label>
  );
}
