import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      // HMR injeta scripts/estilos em desenvolvimento. O build mantém a CSP restrita.
      name: "development-csp",
      apply: "serve",
      transformIndexHtml(html) {
        return html.replace(
          /\s*<meta http-equiv="Content-Security-Policy"[^>]*>/i,
          "",
        );
      },
    },
  ],
  server: { proxy: { "/api": "http://127.0.0.1:8010" } },
  preview: { proxy: { "/api": "http://127.0.0.1:8010" } },
});
