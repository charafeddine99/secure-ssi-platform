import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Development: the browser talks only to the Vite origin and /api is proxied
  // to the gateway. Same origin means the HttpOnly session cookie works under
  // both localhost and 127.0.0.1 and no CORS preflight is needed.
  // Default: the gateway port from docker-compose.yml and the README (8000).
  const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": { target: apiTarget, changeOrigin: false, secure: false },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ["react", "react-dom", "react-router-dom"],
          },
        },
      },
    },
  };
});
