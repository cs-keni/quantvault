import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { RegisterPage } from "./pages/RegisterPage";
import { useAuthStore } from "./store/authStore";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const location = useLocation();

  if (accessToken === null) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}

function AuthBootstrap({ children }: { children: ReactNode }) {
  const authReady = useAuthStore((state) => state.authReady);
  const initializeAuth = useAuthStore((state) => state.initializeAuth);

  useEffect(() => {
    void initializeAuth();
  }, [initializeAuth]);

  if (!authReady) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg px-6">
        <div className="rounded-md bg-surface px-4 py-3 text-sm font-medium text-ink/70 ring-1 ring-ink/5">
          Loading QuantVault
        </div>
      </main>
    );
  }

  return children;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthBootstrap>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/new"
              element={
                <ProtectedRoute>
                  <PlaceholderPage title="New Portfolio" />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/:id/analysis"
              element={
                <ProtectedRoute>
                  <PlaceholderPage title="Analysis" />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/:id/simulate"
              element={
                <ProtectedRoute>
                  <PlaceholderPage title="Monte Carlo" />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolios/:id/backtest"
              element={
                <ProtectedRoute>
                  <PlaceholderPage title="Backtest" />
                </ProtectedRoute>
              }
            />
            <Route
              path="/compare"
              element={
                <ProtectedRoute>
                  <PlaceholderPage title="Compare" />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthBootstrap>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
