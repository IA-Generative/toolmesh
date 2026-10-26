import { useState } from "react";
import { Link } from "react-router";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import RadioButtons from "@codegouvfr/react-dsfr/RadioButtons";
import Stepper from "@codegouvfr/react-dsfr/Stepper";
import { createSource, discoverTools } from "../auth/api";
import { MOCK_OPERATIONS, isExposed, splitLines } from "../tools/endpoints";
import ToolsEditor from "../tools/ToolsEditor";
import { NAME_HINT, NAME_RE, draftFromDiscovered, parseSchema, toolErrors } from "../tools/toolDraft";

const TYPES = [
  { value: "mcp", label: "Serveur MCP", hint: "Serveur exposant des outils via le protocole MCP" },
  { value: "api", label: "API", hint: "API HTTP existante" },
  { value: "skill", label: "Skill", hint: "Compétence réutilisable (pas d'appel réseau)" },
];

const AUTH_MODES = [
  { value: "token_exchange", label: "Token exchange", hint: "Le jeton de l'utilisateur est échangé contre un jeton pour ce service" },
  { value: "none", label: "Public (sans identifiants)", hint: "Le service est appelé sans authentification" },
];

const ACCESS_SCOPES = [
  { value: "all", label: "Tous les utilisateurs connectés" },
  { value: "role", label: "Les utilisateurs ayant un rôle précis" },
];

const INITIAL = {
  type: "mcp",
  name: "",
  description: "",
  tags: "",
  url: "",
  openapiUrl: "",
  includePatterns: "",
  excludePatterns: "",
  authMode: "token_exchange",
  audience: "",
  accessScope: "all",
  accessRole: "",
  schema: "",
  tools: [],
};

const splitList = (s) => s.split(",").map((v) => v.trim()).filter(Boolean);

// Un skill n'est pas appelé par le réseau : il n'a ni URL ni mode d'authentification.
const hasNetworkAccess = (type) => type !== "skill";

function stepsFor(type) {
  if (type === "api") return ["Définition", "Authentification", "Endpoints", "Outils", "Accès", "Récapitulatif"];
  if (type === "mcp") return ["Définition", "Authentification", "Outils", "Accès", "Récapitulatif"];
  return ["Définition", "Accès", "Récapitulatif"];
}

function errorsFor(step, f) {
  const e = {};
  if (step === "Définition") {
    if (!f.name.trim()) e.name = "Le nom est obligatoire.";
    else if (!NAME_RE.test(f.name.trim())) e.name = NAME_HINT;
    if (f.type === "skill" && !f.description.trim()) e.description = "La description est obligatoire pour un skill.";
    if (f.type !== "skill" && !f.url.trim()) e.url = "L'URL est obligatoire.";
    if (f.type === "api" && !f.openapiUrl.trim()) e.openapiUrl = "L'URL du Swagger est obligatoire.";
    if (f.type === "skill" && parseSchema(f.schema).error) e.schema = parseSchema(f.schema).error;
  }
  if (step === "Authentification" && f.authMode === "token_exchange" && !f.audience.trim()) {
    e.audience = "L'audience est obligatoire.";
  }
  if (step === "Outils") {
    const perTool = toolErrors(f.tools, f.type === "api");
    if (perTool.some((t) => Object.keys(t).length)) e.tools = perTool;
  }
  if (step === "Accès" && f.accessScope === "role" && !f.accessRole.trim()) {
    e.accessRole = "Renseignez le rôle requis.";
  }
  return e;
}

// Corps de POST /api/sources.
function buildPayload(f) {
  const isSkill = f.type === "skill";
  const isApi = f.type === "api";
  const base = {
    name: f.name.trim(),
    type: f.type,
    description: f.description.trim() || null,
    required_role: f.accessScope === "role" ? f.accessRole.trim() : null,
  };
  if (isSkill) {
    // Un skill est un outil unique, du même nom que la source.
    const tool = { name: base.name, description: base.description ?? "", tags: splitList(f.tags), input_schema: parseSchema(f.schema).value };
    return { ...base, tags: tool.tags, tools: [tool] };
  }
  return {
    ...base,
    url: f.url.trim(),
    openapi_url: isApi ? f.openapiUrl.trim() : null,
    auth_mode: f.authMode,
    audience: f.authMode === "token_exchange" ? f.audience.trim() : null,
    endpoint_include: isApi ? splitLines(f.includePatterns) : [],
    endpoint_exclude: isApi ? splitLines(f.excludePatterns) : [],
    tools: f.tools.map((t) => ({
      name: t.name.trim(),
      description: t.description.trim(),
      tags: splitList(t.tags),
      method: isApi ? t.method : null,
      path: isApi ? t.path.trim() : null,
      input_schema: parseSchema(t.schema).value,
    })),
  };
}

