import axios from "axios";
import { create } from "zustand";

import type { TokenResponse, UserRead } from "../types/api";

const refreshTokenKey = "refresh_token";
const authClient = axios.create({ baseURL: "/api/v1" });
let silentRefreshPromise: Promise<string> | null = null;

function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(refreshTokenKey);
}

function writeStoredRefreshToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(refreshTokenKey, token);
  }
}

function clearStoredRefreshToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(refreshTokenKey);
  }
}

export interface AuthState {
  user: UserRead | null;
  accessToken: string | null;
  authReady: boolean;
  setTokens(access: string, refresh: string): void;
  setUser(user: UserRead | null): void;
  logout(): void;
  silentRefresh(): Promise<string>;
  initializeAuth(): Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  authReady: false,

  setTokens(access, refresh) {
    writeStoredRefreshToken(refresh);
    set({ accessToken: access });
  },

  setUser(user) {
    set({ user });
  },

  logout() {
    clearStoredRefreshToken();
    set({ accessToken: null, user: null, authReady: true });
  },

  silentRefresh() {
    silentRefreshPromise ??= (async () => {
      const refreshToken = getStoredRefreshToken();
      if (refreshToken === null) {
        set({ accessToken: null, user: null });
        throw new Error("No refresh token available");
      }

      try {
        const response = await authClient.post<TokenResponse>("/auth/refresh", {
          refresh_token: refreshToken,
        });
        get().setTokens(response.data.access_token, response.data.refresh_token);
        return response.data.access_token;
      } catch (error) {
        get().logout();
        throw error;
      }
    })().finally(() => {
      silentRefreshPromise = null;
    });

    return silentRefreshPromise;
  },

  async initializeAuth() {
    const refreshToken = getStoredRefreshToken();
    if (refreshToken === null) {
      set({ authReady: true });
      return;
    }

    try {
      const accessToken = await get().silentRefresh();
      const response = await authClient.get<UserRead>("/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      set({ user: response.data });
    } catch {
      set({ accessToken: null, user: null });
    } finally {
      set({ authReady: true });
    }
  },
}));
