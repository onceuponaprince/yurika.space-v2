"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { TerminalWindow } from "@/components/TerminalWindow";
import { api, ApiError, detailMessage } from "@/lib/api";
import type { DiscoveryResponse, DiscoveryResult } from "@/lib/types";

type Mode = "personalized" | "trending";

export default function DiscoverPage() {
  const [mode, setMode] = useState<Mode>("personalized");
  const [results, setResults] = useState<DiscoveryResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (m: Mode) => {
    setBusy(true);
    setError(null);
    try {
      const resp = await api.get<DiscoveryResponse>(`/graph/discover/?mode=${m}`);
      setResults(resp.results ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? detailMessage(e.data) : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(mode);
  }, [mode, load]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <TerminalWindow
        label="// KNOWLEDGE GRAPH · DISCOVERY"
        heading={
          <>
            DISCOVER{" "}
            <span className="text-[#9d00ff] glow-purple">DOMAINS</span>
            <span className="cursor" />
          </>
        }
      >
        <p className="font-mono text-[11px] text-[#888] leading-relaxed">
          Personalized = 1-hop peer-curator traversal (Jaccard-weighted,
          excluding what you already hold/own). Trending = ranked by distinct
          holder count across the network.
        </p>
        <div className="mt-4 flex gap-3">
          <Button
            variant={mode === "personalized" ? "primary" : "ghost"}
            onClick={() => setMode("personalized")}
            disabled={busy}
          >
            Personalized
          </Button>
          <Button
            variant={mode === "trending" ? "primary" : "ghost"}
            onClick={() => setMode("trending")}
            disabled={busy}
          >
            Trending
          </Button>
        </div>
        {error ? (
          <p className="mt-4 font-mono text-[10px]" style={{ color: "#ff3131" }}>
            [error] {error}
          </p>
        ) : null}
      </TerminalWindow>

      <TerminalWindow
        label={`// RESULTS · ${mode.toUpperCase()}`}
      >
        {results.length === 0 ? (
          <p className="font-mono text-[11px] text-[#555]">
            {busy ? (
              <span className="cursor">querying</span>
            ) : (
              <>No results yet. Buy shards in a campaign to populate the graph.</>
            )}
          </p>
        ) : (
          <ul className="space-y-2">
            {results.map((r) => (
              <li
                key={r.uid}
                className="flex flex-wrap items-center justify-between gap-3 border border-[#2a2a2a] bg-[#1a1a1a] px-4 py-3"
              >
                <div>
                  <p className="font-display text-[13px] text-[#ccff00] glow-lime">
                    {r.fqdn}
                  </p>
                  <p className="mt-1 font-mono text-[9px] text-[#555] break-all">
                    {r.uid}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="status-pill" data-status={r.status}>
                    {r.status}
                  </span>
                  <div className="text-right">
                    <p className="text-[9px] font-mono tracking-widest text-[#555]">
                      SCORE
                    </p>
                    <p className="font-display text-[18px] text-[#9d00ff] glow-purple">
                      {r.score}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </TerminalWindow>
    </div>
  );
}
