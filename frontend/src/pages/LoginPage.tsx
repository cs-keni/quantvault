import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";

import { apiClient } from "../services/apiClient";
import { useAuthStore } from "../store/authStore";
import type { TokenResponse, UserRead } from "../types/api";

interface LoginForm {
  email: string;
  password: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);
  const setUser = useAuthStore((state) => state.setUser);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>();

  async function onSubmit(values: LoginForm) {
    try {
      const tokenResponse = await apiClient.post<TokenResponse>("/auth/login", values);
      setTokens(tokenResponse.data.access_token, tokenResponse.data.refresh_token);
      const userResponse = await apiClient.get<UserRead>("/auth/me");
      setUser(userResponse.data);
      navigate("/dashboard");
    } catch (error) {
      const message =
        axios.isAxiosError(error) && error.response?.status === 401
          ? "Invalid email or password"
          : "Unable to sign in. Try again.";
      setError("root", { message });
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6">
      <section className="w-full max-w-sm rounded-lg border border-border bg-surface p-6">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">Sign in</h1>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <label className="block text-sm font-medium text-ink">
            Email
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
              type="email"
              autoComplete="email"
              {...register("email", {
                required: "Email is required",
                pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email" },
              })}
            />
          </label>
          {errors.email ? <p className="text-sm text-negative">{errors.email.message}</p> : null}

          <label className="block text-sm font-medium text-ink">
            Password
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
              type="password"
              autoComplete="current-password"
              {...register("password", { required: "Password is required" })}
            />
          </label>
          {errors.password ? <p className="text-sm text-negative">{errors.password.message}</p> : null}
          {errors.root ? <p className="text-sm text-negative">{errors.root.message}</p> : null}

          <button
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in" : "Sign in"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm text-muted">
          New to QuantVault?{" "}
          <Link className="font-medium text-accent hover:text-accent/80" to="/register">
            Create an account
          </Link>
        </p>
      </section>
    </main>
  );
}
