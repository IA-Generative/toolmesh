import { test, expect } from "@playwright/test";

const ME = "**/api/auth/me";
const USER = { sub: "1", username: "user", email: "u@x.fr", roles: ["user"] };
const TOOLS = {
  user: "user", roles: ["user"],
  tools: [{ name: "datetime", description: "Date et heure", source: "mcp", type: "mcp", required_role: null }],
};
const asAnonymous = (page) => page.route(ME, (r) => r.fulfill({ status: 401, json: {} }));
const asUser = (page) => page.route(ME, (r) => r.fulfill({ json: USER }));

test("anonyme : les boutons Se connecter visent /accueil", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/");
  const href = /\/api\/auth\/login\?redirect=%2Faccueil/;
  await expect(page.getByRole("banner").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", href);
  await expect(page.getByRole("main").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", href);
});

test("connecté sur / : redirigé vers /accueil", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/");
  await expect(page).toHaveURL(/\/accueil$/);
});

test("/accueil anonyme : part vers le login", async ({ page }) => {
  await asAnonymous(page);
  await page.route("**/api/auth/login**", (r) => r.fulfill({ status: 200, body: "login" }));
  const loginReq = page.waitForRequest(/\/api\/auth\/login\?redirect=%2Faccueil/);
  await page.goto("/accueil");
  await loginReq;
});

test("/accueil connecté : affiche les outils", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
  await page.goto("/accueil");
  await expect(page.getByRole("heading", { name: "Mes outils", level: 1 })).toBeVisible();
  await expect(page.getByText("Bonjour user")).toBeVisible();
  await expect(page.getByText("datetime")).toBeVisible();
});

test("/accueil : erreur serveur sur les outils", async ({ page }) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ status: 500, json: {} }));
  await page.goto("/accueil");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("page inconnue : affiche la page 404", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/n-importe-quoi");
  await expect(page.getByRole("heading", { name: "Page non trouvée" })).toBeVisible();
});
