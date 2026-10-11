import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development, /api calls are forwarded to the FastAPI backend on port 7860.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:7860" },
  },
});
