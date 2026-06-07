import axios, { AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function axiosResponse(config: InternalAxiosRequestConfig, data: unknown, status = 200) {
  return {
    data,
    status,
    statusText: status === 200 ? "OK" : "Error",
    headers: new AxiosHeaders(),
    config,
  };
}

function unauthorized(config: InternalAxiosRequestConfig) {
  return new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, undefined, {
    ...axiosResponse(config, { detail: "Unauthorized" }, 401),
    statusText: "Unauthorized",
  });
}

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  axios.defaults.adapter = undefined;
});

describe("authStore", () => {
  it("deduplicates concurrent silentRefresh calls", async () => {
    let refreshCalls = 0;
    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        return axiosResponse(config, {
          access_token: "access-1",
          refresh_token: "refresh-1",
          token_type: "bearer",
        });
      }
      throw new Error(`Unexpected request: ${config.url}`);
    };
    axios.defaults.adapter = adapter;
    localStorage.setItem("refresh_token", "refresh-0");

    const { useAuthStore } = await import("../authStore");
    const tokens = await Promise.all(
      Array.from({ length: 5 }, () => useAuthStore.getState().silentRefresh()),
    );

    expect(refreshCalls).toBe(1);
    expect(tokens).toEqual(["access-1", "access-1", "access-1", "access-1", "access-1"]);
    expect(useAuthStore.getState().accessToken).toBe("access-1");
    expect(localStorage.getItem("refresh_token")).toBe("refresh-1");
  });

  it("logout clears accessToken and localStorage", async () => {
    const { useAuthStore } = await import("../authStore");

    useAuthStore.getState().setTokens("access-token", "refresh-token");
    useAuthStore.getState().logout();

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("does not refresh again when /auth/refresh returns 401", async () => {
    let refreshRequests = 0;
    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/auth/refresh") {
        refreshRequests += 1;
        throw unauthorized(config);
      }
      throw new Error(`Unexpected request: ${config.url}`);
    };
    axios.defaults.adapter = adapter;
    localStorage.setItem("refresh_token", "refresh-token");

    const { useAuthStore } = await import("../authStore");
    const { apiClient } = await import("../../services/apiClient");
    useAuthStore.getState().setTokens("expired-access", "refresh-token");

    await expect(apiClient.post("/auth/refresh", { refresh_token: "refresh-token" })).rejects.toBeInstanceOf(
      AxiosError,
    );
    expect(refreshRequests).toBe(1);
  });

  it("rejects silentRefresh without hitting backend when no refresh token exists", async () => {
    let requests = 0;
    const adapter: AxiosAdapter = async (config) => {
      requests += 1;
      return axiosResponse(config, {});
    };
    axios.defaults.adapter = adapter;

    const { useAuthStore } = await import("../authStore");

    await expect(useAuthStore.getState().silentRefresh()).rejects.toThrow("No refresh token");
    expect(requests).toBe(0);
  });
});
