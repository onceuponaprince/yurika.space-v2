"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Nav } from "@/components/Nav";
import { useAuthStore } from "@/lib/auth-store";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);

  // Soft gate — hydration timing means we can't render this server-side
  // (the store isn't populated on the server). We render the nav + a
  // brief placeholder; if no token after rehydration, kick to /login.
  useEffect(() => {
    // Wait one tick for the store to rehydrate from localStorage.
    const t = setTimeout(() => {
      if (!useAuthStore.getState().accessToken) {
        router.replace("/login");
      }
    }, 100);
    return () => clearTimeout(t);
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-6 py-12">
        {accessToken ? (
          children
        ) : (
          <p className="mx-auto max-w-7xl text-center text-[11px] font-mono text-[#555]">
            <span className="cursor">checking session</span>
          </p>
        )}
      </main>
    </div>
  );
}
