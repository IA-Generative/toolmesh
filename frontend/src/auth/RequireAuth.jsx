import { useEffect } from "react";
import { useLocation } from "react-router";
import { useAuth } from "./AuthContext";

export default function RequireAuth({ children }) {
  const { status, loginUrl } = useAuth();
  const { pathname, search } = useLocation();

  useEffect(() => {
    if (status === "anonymous") {
      // Redirection complète vers le backend (OIDC), puis retour sur la page demandée
      window.location.assign(loginUrl(pathname + search));
    }
  }, [status, loginUrl, pathname, search]);

  if (status !== "authenticated") return <p className="fr-container fr-my-8w" aria-live="polite" role="status">Chargement…</p>;
  return children;
}
