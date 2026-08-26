import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    // Keep discovery inside the application source tree. Temporary workspaces
    // can contain their own dependency trees and must never become CI tests.
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "**/node_modules/**", "**/.tmp_*/**"],
  },
});
