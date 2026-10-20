import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "@playwright/test";

const DOCS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/frontend");
const USER = { sub: "1", username: "user", email: "u@x.fr", roles: ["user"] };
const TOOLS = {
  user: "user", roles: ["user"],
  tools: [{ name: "datetime", description: "Date et heure", source: "mcp", type: "mcp", required_role: null }],
};

const asAnonymous = (p) => p.route("**/api/auth/me", (r) => r.fulfill({ status: 401, json: {} }));
const asUser = (p) => p.route("**/api/auth/me", (r) => r.fulfill({ json: USER }));
const settle = (p) => p.evaluate(() => document.fonts.ready); // attend les polices DSFR
const out = (...parts) => path.join(DOCS, ...parts);
const full = { fullPage: true, animations: "disabled" };

test("@docs landing anonyme", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/");
  await settle(page);
  await page.screenshot({ path: out("pages/landing/anonyme.png"), ...full });
  await page.getByRole("banner").screenshot({ path: out("components/header/anonyme.png") });
  await page.getByRole("contentinfo").screenshot({ path: out("components/footer/footer.png") });
});

test("@docs accueil connecté", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  await settle(page);
  await page.screenshot({ path: out("pages/accueil/connecte.png"), ...full });
  await page.getByRole("banner").screenshot({ path: out("components/header/connecte.png") });
});

test("@docs accueil erreur outils", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ status: 500, json: {} }));
  await page.goto("/accueil");
  await page.getByRole("alert").waitFor();
  await page.screenshot({ path: out("pages/accueil/erreur-outils.png"), ...full });
});

test("@docs mentions légales", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/mentions-legales");
  await settle(page);
  await page.screenshot({ path: out("pages/mentions-legales/page.png"), ...full });
});

test("@docs page 404", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/n-importe-quoi");
  await page.getByRole("heading", { name: "Page non trouvée" }).waitFor();
  await settle(page);
  await page.screenshot({ path: out("pages/404/page.png"), ...full });
});
