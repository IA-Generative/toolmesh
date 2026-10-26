export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8010";

// Le backend n'accepte que des chemins internes ("/..."), sinon il retombe sur "/".
export const loginUrl = (redirect = "/accueil") =>
  `${API_URL}/api/auth/login?redirect=${encodeURIComponent(redirect)}`;

export async function fetchMe() {
  const res = await fetch(`${API_URL}/api/auth/me`, { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`/me: ${res.status}`);
  return res.json(); // { sub, username, email, roles }
}

export async function logout() {
  const res = await fetch(`${API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  const { redirectUrl } = await res.json();
  window.location.assign(redirectUrl); // termine la session SSO Keycloak
}

export async function fetchMyTools() {
  const res = await fetch(`${API_URL}/api/me/tools`, { credentials: "include" });
  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json(); // { user, roles, tools: [{ name, description, source, type, tags, source_url, source_version, method, path, input_schema, auth_mode, audience, required_role }] }
}

export async function fetchVersion(){
  const res = await fetch(`${API_URL}/api/health`);
  if(!res.ok) throw new Error(`/health: ${res.status}`);
  return (await res.json()).version;
}
// Message lisible à partir d'une réponse d'erreur du backend ({ detail: string | [{ loc, msg }] }).
async function errorMessage(res) {
  if (res.status === 401) return "Session expirée : reconnectez-vous.";
  try {
    const { detail } = await res.json();
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => `${d.loc.slice(1).join(".")} : ${d.msg}`).join(" ; ");
  } catch {
    // Corps absent ou illisible : on retombe sur le code HTTP.
  }
  return `Erreur ${res.status}`;
}

export async function createSource(payload) {
  const res = await fetch(`${API_URL}/api/sources`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json(); // { id, name, type, ..., tools: [{ name, ... }] }
}

// Aperçu des outils d'un serveur MCP / d'une API, sans rien enregistrer.
export async function discoverTools(payload) {
  const res = await fetch(`${API_URL}/api/sources/discover`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json(); // { tools: [{ name, description, tags, method, path, input_schema }], version }
}

// Exécute un outil pour l'utilisateur connecté.
export async function callTool(name, args, model = null) {
  const res = await fetch(`${API_URL}/api/me/tools/${encodeURIComponent(name)}/call`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arguments: args, model }),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json(); // { ok, status, content_type, content, truncated, duration_ms }
}

// Recherche (pertinence) et/ou filtres sur les outils visibles. `mode` dit comment les résultats ont été classés.
export async function searchTools({ q = "", type = null, tags = [], source = null, version = null, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (type) params.set("type", type);
  tags.forEach((t) => params.append("tag", t));
  if (source) params.set("source", source);
  if (version) params.set("version", version);
  params.set("limit", String(limit));
  const res = await fetch(`${API_URL}/api/me/tools/search?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json(); // { tools, mode: "hybrid" | "keyword" | "basic" | "filter" }
}
