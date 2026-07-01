// App root: wires the QueryClient provider and client-side routes. The Layout
// renders the persistent sidebar; each route fills the content area.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ErrorFeed } from "@/pages/ErrorFeed";
import { RunsList } from "@/pages/RunsList";
import { RunDetail } from "@/pages/RunDetail";
import { StatsOverview } from "@/pages/StatsOverview";
import { AlertRules } from "@/pages/AlertRules";

// One QueryClient for the app. Sensible defaults: don't hammer the API on every
// window focus, keep data fresh for a few seconds.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, staleTime: 5_000, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<ErrorFeed />} />
            <Route path="/runs" element={<RunsList />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/stats" element={<StatsOverview />} />
            <Route path="/alerts" element={<AlertRules />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
