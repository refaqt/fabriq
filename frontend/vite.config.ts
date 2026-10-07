import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The built bundle lands in the Python package, so `fabriq` serves it with no Node.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "../fabriq/static", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: true } },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
