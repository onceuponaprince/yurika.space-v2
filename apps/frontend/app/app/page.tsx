"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TerminalWindow } from "@/components/TerminalWindow";
import { api, ApiError, detailMessage } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { DiscoveryResponse } from "@/lib/types";

interface Stats {
  users: number;
  domains: number;
  projects: number;
  holds: number;
  owns: number;
}

const LAUNCH_TASKS = [
  "Submit a domain you control",
  "Publish the verification TXT record",
  "Vault the domain (mock contract for now)",
  "Create + activate a shard campaign",
  "Watch the discovery graph populate",
];

export default function CommandCenterPage() {
  const user = useAuthStore((s) => s.user);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await api.get<DiscoveryResponse>(
          "/graph/discover/?mode=stats",
        );
        if (!cancelled && resp.stats) setStats(resp.stats);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError ? detailMessage(e.data) : (e as Error).message,
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:grid-cols-12">
      <TerminalWindow
        className="lg:col-span-8"
        label="// PHASE 2 // FOUNDER OPERATIONS HUB"
        heading={
          <>
            COMMAND CENTER{" "}
            <span className="text-[#ccff00] glow-lime">INITIALIZED</span>
            <span className="cursor" />
          </>
        }
      >
        <p className="max-w-2xl text-[12px] font-mono leading-loose text-[#888]">
          Founder + curator control surface. Wired to the Django API at{" "}
          <span className="text-[#9d00ff]">
            {process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api"}
          </span>
          . Signed in as{" "}
          <span className="text-[#ccff00]">
            {user?.wallet_address ?? "(none)"}
          </span>
          .
        </p>

        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-5">
          <Stat label="USERS" value={stats?.users} />
          <Stat label="DOMAINS" value={stats?.domains} />
          <Stat label="OWNS" value={stats?.owns} />
          <Stat label="HOLDS" value={stats?.holds} />
          <Stat label="PROJECTS" value={stats?.projects} />
        </div>
        {error ? (
          <p
            className="mt-4 font-mono text-[10px]"
            style={{ color: "#ff3131" }}
          >
            [error] {error}
          </p>
        ) : null}
      </TerminalWindow>

      <TerminalWindow
        className="lg:col-span-4"
        label="// NEXT ACTIONS"
        heading={
          <span className="text-[10px] tracking-widest text-[#ccff00]">
            LAUNCH TASK QUEUE
          </span>
        }
      >
        <ol className="space-y-3">
          {LAUNCH_TASKS.map((task, i) => (
            <li
              key={task}
              className="flex items-start gap-3 text-[11px] font-mono text-[#888]"
            >
              <span className="mt-[1px] text-[#ccff00]">
                [{String(i + 1).padStart(2, "0")}]
              </span>
              <span>{task}</span>
            </li>
          ))}
        </ol>
        <nav className="mt-6 space-y-2 border-t border-[#2a2a2a] pt-4 text-[10px] font-mono">
          <Link
            href="/app/domains"
            className="block text-[#888] hover:text-[#ccff00]"
          >
            → Founder: my domains
          </Link>
          <Link
            href="/app/marketplace"
            className="block text-[#888] hover:text-[#ccff00]"
          >
            → Curator: marketplace
          </Link>
          <Link
            href="/app/discover"
            className="block text-[#888] hover:text-[#ccff00]"
          >
            → Discover graph
          </Link>
        </nav>
      </TerminalWindow>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="border border-[#2a2a2a] bg-[#1a1a1a] p-3">
      <p className="text-[9px] font-mono tracking-widest text-[#555]">{label}</p>
      <p className="mt-1 font-display text-[18px] text-[#ccff00] glow-lime">
        {value ?? "—"}
      </p>
    </div>
  );
}
