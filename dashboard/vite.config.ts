/**
 * Vite config for the Canary dashboard.
 *
 * Builds to ../backend/src/canary_server/static so the FastAPI app can serve
 * the SPA directly. During `npm run dev`, /v1 and /health are proxied to the
 * local Canary server on :8732 so the dev UI hits real data.
 */
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://localhost:8732",
      "/health": "http://localhost:8732",
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../backend/src/canary_server/static"),
    emptyOutDir: true,
  },
});
