import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "./components/ui/Toast";
import { Layout } from "./components/Layout";
import { DealRegistryPage } from "./pages/DealRegistryPage";
import { HealthCheckPage } from "./pages/HealthCheckPage";
import { PortfolioScoringPage } from "./pages/PortfolioScoringPage";
import { ScenarioRunnerPage } from "./pages/ScenarioRunnerPage";
import { WatchlistPage } from "./pages/WatchlistPage";
import { DraftsPage } from "./pages/DraftsPage";
import { ComparisonPage } from "./pages/ComparisonPage";
import { SensitivityPage } from "./pages/SensitivityPage";
import { StressMatrixPage } from "./pages/StressMatrixPage";
import { OptimizerPage } from "./pages/OptimizerPage";
import { DealMonitorPage } from "./pages/DealMonitorPage";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { BulkHealthPage } from "./pages/BulkHealthPage";
import { PipelinePage } from "./pages/PipelinePage";
import { DealProfilePage } from "./pages/DealProfilePage";
import { PortfolioTrendPage } from "./pages/PortfolioTrendPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { PortfolioAnalysisPage } from "./pages/PortfolioAnalysisPage";
import { PublishGatePage } from "./pages/PublishGatePage";
import { SettingsPage } from "./pages/SettingsPage";
import { TemplateSuitePage } from "./pages/TemplateSuitePage";
import { KRIComparisonPage } from "./pages/KRIComparisonPage";
import { ScenarioBuilderPage } from "./pages/ScenarioBuilderPage";
import { PortfolioStressPage } from "./pages/PortfolioStressPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/deals" replace />} />
              <Route path="/deals" element={<DealRegistryPage />} />
              <Route path="/health" element={<HealthCheckPage />} />
              <Route path="/portfolio" element={<PortfolioScoringPage />} />
              <Route path="/scenarios" element={<ScenarioRunnerPage />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/drafts" element={<DraftsPage />} />
              <Route path="/compare" element={<ComparisonPage />} />
              <Route path="/sensitivity" element={<SensitivityPage />} />
              <Route path="/stress-matrix" element={<StressMatrixPage />} />
              <Route path="/optimize" element={<OptimizerPage />} />
              <Route path="/monitor" element={<DealMonitorPage />} />
              <Route path="/benchmark" element={<BenchmarkPage />} />
              <Route path="/audit" element={<AuditLogPage />} />
              <Route path="/bulk-health" element={<BulkHealthPage />} />
              <Route path="/pipeline" element={<PipelinePage />} />
              <Route path="/deals/:dealId" element={<DealProfilePage />} />
              <Route path="/trend" element={<PortfolioTrendPage />} />
              <Route path="/approvals" element={<ApprovalsPage />} />
              <Route path="/portfolio-analyze" element={<PortfolioAnalysisPage />} />
              <Route path="/publish-gate" element={<PublishGatePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/template-suite" element={<TemplateSuitePage />} />
              <Route path="/kri-compare" element={<KRIComparisonPage />} />
              <Route path="/scenario-builder" element={<ScenarioBuilderPage />} />
              <Route path="/portfolio-stress" element={<PortfolioStressPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
