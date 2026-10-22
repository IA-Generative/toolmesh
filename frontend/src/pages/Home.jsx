import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Badge from "@codegouvfr/react-dsfr/Badge";
import Tile from "@codegouvfr/react-dsfr/Tile";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import { useAuth } from "../auth/AuthContext";
import { fetchMyTools } from "../auth/api";
import { filterTools, TYPE_LABELS } from "../tools/tools";

const plural = (n) => `${n} outil${n > 1 ? "s" : ""}`;

export default function Home() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [tools, setTools] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null)
  const q = params.get("q") ?? ""; // l'URL reste la seule source de vérité

  const setQuery = (value) =>
    setParams(value ? {q: value} : {}, { replace: true}) // pas d'entrée d'historique

  const clear = () =>{ setQuery(""); inputRef.current?.focus()};

  const visible = tools && filterTools(tools, q);

  useEffect(() => {
    fetchMyTools().then((d) => setTools(d.tools)).catch((e) => setError(e.message));
  }, []);


  return (
    <div>
      <h1>Mes outils</h1>
      <p className="fr-text--lead">Bonjour {user.username}, voici les outils auxquels vous avez accès.</p>

      {error && <Alert severity="error" title="Impossible de charger vos outils" description={error} />}
      {!tools && !error && <p role="status">Chargement…</p>}
      {tools?.length === 0 && (
        <Alert severity="info" title="Aucun outil disponible" description="Votre compte n'a accès à aucun outil pour le moment." />
      )}

      {tools?.length > 0 && (
        <search aria-label="Rechercher un outil" className="fr-mb-3w">
          <Input
            label="Rechercher un outil"
            nativeInputProps={{
              ref: inputRef,
              type: "search",
              value: q,
              onChange: (e) => setQuery(e.target.value),
              onKeyDown: (e) => e.key === "Escape" && clear(),
            }}
          />
          {q && (
            <Button priority="tertiary no outline" iconId="fr-icon-close-line" onClick={clear}>
              Effacer
            </Button>
          )}
          <p role="status" className="fr-text--sm">
            {q ? `${plural(visible.length)} sur ${tools.length}` : plural(tools.length)}
          </p>
        </search>
      )}

      {tools?.length > 0 && visible.length === 0 && (
        <Alert severity="info" title="Aucun résultat" description={`Aucun outil ne correspond à « ${params.get("q")} ».`} />
      )}

      {visible?.length > 0 && (
        <ul className="fr-grid-row fr-grid-row--gutters fr-raw-list">
          {visible.map((t) => (
              <li key={t.name} className="fr-col-12 fr-col-md-6 fr-col-lg-4">
                <Tile
                  title={t.name}
                  titleAs="h2"
                  desc={t.description}
                  start={<Badge as="span" small severity="info" noIcon>{TYPE_LABELS[t.type] ?? t.type}</Badge>}
                  detail={t.required_role ? `Rôle requis : ${t.required_role}` : "Accessible à tous"}
                />
              </li>
          ))}
        </ul>
      )}
    </div>
  );
}
