import { loadEnv, type ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const target =
    loadEnv(mode, ".", "DRAMA_").DRAMA_API_URL || "http://127.0.0.1:8765";
  const proxy: ProxyOptions = {
    target,
    changeOrigin: true,
    configure(server) {
      server.on("proxyReq", (req) => {
        // Keep FastAPI's same-origin guard; only the development proxy rewrites Origin.
        if (req.getHeader("origin"))
          req.setHeader("origin", new URL(target).origin);
      });
    },
  };
  return {
    plugins: [vue()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: { "/api": proxy, "/assets": proxy, "/openapi.json": proxy },
    },
    build: { assetsDir: "static" },
    test: { environment: "happy-dom", clearMocks: true },
  };
});
