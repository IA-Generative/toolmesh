import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "@playwright/test";

const DOCS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/frontend");
const USER = { sub: "1", username: "user", email: "u@x.fr", roles: ["user"] };
const TOOLS = {
  user: "user", roles: ["user"],
  tools: [{ name: "datetime", description: "Date et heure", source: "mcp", type: "mcp", required_role: null }],
};
const VERSION = "1.2.3"; // valeur fictive : les captures restent stables d'une release à l'autre

const asAnonymous = (p) => p.route("**/api/auth/me", (r) => r.fulfill({ status: 401, json: {} }));
const asUser = (p) => p.route("**/api/auth/me", (r) => r.fulfill({ json: USER }));
const settle = async (p) => {
      await p.evaluate(() => document.fonts.ready);
      await p.getByText(`Version ${VERSION}`).first().waitFor({ state: "attached" });
}; // attend les polices DSFR et la version (footer public ou barre latérale)
const out = (...parts) => path.join(DOCS, ...parts);
const full = { fullPage: true, animations: "disabled" };
const sidebar = (p) => p.getByRole("complementary", { name: "Barre latérale" });

test.beforeEach(({ page }) =>
  page.route("**/api/health", (r) => r.fulfill({ json: { status: "ok", version: VERSION } })));

test("@docs accueil connecté", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  await settle(page);
  await page.screenshot({ path: out("pages/accueil/connecte.png"), ...full });
  await sidebar(page).screenshot({ path: out("components/sidebar/connecte.png") });
  await page.getByRole("banner").screenshot({ path: out("components/topbar/connecte.png") });
});

test("@docs accueil menu du compte ouvert", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  await page.getByRole("button", { name: "user", exact: true }).click();
  await page.getByRole("group", { name: "Menu du compte" }).waitFor();
  await settle(page);
  // la barre latérale entière, car le panneau est positionné au-dessus du bouton
  await sidebar(page).screenshot({ path: out("components/user-menu/ouvert.png") });
});

test("@docs accueil modale de recherche", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  await sidebar(page).getByRole("button", { name: "Rechercher" }).click();
  await page.getByRole("dialog").getByRole("searchbox").waitFor();
  await settle(page);
  await page.screenshot({ path: out("components/search-modal/ouverte.png"), animations: "disabled" });
});

test("@docs accueil paramètres d'affichage", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  await page.getByRole("banner").getByRole("button", { name: "Paramètres d'affichage" }).click();
  await page.getByRole("dialog", { name: "Paramètres d'affichage" }).waitFor();
  await settle(page);
  await page.screenshot({ path: out("components/display-modal/ouverte.png"), animations: "disabled" });
});

test("@docs accueil erreur outils", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ status: 500, json: {} }));
  await page.goto("/accueil");
  await page.getByRole("alert").waitFor();
  await page.screenshot({ path: out("pages/accueil/erreur-outils.png"), ...full });
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("@docs accueil mobile", async ({ page }) => {
    await asUser(page);
    await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
    await page.goto("/accueil");
    await page.getByText("datetime").waitFor();
    await settle(page);
    await page.screenshot({ path: out("pages/accueil/mobile.png"), ...full });

    await page.getByRole("button", { name: "Menu" }).click();
    await sidebar(page).waitFor();
    await settle(page);
    await page.screenshot({ path: out("pages/accueil/mobile-menu.png"), animations: "disabled" });
  });
});

test("@docs landing anonyme", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/");
  await settle(page);
  await page.screenshot({ path: out("pages/landing/anonyme.png"), ...full });
  await page.getByRole("banner").screenshot({ path: out("components/header/anonyme.png") });
  await page.getByRole("contentinfo").screenshot({ path: out("components/footer/footer.png") });
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

test("@docs accueil avec filtre", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil?q=date");
  await page.getByText("datetime").waitFor();
  await settle(page);
  await page.screenshot({ path: out("pages/accueil/filtre.png"), ...full });
});
