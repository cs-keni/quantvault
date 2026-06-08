import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion, type Transition } from "framer-motion";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { PageSkeleton } from "./components/SkeletonCard";
import { useAuthStore } from "./store/authStore";

const AnalysisPage = lazy(() => import("./pages/AnalysisPage").then((module) => ({ default: module.AnalysisPage })));
const BacktestPage = lazy(() => import("./pages/BacktestPage").then((module) => ({ default: module.BacktestPage })));
const ComparePage = lazy(() => import("./pages/ComparePage").then((module) => ({ default: module.ComparePage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const MonteCarloPage = lazy(() =>
  import("./pages/MonteCarloPage").then((module) => ({ default: module.MonteCarloPage })),
);
const PortfolioBuilderPage = lazy(() =>
  import("./pages/PortfolioBuilderPage").then((module) => ({ default: module.PortfolioBuilderPage })),
);
const RegisterPage = lazy(() => import("./pages/RegisterPage").then((module) => ({ default: module.RegisterPage })));

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

  return <AppShell>{children}</AppShell>;
}

function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const prefersReduced = useReducedMotion();
  const transition: Transition = prefersReduced ? { duration: 0 } : { duration: 0.15, ease: "easeOut" };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        initial={{ opacity: 0 }}
        key={location.pathname}
        transition={transition}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
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
        <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm font-medium text-muted">
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
          <Suspense fallback={<PageSkeleton />}>
            <RouteTransition>
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
                  path="/dashboard/portfolios/:portfolioId"
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
                      <PortfolioBuilderPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/portfolios/:id/analysis"
                  element={
                    <ProtectedRoute>
                      <AnalysisPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/portfolios/:id/simulate"
                  element={
                    <ProtectedRoute>
                      <MonteCarloPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/portfolios/:id/backtest"
                  element={
                    <ProtectedRoute>
                      <BacktestPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/compare"
                  element={
                    <ProtectedRoute>
                      <ComparePage />
                    </ProtectedRoute>
                  }
                />
              </Routes>
            </RouteTransition>
          </Suspense>
        </AuthBootstrap>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
