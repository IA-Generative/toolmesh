import { useCallback, useEffect, useRef, useState } from "react";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import Select from "@codegouvfr/react-dsfr/Select";
import { SegmentedControl } from "@codegouvfr/react-dsfr/SegmentedControl";
import JsonView from "../tools/JsonView";
import SchemaForm from "../tools/SchemaForm";
import { addHistory } from "../tools/history";
import { DEFAULT_MODEL, MODELS, modelLabel } from "../tools/models";
import ToolCard from "../tools/ToolCard";
import { toArguments, toFormValues, validateArguments } from "../tools/schema";
import "./ToolTester.css";

// Exécution simulée, en attendant l'appel réel via le backend.
const simulateCall = (tool, args, model) =>
  new Promise((resolve) =>
    setTimeout(
      () =>
        resolve({
          simulated: true,
          tool: tool.name,
          ...(model && { model }),
          arguments: args,
          result: "Réponse simulée : le backend n'est pas encore branché.",
        }),
      600,
    ),
  );

function CopyButton({ value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Presse-papiers indisponible (contexte non sécurisé) : rien à faire.
    }
  };
  return (
    <Button size="small" priority="tertiary no outline" iconId={copied ? "fr-icon-check-line" : "fr-icon-clipboard-line"} onClick={copy}>
      {copied ? "Copié" : "Copier"}
    </Button>
  );
}

const STAGES = ["Entrée", "Exécution", "Sortie"];

