import Button from "@codegouvfr/react-dsfr/Button";
import { useAuth } from "../auth/AuthContext";

export default function Landing() {
  const { status, user, loginUrl } = useAuth();
  return (
    <main id="contenu" className="fr-container fr-my-8w">
      <h1>ToolMesh</h1>
      <p className="fr-text--lead">
        Passerelle d'outils pour agents IA : ToolMesh liste et appelle des
        outils (serveurs MCP, API, skills) au nom d'un utilisateur, sans perdre
        son identité ni lui donner plus de droits que prévu.
      </p>
      {status === "anonymous" && (
        <Button linkProps={{ href: loginUrl() }} iconId="fr-icon-user-fill">
          Se connecter
        </Button>
      )}
      {status === "authenticated" && <p>Connecté en tant que {user.username}</p>}
    </main>
  );
}
