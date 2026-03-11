import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { DealRegistryPage } from "./pages/DealRegistryPage";
import { HealthCheckPage } from "./pages/HealthCheckPage";
import { PortfolioScoringPage } from "./pages/PortfolioScoringPage";
import { ScenarioRunnerPage } from "./pages/ScenarioRunnerPage";
import { WatchlistPage } from "./pages/WatchlistPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/deals" replace />} />
            <Route path="/deals" element={<DealRegistryPage />} />
            <Route path="/health" element={<HealthCheckPage />} />
            <Route path="/portfolio" element={<PortfolioScoringPage />} />
            <Route path="/scenarios" element={<ScenarioRunnerPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
