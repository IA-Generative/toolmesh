import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { fetchMyTools } from "../auth/api";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Badge from "@codegouvfr/react-dsfr/Badge";
import Tile from "@codegouvfr/react-dsfr/Tile";

const TYPE_LABELS = { mcp: "Serveur MCP", api: "API", skill: "Skill" };

export default function Home() {
  const { user } = useAuth();
  const [tools, setTools] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMyTools().then((d) => setTools(d.tools)).catch((e) => setError(e.message));
  }, []);

  return (
    <main id="contenu" className="fr-container fr-my-8w">
      <h1>Mes outils</h1>
      <p className="fr-text--lead">Bonjour {user.username}, voici les outils auxquels vous avez accès.</p>

      {error && (
        <Alert severity="error" title="Impossible de charger vos outils" description={error} />
      )}
      {!tools && !error && <p role="status">Chargement…</p>}
      {tools?.length === 0 && (
        <Alert severity="info" title="Aucun outil disponible" description="Votre compte n'a accès à aucun outil pour le moment." />
      )}

      {tools?.length > 0 && (
        <div className="fr-grid-row fr-grid-row--gutters">
          {tools.map((t) => (
            <div key={t.name} className="fr-col-12 fr-col-md-6 fr-col-lg-4">
              <Tile
                title={t.name}
                titleAs="h2"
                desc={t.description}
                start={<Badge as="span" small severity="info" noIcon>{TYPE_LABELS[t.type] ?? t.type}</Badge>}
                detail={t.required_role ? `Rôle requis : ${t.required_role}` : "Accessible à tous"}
              />
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

