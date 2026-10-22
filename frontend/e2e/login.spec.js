import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ME = "**/api/auth/me";
const USER = { sub: "1", username: "user", email: "u@x.fr", roles: ["user"] };
const TOOLS = {
  user: "user", roles: ["user"],
  tools: [
    { name: "datetime", description: "Date et heure", source: "mcp", type: "mcp", required_role: null },
    { name: "calendar", description: "Agenda partagé", source: "api", type: "api", required_role: "user" },
  ],
};
const asUserWithTools = async (page) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: TOOLS }));
};
const asUserWithNoTools = async (page) => {
  await asUser(page);
  await page.route("**/api/me/tools", (r) => r.fulfill({ json: { ...TOOLS, tools: [] } }));
};
const sidebar = (page) => page.getByRole("complementary", { name: "Barre latérale" });
const asAnonymous = (page) => page.route(ME, (r) => r.fulfill({ status: 401, json: {} }));
const asUser = (page) => page.route(ME, (r) => r.fulfill({ json: USER }));

test("anonyme : les boutons Se connecter visent /accueil", async ({ page }) => {
  await asAnonymous(page);
  await page.goto("/");
  const href = /\/api\/auth\/login\?redirect=%2Faccueil/;
  await expect(page.getByRole("banner").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", href);
  await expect(page.getByRole("main").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", href);
});

for (const region of ["banner", "main"]) {
  test(`connexion (${region}) : navigation complète vers le backend`, async ({ page }) => {
    await asAnonymous(page);
    await page.route("**/api/auth/login**", (route) =>
      route.fulfill({ contentType: "text/html", body: "<h1>Login backend</h1>" }));
    await page.goto("/");

    const link = page.getByRole(region).getByRole("link", { name: "Se connecter" });
    await expect(link).toHaveAttribute("href", "/api/auth/login?redirect=%2Faccueil");
    const loginRequest = page.waitForRequest((request) =>
      request.isNavigationRequest() && request.url().includes("/api/auth/login?redirect=%2Faccueil"));
    await link.click();
    await loginRequest;

    await expect(page).toHaveURL(/\/api\/auth\/login\?redirect=%2Faccueil$/);
    await expect(page.getByRole("heading", { name: "Login backend" })).toBeVisible();
  });
}

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

test("accueil : la barre latérale présente la marque, la navigation et l'historique", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil");

  await expect(sidebar(page)).toBeVisible();
  await expect(page.getByRole("link", { name: /ToolMesh\s*,?\s*accueil/ })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Navigation principale" });
  await expect(nav.getByRole("link", { name: "Accueil" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Historique", level: 2 })).toBeVisible();
  await expect(sidebar(page).getByRole("link", { name: "Mentions légales" })).toBeVisible();
});

test("menu du compte : s'ouvre, affiche l'email, se ferme avec Échap puis au clic extérieur", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil");

  const trigger = page.getByRole("button", { name: "user", exact: true });
  const panel = page.getByRole("group", { name: "Menu du compte" });

  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toBeHidden();

  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(panel.getByText("u@x.fr")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Se déconnecter" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(trigger).toBeFocused();

  await trigger.click();
  await page.getByRole("heading", { name: "Mes outils" }).click();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
});

test("déconnexion depuis le menu du compte", async ({ page }) => {
  await asUserWithTools(page);
  await page.route("**/api/auth/logout", (r) =>
    r.fulfill({ json: { redirectUrl: "http://localhost:3000/mentions-legales" } }));
  await page.goto("/accueil");

  await page.getByRole("button", { name: "user", exact: true }).click();
  const logoutReq = page.waitForRequest((r) => r.url().includes("/api/auth/logout") && r.method() === "POST");
  await page.getByRole("group", { name: "Menu du compte" }).getByRole("button", { name: "Se déconnecter" }).click();
  await logoutReq;
  await expect(page).toHaveURL(/\/mentions-legales$/);
});

test("déconnexion depuis le mini header", async ({ page }) => {
  await asUserWithTools(page);
  await page.route("**/api/auth/logout", (r) =>
    r.fulfill({ json: { redirectUrl: "http://localhost:3000/mentions-legales" } }));
  await page.goto("/accueil");

  await page.getByRole("banner").getByRole("button", { name: "Se déconnecter" }).click();
  await expect(page).toHaveURL(/\/mentions-legales$/);
});

test("recherche : la modale filtre les outils", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil");
  await expect(page.getByText("calendar")).toBeVisible();

  await sidebar(page).getByRole("button", { name: "Rechercher" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("searchbox").fill("date");
  await dialog.getByRole("button", { name: "Rechercher" }).click();

  await expect(page).toHaveURL(/\/accueil\?q=date$/);
  await expect(page.getByText("datetime")).toBeVisible();
  await expect(page.getByText("calendar")).toHaveCount(0);
});

test("recherche sans résultat : affiche un message", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil?q=zzz");
  await expect(page.getByText("Aucun résultat")).toBeVisible();
});

// Même fenêtre de thème sur la landing (Header DSFR) et sur l'accueil (mini header)
for (const [nom, route, connecte] of [["landing", "/", false], ["accueil", "/accueil", true]]) {
  test(`paramètres d'affichage (${nom}) : ouvre la fenêtre et applique le thème sombre`, async ({ page }) => {
    if (connecte) await asUserWithTools(page); else await asAnonymous(page);
    await page.goto(route);

    await page.getByRole("banner").getByRole("button", { name: "Paramètres d'affichage" }).click();
    const dialog = page.getByRole("dialog", { name: "Paramètres d'affichage" });
    await expect(dialog).toBeVisible();

    await dialog.getByText("Thème sombre").click();
    await expect(page.locator("html")).toHaveAttribute("data-fr-theme", "dark");

    await dialog.getByRole("button", { name: "Fermer" }).click();
    await expect(dialog).toBeHidden();
  });
}

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("la barre latérale s'ouvre avec le bouton Menu et se ferme", async ({ page }) => {
    await asUserWithTools(page);
    await page.goto("/accueil");

    const nav = page.getByRole("navigation", { name: "Navigation principale" });
    const burger = page.getByRole("button", { name: "Menu" });

    await expect(nav).toBeHidden();
    await expect(burger).toHaveAttribute("aria-expanded", "false");

    await burger.click();
    await expect(nav).toBeVisible();
    await expect(burger).toHaveAttribute("aria-expanded", "true");

    await page.keyboard.press("Escape");
    await expect(nav).toBeHidden();

    await burger.click();
    await nav.getByRole("link", { name: "Accueil" }).click();
    await expect(nav).toBeHidden();
  });
});

test("accessibilité : aucune violation sur /accueil", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil");
  await page.getByText("datetime").waitFor();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("recherche en direct : filtre pendant la saisie et synchronise l'URL", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil");

  const champ = page.getByRole("searchbox", { name: "Rechercher un outil" });
  await champ.fill("DATE");                                    // casse ignorée
  await expect(page.getByText("datetime")).toBeVisible();
  await expect(page.getByText("calendar")).toHaveCount(0);
  await expect(page).toHaveURL(/\/accueil\?q=DATE$/);
  await expect(page.getByRole("status").filter({ hasText: "sur" })).toBeVisible();

  await page.reload();                                         // le filtre survit au rechargement
  await expect(champ).toHaveValue("DATE");
  await expect(page.getByText("calendar")).toHaveCount(0);
});

test("recherche en direct : Échap et « Effacer » vident le champ et rendent le focus", async ({ page }) => {
  await asUserWithTools(page);
  await page.goto("/accueil?q=date");
  const champ = page.getByRole("searchbox", { name: "Rechercher un outil" });

  await page.getByRole("button", { name: "Effacer" }).click();
  await expect(champ).toHaveValue("");
  await expect(champ).toBeFocused();
  await expect(page.getByText("calendar")).toBeVisible();

  await champ.fill("zzz");
  await expect(page.getByText("Aucun résultat")).toBeVisible();
  await champ.press("Escape");
  await expect(champ).toHaveValue("");
});

test("recherche en direct : barre absente si le compte n'a aucun outil", async ({ page }) => {
  await asUserWithNoTools(page);
  await page.goto("/accueil");
  await expect(page.getByText("Aucun outil disponible")).toBeVisible();   // le chargement est terminé
  await expect(page.getByRole("searchbox")).toHaveCount(0);
});
