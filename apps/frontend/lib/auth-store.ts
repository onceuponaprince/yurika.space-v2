"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  setSession: (access: string, refresh: string, user: User) => void;
  clearSession: () => void;
  hydrateApi: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (access, refresh, user) => {
        api.setToken(access);
        set({ accessToken: access, refreshToken: refresh, user });
      },
      clearSession: () => {
        api.setToken(null);
        set({ accessToken: null, refreshToken: null, user: null });
      },
      hydrateApi: () => {
        const token = get().accessToken;
        api.setToken(token);
      },
    }),
    { name: "yurika-auth" },
  ),
);
