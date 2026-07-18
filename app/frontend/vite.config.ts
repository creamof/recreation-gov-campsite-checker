import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the PWA is served by Vite on :5173 and proxies /api to the
// FastAPI backend on :8000. In production the frontend is built to static files
// and served from the same origin as the API, so calls to /api "just work".
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