export default function AddTool() {
  const [form, setForm] = useState(INITIAL);
  const [index, setIndex] = useState(0);
  const [showErrors, setShowErrors] = useState(false);
  const [created, setCreated] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const steps = stepsFor(form.type);
  const step = steps[index];
  const errors = errorsFor(step, form);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const fieldState = (key) => (showErrors && errors[key] ? { state: "error", stateRelatedMessage: errors[key] } : {});

  const next = () => {
    if (Object.keys(errors).length) return setShowErrors(true);
    setShowErrors(false);
    setIndex((i) => i + 1);
  };
  const back = () => {
    setShowErrors(false);
    setIndex((i) => i - 1);
  };
  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      setCreated(await createSource(buildPayload(form)));
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (created) {
    const first = created.tools[0];
    return (
      <div>
        <h1>Ajouter un outil</h1>
        <Alert
          severity="success"
          title="Outil ajouté"
          description={`« ${created.name} » est enregistré avec ${created.tools.length} outil${created.tools.length > 1 ? "s" : ""}.`}
        />
        <ul className="fr-btns-group fr-btns-group--inline-md fr-mt-3w">
          {first && (
            <li><Link to={`/outils/${encodeURIComponent(first.name)}`} className="fr-btn">Voir {first.name}</Link></li>
          )}
          <li><Link to="/accueil" className="fr-btn fr-btn--secondary">Retour à mes outils</Link></li>
        </ul>
      </div>
    );
  }

  return (
    <div>
      <h1>Ajouter un outil</h1>
      <Stepper
        currentStep={index + 1}
        stepCount={steps.length}
        title={step}
        nextTitle={steps[index + 1]}
      />

      {step === "Définition" && (
        <>
          <RadioButtons
            legend="Catégorie"
            orientation="horizontal"
            options={TYPES.map((t) => ({
              label: t.label,
              hintText: t.hint,
              nativeInputProps: {
                name: "type",
                value: t.value,
                checked: form.type === t.value,
                onChange: set("type"),
              },
            }))}
          />
          <Input
            label="Nom"
            hintText={NAME_HINT}
            nativeInputProps={{ value: form.name, onChange: set("name"), required: true }}
            {...fieldState("name")}
          />
          <Input
            label="Description"
            hintText={form.type === "skill" ? "Obligatoire pour un skill" : "Facultative"}
            textArea
            nativeTextAreaProps={{ value: form.description, onChange: set("description"), rows: 3, required: form.type === "skill" }}
            {...fieldState("description")}
          />
          {form.type === "skill" && (
            <>
              <Input
                label="Tags"
                hintText="Séparés par des virgules, par exemple : recherche, web"
                nativeInputProps={{ value: form.tags, onChange: set("tags") }}
              />
              <Input
                label="Schéma d'entrée (JSON Schema)"
                hintText="Facultatif ; permet de tester le skill avec un formulaire"
                textArea
                nativeTextAreaProps={{ value: form.schema, onChange: set("schema"), rows: 6, spellCheck: false }}
                {...fieldState("schema")}
              />
            </>
          )}
          {hasNetworkAccess(form.type) && (
            <Input
              label={form.type === "mcp" ? "URL du serveur MCP" : "URL de l'API"}
              nativeInputProps={{ value: form.url, onChange: set("url"), type: "url", placeholder: "https://", required: true }}
              {...fieldState("url")}
            />
          )}
          {form.type === "api" && (
            <Input
              label="URL du Swagger / OpenAPI"
              hintText="Fichier JSON ou YAML décrivant les endpoints"
              nativeInputProps={{ value: form.openapiUrl, onChange: set("openapiUrl"), type: "url", placeholder: "https://…/openapi.json", required: true }}
              {...fieldState("openapiUrl")}
            />
          )}
        </>
      )}

      {step === "Authentification" && (
        <>
          <RadioButtons
            legend="Comment ToolMesh s'authentifie auprès de ce service"
            options={AUTH_MODES.map((m) => ({
              label: m.label,
              hintText: m.hint,
              nativeInputProps: {
                name: "authMode",
                value: m.value,
                checked: form.authMode === m.value,
                onChange: set("authMode"),
              },
            }))}
          />
          {form.authMode === "token_exchange" && (
            <Input
              label="Audience"
              hintText="Client Keycloak cible du token exchange"
              nativeInputProps={{ value: form.audience, onChange: set("audience"), required: true }}
              {...fieldState("audience")}
            />
          )}
        </>
      )}

      {step === "Endpoints" && (
        <EndpointRules form={form} set={set} />
      )}

      {step === "Outils" && (
        <ToolsEditor
          tools={form.tools}
          isApi={form.type === "api"}
          errors={showErrors ? errors.tools : undefined}
          onDiscover={async () => (await discoverTools(buildPayload({ ...form, tools: [] }))).map(draftFromDiscovered)}
          onChange={(tools) => setForm((f) => ({ ...f, tools }))}
        />
      )}

      {step === "Accès" && (
        <>
          <RadioButtons
            legend={form.type === "skill" ? "Qui peut utiliser ce skill" : "Qui peut utiliser cet outil"}
            options={ACCESS_SCOPES.map((s) => ({
              label: s.label,
              nativeInputProps: {
                name: "accessScope",
                value: s.value,
                checked: form.accessScope === s.value,
                onChange: set("accessScope"),
              },
            }))}
          />
          {form.accessScope === "role" && (
            <Input
              label="Rôle requis"
              hintText="Rôle du realm Keycloak, par exemple admin"
              nativeInputProps={{ value: form.accessRole, onChange: set("accessRole"), required: true }}
              {...fieldState("accessRole")}
            />
          )}
        </>
      )}

      {step === "Récapitulatif" && <Summary payload={buildPayload(form)} />}

      {submitError && (
        <Alert className="fr-mt-3w" severity="error" title="L'ajout a échoué" description={submitError} />
      )}

      <ul className="fr-btns-group fr-btns-group--inline-md fr-mt-4w">
        {index > 0 && (
          <li><Button priority="secondary" onClick={back} disabled={submitting}>Précédent</Button></li>
        )}
        <li>
          {index < steps.length - 1
            ? <Button onClick={next}>Suivant</Button>
            : <Button onClick={submit} disabled={submitting}>{submitting ? "Ajout en cours…" : "Ajouter l'outil"}</Button>}
        </li>
      </ul>
    </div>
  );
}

