"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useAuthStore } from "@/lib/auth-store";

export function Providers({ children }: { children: React.ReactNode }) {
  // One QueryClient per component-tree mount (stable across re-renders)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  // Re-hydrate the API client with the persisted JWT after the
  // Zustand store rehydrates on the client. Without this the access
  // token sits in localStorage but the api singleton is unaware.
  const hydrateApi = useAuthStore((s) => s.hydrateApi);
  useEffect(() => {
    hydrateApi();
  }, [hydrateApi]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