// Barre de progression de gauche à droite : saisie -> exécution -> résultat.
function Progress({ running, done }) {
  const current = done ? 2 : running ? 1 : 0;
  return (
    <ol className="tool-progress" aria-label="Progression du test">
      <li className="tool-progress__track" aria-hidden="true">
        <span className="tool-progress__fill" style={{ width: `${current * 50}%` }} data-running={running} />
      </li>
      {STAGES.map((label, i) => (
        <li
          key={label}
          className={`tool-progress__node${i < current || (i === current && done) ? " is-done" : ""}${i === current && !done ? " is-current" : ""}`}
          aria-current={i === current ? "step" : undefined}
        >
          <span className="tool-progress__dot" aria-hidden="true">
            {i < current || (i === 2 && done) ? <span className="fr-icon-check-line fr-icon--sm" /> : i + 1}
          </span>
          <span className="tool-progress__label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

function Output({ running, output }) {
  const [tab, setTab] = useState("response");
  if (running) {
    return (
      <div className="tool-modal__empty" role="status">
        <span className="tool-modal__spinner" aria-hidden="true" />
        <p>Exécution en cours…</p>
      </div>
    );
  }
  if (!output) {
    return (
      <div className="tool-modal__empty">
        <span className="fr-icon-terminal-box-line" aria-hidden="true" />
        <p>Renseignez l'entrée puis lancez l'exécution : le résultat s'affichera ici.</p>
      </div>
    );
  }
  const shown = tab === "response" ? output.response : output.request;
  return (
    <>
      <div className="tool-modal__status">
        <span className="tool-modal__pill tool-modal__pill--ok">
          <span className="fr-icon-checkbox-circle-fill fr-icon--sm" aria-hidden="true" /> Succès
        </span>
        <span className="tool-modal__pill">{output.ms} ms</span>
        {output.model && <span className="tool-modal__pill">{modelLabel(output.model)}</span>}
        <span className="tool-modal__pill">simulation</span>
      </div>
      <div className="tool-modal__tabs">
        <SegmentedControl
          small
          hideLegend
          legend="Contenu affiché"
          segments={[
            { label: "Réponse", nativeInputProps: { checked: tab === "response", onChange: () => setTab("response") } },
            { label: "Requête", nativeInputProps: { checked: tab === "request", onChange: () => setTab("request") } },
          ]}
        />
        <CopyButton value={shown} />
      </div>
      <JsonView value={shown} label={tab === "response" ? "Réponse" : "Requête"} />
    </>
  );
}

export default function ToolTester({ tool, open, onClose, initial = null }) {
  const schema = tool.input_schema;
  const isSkill = tool.type === "skill";
  const [values, setValues] = useState(() => toFormValues(schema, initial?.args));
  const [model, setModel] = useState(initial?.model ?? DEFAULT_MODEL);
  const [rawMode, setRawMode] = useState(false);
  const [raw, setRaw] = useState("");
  const [errors, setErrors] = useState({});
  const [rawErrors, setRawErrors] = useState([]);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState(null);
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const switchMode = (toRaw) => {
    if (toRaw) {
      setRaw(JSON.stringify(toArguments(schema, values).args, null, 2));
      setRawErrors([]);
    } else {
      try {
        setValues(toFormValues(schema, JSON.parse(raw)));
        setErrors({});
      } catch {
        // JSON illisible : on garde les valeurs du formulaire.
      }
    }
    setRawMode(toRaw);
  };

  const reset = () => {
    setModel(DEFAULT_MODEL);
    setValues(toFormValues(schema));
    setRaw("{}");
    setErrors({});
    setRawErrors([]);
    setOutput(null);
  };

  const run = useCallback(async () => {
    if (!schema || running) return;
    let args;
    if (rawMode) {
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (e) {
        return setRawErrors([`JSON invalide : ${e.message}`]);
      }
      const problems = validateArguments(schema, parsed);
      setRawErrors(problems);
      if (problems.length) return;
      args = parsed;
    } else {
      const res = toArguments(schema, values);
      setErrors(res.errors);
      if (Object.keys(res.errors).length) return;
      args = res.args;
    }
    setRunning(true);
    setOutput(null);
    const started = performance.now();
    const response = await simulateCall(tool, args, isSkill ? model : null);
    const ms = Math.round(performance.now() - started);
    setOutput({ request: isSkill ? { model, arguments: args } : args, response, ms, model: isSkill ? model : null });
    addHistory({ tool: tool.name, type: tool.type, args, model: isSkill ? model : null, ok: true, ms });
    setRunning(false);
  }, [schema, running, rawMode, raw, values, tool, isSkill, model]);

  // Ctrl/Cmd + Entrée lance l'exécution depuis n'importe quel champ.
  const onKeyDown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      run();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      className="tool-modal"
      aria-labelledby="tool-modal-title"
      onClose={onClose}
      onClick={(e) => e.target === dialogRef.current && onClose()}
      onKeyDown={onKeyDown}
    >
      <div className="tool-modal__header">
        <h2 id="tool-modal-title" className="fr-h5 fr-mb-0">
          <span className="fr-icon-flashlight-line fr-mr-1w" aria-hidden="true" />
          Tester <strong>{tool.name}</strong>
        </h2>
        <Button priority="tertiary no outline" iconId="fr-icon-close-line" onClick={onClose}>
          Fermer
        </Button>
      </div>

      <Progress running={running} done={Boolean(output)} />

      <div className="tool-modal__grid">
        <section className="tool-modal__panel" aria-labelledby="tool-modal-input">
          <header className="tool-modal__panel-head">
            <h3 id="tool-modal-input" className="tool-modal__panel-title">
              Entrée
            </h3>
            {schema && (
              <Button size="small" priority="tertiary no outline" iconId="fr-icon-refresh-line" onClick={reset}>
                Réinitialiser
              </Button>
            )}
          </header>
          <div className="tool-modal__panel-body">
            {!schema ? (
              <Alert severity="info" small description="Aucun schéma d'entrée n'est disponible : cet outil ne peut pas être testé." />
            ) : (
              <>
                {isSkill && (
                  <Select
                    label="Modèle"
                    hint="Modèle qui exécute le skill"
                    nativeSelectProps={{ value: model, onChange: (e) => setModel(e.target.value) }}
                  >
                    {MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                  </Select>
                )}
                <SegmentedControl
                  small
                  hideLegend
                  legend="Mode de saisie"
                  segments={[
                    { label: "Formulaire", iconId: "fr-icon-edit-box-line", nativeInputProps: { checked: !rawMode, onChange: () => switchMode(false) } },
                    { label: "JSON", iconId: "fr-icon-code-s-slash-line", nativeInputProps: { checked: rawMode, onChange: () => switchMode(true) } },
                  ]}
                />
                {rawMode ? (
                  <Input
                    label="Arguments"
                    hintText="Objet JSON conforme au schéma"
                    textArea
                    nativeTextAreaProps={{ value: raw, onChange: (e) => setRaw(e.target.value), rows: 10, spellCheck: false, className: "tool-modal__mono" }}
                    state={rawErrors.length ? "error" : "default"}
                    stateRelatedMessage={rawErrors.length ? rawErrors.join(" ") : undefined}
                  />
                ) : (
                  <SchemaForm
                    schema={schema}
                    values={values}
                    errors={errors}
                    onChange={(key, v) => setValues((cur) => ({ ...cur, [key]: v }))}
                  />
                )}
                <details className="fr-mt-2w">
                  <summary>Schéma d'entrée</summary>
                  <JsonView value={schema} label="Schéma d'entrée" />
                </details>
              </>
            )}
          </div>
        </section>

        <div className="tool-modal__hub">
          <div className="tool-modal__hub-card">
            <ToolCard tool={tool} titleAs="h3" />
            <Button className="tool-modal__run" size="large" onClick={run} disabled={running || !schema} iconId="fr-icon-play-circle-fill">
              {running ? "Exécution…" : "Exécuter"}
            </Button>
            <p className="fr-text--xs tool-modal__hint">Ctrl + Entrée</p>
          </div>
        </div>

        <section className="tool-modal__panel" aria-labelledby="tool-modal-output" aria-live="polite">
          <header className="tool-modal__panel-head">
            <h3 id="tool-modal-output" className="tool-modal__panel-title">
              Sortie
            </h3>
          </header>
          <div className="tool-modal__panel-body">
            <Output running={running} output={output} />
          </div>
        </section>
      </div>
    </dialog>
  );
}
