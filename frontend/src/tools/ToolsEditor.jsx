import { useState } from "react";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import Select from "@codegouvfr/react-dsfr/Select";
import { METHODS, NAME_HINT, emptyTool } from "./toolDraft";

// Déclaration manuelle des outils d'une source, en attendant leur découverte automatique.
export default function ToolsEditor({ tools, isApi, errors, onChange, onDiscover }) {
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState(null);
  const update = (id, patch) => onChange(tools.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  const remove = (id) => onChange(tools.filter((t) => t.id !== id));
  const manual = tools.filter((t) => !t.discovered);
  const discovered = tools.filter((t) => t.discovered);

  const discover = async () => {
    setDiscovering(true);
    setDiscoverError(null);
    try {
      // Les outils saisis à la main sont conservés ; la découverte remplace seulement les précédents résultats.
      onChange([...manual, ...(await onDiscover())]);
    } catch (e) {
      setDiscoverError(e.message);
    } finally {
      setDiscovering(false);
    }
  };

  return (
    <>
      <p className="fr-text--sm">
        Les outils sont découverts automatiquement {isApi ? "à partir du Swagger" : "auprès du serveur"} lorsque vous
        ajoutez la source. Vous pouvez les découvrir dès maintenant pour les relire, en retirer, ou en déclarer à la main.
      </p>
      <ul className="fr-btns-group fr-btns-group--inline-md">
        <li>
          <Button type="button" iconId="fr-icon-search-line" onClick={discover} disabled={discovering}>
            {discovering ? "Découverte en cours…" : "Découvrir maintenant"}
          </Button>
        </li>
        <li>
          <Button type="button" priority="secondary" iconId="fr-icon-add-line" onClick={() => onChange([...tools, emptyTool()])}>
            Ajouter un outil à la main
          </Button>
        </li>
      </ul>
      {discoverError && <Alert className="fr-mb-2w" severity="error" small title="Découverte impossible" description={discoverError} />}
      {tools.length === 0 && !discoverError && (
        <p className="fr-text--sm" role="status">Aucun outil déclaré : ils seront découverts à l'ajout.</p>
      )}

      {discovered.length > 0 && (
        <>
          <h2 className="fr-h6 fr-mt-2w" aria-live="polite">{discovered.length} outil{discovered.length > 1 ? "s" : ""} découvert{discovered.length > 1 ? "s" : ""}</h2>
          <ul className="fr-raw-list">
            {discovered.map((t) => (
              <li key={t.id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0", borderBottom: "1px solid var(--border-default-grey)" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>{t.name}</strong>
                  {t.method && isApi && <code className="fr-ml-1w">{t.method} {t.path}</code>}
                  {t.description && <p className="fr-text--sm fr-mb-0" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.description}</p>}
                </div>
                <Button type="button" priority="tertiary no outline" size="small" iconId="fr-icon-delete-line" onClick={() => remove(t.id)}>
                  Retirer<span className="fr-sr-only"> {t.name}</span>
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}

      {manual.map((t) => {
        const i = tools.indexOf(t);
        const e = errors?.[i] ?? {};
        return (
          <fieldset key={t.id} className="fr-fieldset fr-mt-3w" style={{ border: "1px solid var(--border-default-grey)", borderRadius: "0.5rem", padding: "1rem" }}>
            <legend className="fr-fieldset__legend fr-text--bold">Outil déclaré à la main</legend>
            <Input label="Nom" hintText={NAME_HINT} nativeInputProps={{ value: t.name, onChange: (ev) => update(t.id, { name: ev.target.value }) }} state={e.name ? "error" : "default"} stateRelatedMessage={e.name} />
            <Input label="Description" hintText="Facultative" nativeInputProps={{ value: t.description, onChange: (ev) => update(t.id, { description: ev.target.value }) }} />
            <Input label="Tags" hintText="Séparés par des virgules" nativeInputProps={{ value: t.tags, onChange: (ev) => update(t.id, { tags: ev.target.value }) }} />
            {isApi && (
              <div className="fr-grid-row fr-grid-row--gutters">
                <div className="fr-col-12 fr-col-md-4">
                  <Select label="Méthode" nativeSelectProps={{ value: t.method, onChange: (ev) => update(t.id, { method: ev.target.value }) }}>
                    {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </Select>
                </div>
                <div className="fr-col-12 fr-col-md-8">
                  <Input label="Chemin" nativeInputProps={{ value: t.path, placeholder: "/orders/{id}", onChange: (ev) => update(t.id, { path: ev.target.value }) }} state={e.path ? "error" : "default"} stateRelatedMessage={e.path} />
                </div>
              </div>
            )}
            <Input
              label="Schéma d'entrée (JSON Schema)"
              hintText="Facultatif ; permet de tester l'outil avec un formulaire"
              textArea
              nativeTextAreaProps={{ value: t.schema, rows: 5, spellCheck: false, onChange: (ev) => update(t.id, { schema: ev.target.value }) }}
              state={e.schema ? "error" : "default"}
              stateRelatedMessage={e.schema}
            />
            <Button type="button" priority="tertiary" size="small" iconId="fr-icon-delete-line" onClick={() => remove(t.id)}>
              Retirer cet outil
            </Button>
          </fieldset>
        );
      })}
    </>
  );
}
