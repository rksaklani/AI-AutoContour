import { create } from "zustand";

import { tokenStore } from "@/lib/apiClient";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  login: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: Boolean(tokenStore.getAccess()),
  setUser: (user) => set({ user, isAuthenticated: Boolean(tokenStore.getAccess()) }),
  login: (access, refresh) => {
    tokenStore.set(access, refresh);
    set({ isAuthenticated: true });
  },
  logout: () => {
    tokenStore.clear();
    set({ user: null, isAuthenticated: false });
  },
}));
