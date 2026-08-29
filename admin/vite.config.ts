import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// admin-dashboard change: a plain Vite dev server, no proxy magic — the
// admin API's base URL is read from VITE_ADMIN_API_URL (see src/api.ts),
// so dev/prod just point at a different backend, no rewrite rules here.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
});
