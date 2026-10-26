import { useState } from "react";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import RadioButtons from "@codegouvfr/react-dsfr/RadioButtons";
import Select from "@codegouvfr/react-dsfr/Select";
import { sendFeedback } from "../auth/api";

// « Cette recherche a-t-elle trouvé ce que vous cherchiez ? » : alimente le jeu de données (après relecture d'un admin).
export default function SearchFeedback({ searchId, results, allTools }) {
  const [answer, setAnswer] = useState(null); // "found" | "not_found"
  const [chosen, setChosen] = useState("");
  const [comment, setComment] = useState("");
  const [state, setState] = useState({ status: "idle", error: null });

  if (state.status === "done") {
    return <Alert severity="success" small description="Merci, votre retour sera examiné avant de servir à améliorer la recherche." />;
  }

  const submit = async () => {
    setState({ status: "sending", error: null });
    try {
      await sendFeedback(searchId, { verdict: answer, expected: chosen ? [chosen] : [], comment });
      setState({ status: "done", error: null });
    } catch (e) {
      setState({ status: "idle", error: e.message });
    }
  };
  const invalid = answer === "found" && !chosen;

  return (
    <section className="fr-callout fr-callout--sm fr-mb-3w" aria-labelledby="feedback-titre">
      <h2 id="feedback-titre" className="fr-callout__title fr-text--md">Cette recherche a-t-elle trouvé ce que vous cherchiez ?</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <Button size="small" priority={answer === "found" ? "primary" : "secondary"} iconId="fr-icon-thumb-up-line" onClick={() => setAnswer("found")} disabled={results.length === 0}>
          Oui
        </Button>
        <Button size="small" priority={answer === "not_found" ? "primary" : "secondary"} iconId="fr-icon-thumb-down-line" onClick={() => setAnswer("not_found")}>
          Non
        </Button>
      </div>

      {answer === "found" && (
        <RadioButtons
          legend="Quel outil convenait ?"
          small
          options={results.map((t) => ({
            label: t.name,
            nativeInputProps: { name: "expected", value: t.name, checked: chosen === t.name, onChange: () => setChosen(t.name) },
          }))}
        />
      )}
      {answer === "not_found" && (
        <Select
          label="Quel outil convenait ?"
          hint="Facultatif : laissez vide si le catalogue n'a rien pour cette demande"
          nativeSelectProps={{ value: chosen, onChange: (e) => setChosen(e.target.value) }}
        >
          <option value="">Aucun outil du catalogue ne convient</option>
          {allTools.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
        </Select>
      )}
      {answer && (
        <>
          <Input
            label="Un commentaire ?"
            hintText="Facultatif"
            nativeInputProps={{ value: comment, maxLength: 1000, onChange: (e) => setComment(e.target.value) }}
          />
          {state.error && <Alert className="fr-mb-2w" severity="error" small description={state.error} />}
          <Button size="small" onClick={submit} disabled={invalid || state.status === "sending"}>
            {state.status === "sending" ? "Envoi…" : "Envoyer mon retour"}
          </Button>
        </>
      )}
    </section>
  );
}
