import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";

import { apiClient } from "../services/apiClient";
import { useAuthStore } from "../store/authStore";
import type { TokenResponse, UserRead } from "../types/api";

interface RegisterForm {
  full_name: string;
  email: string;
  password: string;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);
  const setUser = useAuthStore((state) => state.setUser);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>();

  async function onSubmit(values: RegisterForm) {
    try {
      const registerResponse = await apiClient.post<UserRead>("/auth/register", values);
      const loginResponse = await apiClient.post<TokenResponse>("/auth/login", {
        email: values.email,
        password: values.password,
      });
      setTokens(loginResponse.data.access_token, loginResponse.data.refresh_token);
      setUser(registerResponse.data);
      navigate("/dashboard");
    } catch (error) {
      const message =
        axios.isAxiosError(error) && error.response?.status === 409
          ? "Email already registered"
          : "Unable to create account. Try again.";
      setError("root", { message });
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6">
      <section className="w-full max-w-sm rounded-lg border border-ink/10 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">Create account</h1>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <label className="block text-sm font-medium text-ink">
            Full name
            <input
              className="mt-1 w-full rounded-md border border-ink/10 bg-white px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
              type="text"
              autoComplete="name"
              {...register("full_name", { required: "Full name is required" })}
            />
          </label>
          {errors.full_name ? (
            <p className="text-sm text-negative">{errors.full_name.message}</p>
          ) : null}

          <label className="block text-sm font-medium text-ink">
            Email
            <input
              className="mt-1 w-full rounded-md border border-ink/10 bg-white px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
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
              className="mt-1 w-full rounded-md border border-ink/10 bg-white px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
              type="password"
              autoComplete="new-password"
              {...register("password", {
                required: "Password is required",
                minLength: { value: 8, message: "Use at least 8 characters" },
              })}
            />
          </label>
          {errors.password ? <p className="text-sm text-negative">{errors.password.message}</p> : null}
          {errors.root ? <p className="text-sm text-negative">{errors.root.message}</p> : null}

          <button
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Creating account" : "Create account"}
          </button>
        </form>
        <p className="mt-5 text-center text-sm text-ink/65">
          Already have an account?{" "}
          <Link className="font-medium text-accent hover:text-accent/80" to="/login">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