function EndpointRules({ form, set }) {
  const include = splitLines(form.includePatterns);
  const exclude = splitLines(form.excludePatterns);
  return (
    <>
      <p className="fr-text--sm">
        Chaque endpoint devient un outil. Les motifs s'appliquent à « MÉTHODE /chemin » ; <code>*</code> remplace
        n'importe quelle suite de caractères et <code>?</code> un seul caractère.
      </p>
      <Input
        label="Inclure"
        hintText="Un motif par ligne, par exemple GET /users*. Vide : tous les endpoints."
        textArea
        nativeTextAreaProps={{ value: form.includePatterns, onChange: set("includePatterns"), rows: 3 }}
      />
      <Input
        label="Exclure"
        hintText="Un motif par ligne, par exemple DELETE * ou */internal/*. L'exclusion l'emporte."
        textArea
        nativeTextAreaProps={{ value: form.excludePatterns, onChange: set("excludePatterns"), rows: 3 }}
      />
      <h2 className="fr-h6">Aperçu (endpoints simulés)</h2>
      <ul className="fr-raw-list" aria-live="polite">
        {MOCK_OPERATIONS.map((op) => {
          const exposed = isExposed(op, include, exclude);
          return (
            <li key={op} className="fr-mb-1v">
              <span className={`${exposed ? "fr-icon-checkbox-circle-fill" : "fr-icon-close-circle-line"} fr-icon--sm fr-mr-1w`} aria-hidden="true" />
              <code style={exposed ? undefined : { textDecoration: "line-through" }}>{op}</code>
              <span className="fr-sr-only">{exposed ? " : exposé" : " : exclu"}</span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

const AUTH_LABELS = Object.fromEntries(AUTH_MODES.map((m) => [m.value, m.label]));
const SCOPE_LABELS = Object.fromEntries(ACCESS_SCOPES.map((s) => [s.value, s.label]));

function Summary({ payload: p }) {
  const isSkill = p.type === "skill";
  const rows = [
    ["Catégorie", TYPES.find((t) => t.value === p.type).label],
    ["Nom", p.name],
    ["Description", p.description ?? "—"],
    ...(isSkill
      ? [["Tags", p.tags.length ? p.tags.join(", ") : "—"]]
      : [
          ["URL", p.url],
          ["Authentification", AUTH_LABELS[p.auth_mode] + (p.audience ? ` (audience ${p.audience})` : "")],
        ]),
    ...(p.openapi_url
      ? [
          ["Swagger", p.openapi_url],
          ["Endpoints inclus", p.endpoint_include.join(", ") || "tous"],
          ["Endpoints exclus", p.endpoint_exclude.join(", ") || "aucun"],
        ]
      : []),
    ...(isSkill ? [] : [["Outils", p.tools.length === 0 ? "Découverts à l'ajout" : p.tools.map((t) => (t.method ? `${t.method} ${t.path} → ${t.name}` : t.name)).join(", ")]]),
    ["Accès", p.required_role ? `Rôle requis : ${p.required_role}` : SCOPE_LABELS.all],
  ];
  return (
    <dl>
      {rows.map(([k, v]) => (
        <div key={k} className="fr-mb-2w">
          <dt className="fr-text--bold">{k}</dt>
          <dd className="fr-ml-0">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
