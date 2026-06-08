import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "../store/authStore";

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

export const apiClient = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1`,
});

let refreshPromise: Promise<string> | null = null;

function ensureHeaders(config: InternalAxiosRequestConfig): AxiosHeaders {
  if (config.headers instanceof AxiosHeaders) {
    return config.headers;
  }
  config.headers = new AxiosHeaders(config.headers);
  return config.headers;
}

function isAuthRefreshCandidate(config: RetryConfig): boolean {
  const url = config.url ?? "";
  return !url.endsWith("/auth/login") && !url.endsWith("/auth/refresh");
}

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token !== null) {
    ensureHeaders(config).set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    if (
      error.response?.status !== 401 ||
      config === undefined ||
      config._retry === true ||
      !isAuthRefreshCandidate(config)
    ) {
      return Promise.reject(error);
    }

    config._retry = true;
    refreshPromise ??= useAuthStore
      .getState()
      .silentRefresh()
      .finally(() => {
        refreshPromise = null;
      });

    try {
      const token = await refreshPromise;
      ensureHeaders(config).set("Authorization", `Bearer ${token}`);
      return apiClient(config);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  },
);
