import { chromium } from "playwright";

const browser = await chromium.launch(); // ajoute { channel: "chrome" } pour l'option B
const page = await browser.newPage();
await page.goto("https://example.com");
await page.screenshot({ path: "test.png" });
await browser.close();
