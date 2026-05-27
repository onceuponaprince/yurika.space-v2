import Link from "next/link";

import { Nav } from "@/components/Nav";
import { TerminalWindow } from "@/components/TerminalWindow";

const FEATURES = [
  {
    label: "// 01",
    title: "VAULT",
    body: "Prove DNS control, lock your domain into a YurikaVault contract. The domain becomes a digital asset with a verifiable on-chain identity.",
  },
  {
    label: "// 02",
    title: "SHARD",
    body: "Fractionalize ownership. Set total supply, price per shard, funding target. Curators buy in; you raise instant capital.",
  },
  {
    label: "// 03",
    title: "DISCOVER",
    body: "Curators find adjacent projects through a Neo4j-powered peer-curator graph. Holdings overlap = signal.",
  },
];

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 px-6 py-12">
        <div className="mx-auto max-w-5xl space-y-8">
          <header className="space-y-4">
            <p className="text-[10px] font-mono tracking-widest text-[#555]">
              {"// YURIKA.SPACE — DOMAIN-NATIVE LAUNCHPAD"}
            </p>
            <h1 className="text-[clamp(20px,4vw,36px)] font-display leading-relaxed">
              LIQUID DOMAINS.{" "}
              <span className="text-[#ccff00] glow-lime">ACCELERATED</span>{" "}
              FOUNDERS.<span className="cursor" />
            </h1>
            <p className="max-w-2xl text-sm font-mono leading-relaxed text-[#888]">
              Turn your domain into a vault-backed, shardable asset. Raise
              capital instantly. Curators discover what to fund through a
              peer-curator graph, not an algorithm.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link href="/login" className="btn-primary">
                Enter command center
              </Link>
              <Link href="/app/marketplace" className="btn-ghost">
                Browse marketplace
              </Link>
            </div>
          </header>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {FEATURES.map((f) => (
              <TerminalWindow key={f.title} label={f.label}>
                <h2 className="mb-3 font-display text-[16px] tracking-widest text-[#ccff00]">
                  {f.title}
                </h2>
                <p className="text-[11px] font-mono leading-relaxed text-[#888]">
                  {f.body}
                </p>
              </TerminalWindow>
            ))}
          </div>

          <TerminalWindow label="// STACK">
            <ul className="space-y-2 text-[11px] font-mono text-[#888]">
              <li>
                <span className="text-[#555]">→</span> Django 5 + DRF + SimpleJWT (SIWE wallet auth)
              </li>
              <li>
                <span className="text-[#555]">→</span> PostgreSQL (source of truth) + Neo4j (knowledge graph)
              </li>
              <li>
                <span className="text-[#555]">→</span> Next.js 16 + React 19 + Turbopack
              </li>
              <li>
                <span className="text-[#555]">→</span>{" "}
                <span className="text-[#9d00ff] glow-purple">
                  Foundry smart contracts (vault + ERC-20 shard token) — subsystem 7
                </span>
              </li>
            </ul>
          </TerminalWindow>
        </div>
      </main>

      <footer className="border-t border-[#2a2a2a] px-6 py-4 text-center text-[10px] font-mono text-[#555]">
        <span>v0.6.0 — yurika.space-v2</span> ·{" "}
        <Link
          href="https://github.com/onceuponaprince/yurika.space-v2"
          className="hover:text-[#ccff00]"
        >
          source
        </Link>
      </footer>
    </div>
  );
}
