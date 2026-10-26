import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import Select from "@codegouvfr/react-dsfr/Select";
import { METHODS, NAME_HINT, emptyTool } from "./toolDraft";

// Déclaration manuelle des outils d'une source, en attendant leur découverte automatique.
export default function ToolsEditor({ tools, isApi, errors, onChange }) {
  const update = (id, patch) => onChange(tools.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  const remove = (id) => onChange(tools.filter((t) => t.id !== id));

  return (
    <>
      <p className="fr-text--sm">
        Déclarez les outils exposés par {isApi ? "cette API (un par endpoint)" : "ce serveur"}. La découverte
        automatique les remplacera plus tard.
      </p>
      {tools.map((t, i) => {
        const e = errors?.[i] ?? {};
        return (
          <fieldset key={t.id} className="fr-fieldset fr-mb-3w" style={{ border: "1px solid var(--border-default-grey)", borderRadius: "0.5rem", padding: "1rem" }}>
            <legend className="fr-fieldset__legend fr-text--bold">Outil {i + 1}</legend>
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
            {tools.length > 1 && (
              <Button type="button" priority="tertiary" size="small" iconId="fr-icon-delete-line" onClick={() => remove(t.id)}>
                Retirer cet outil
              </Button>
            )}
          </fieldset>
        );
      })}
      <Button type="button" priority="secondary" iconId="fr-icon-add-line" onClick={() => onChange([...tools, emptyTool()])}>
        Ajouter un outil
      </Button>
    </>
  );
}
