export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8010";

// Le backend n'accepte que des chemins internes ("/..."), sinon il retombe sur "/".
export const loginUrl = (redirect = "/") =>
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
