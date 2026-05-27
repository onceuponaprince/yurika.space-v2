"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuthStore } from "@/lib/auth-store";

const APP_LINKS = [
  { href: "/app", label: "command center" },
  { href: "/app/domains", label: "domains" },
  { href: "/app/marketplace", label: "marketplace" },
  { href: "/app/discover", label: "discover" },
];

export function Nav() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  return (
    <nav className="border-b border-[#2a2a2a] bg-[#0d0d0d] px-6 py-3">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <Link
          href="/"
          className="font-display text-[12px] tracking-widest text-[#ccff00] glow-lime"
        >
          yurika.space
        </Link>
        <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono uppercase tracking-widest">
          {APP_LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={
                  active
                    ? "text-[#ccff00] glow-lime"
                    : "text-[#888] hover:text-[#ccff00]"
                }
              >
                {l.label}
              </Link>
            );
          })}
          {user ? (
            <button
              type="button"
              onClick={clearSession}
              className="text-[#888] hover:text-[#ff3131] font-mono uppercase tracking-widest"
            >
              sign out
            </button>
          ) : (
            <Link href="/login" className="text-[#888] hover:text-[#ccff00]">
              sign in
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
