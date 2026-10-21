import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:3000",
    viewport: { width: 1280, height: 720 },
    locale: "fr-FR",
   },
  webServer: {
    command: "bun run dev",
    env: { VITE_API_URL: "" },
    url: "http://localhost:3000",
    reuseExistingServer: true,
  },
});
