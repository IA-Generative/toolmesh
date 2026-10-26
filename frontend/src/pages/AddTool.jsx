import { useState } from "react";
import { Link } from "react-router";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Input from "@codegouvfr/react-dsfr/Input";
import RadioButtons from "@codegouvfr/react-dsfr/RadioButtons";
import Stepper from "@codegouvfr/react-dsfr/Stepper";
import { MOCK_OPERATIONS, isExposed, splitLines } from "../tools/endpoints";

const TYPES = [
  { value: "mcp", label: "Serveur MCP", hint: "Serveur exposant des outils via le protocole MCP" },
  { value: "api", label: "API", hint: "API HTTP existante" },
  { value: "skill", label: "Skill", hint: "Compétence réutilisable (pas d'appel réseau)" },
];

const AUTH_MODES = [
  { value: "token_exchange", label: "Token exchange", hint: "Le jeton de l'utilisateur est échangé contre un jeton pour ce service" },
  { value: "static_token", label: "Token statique", hint: "Un jeton unique partagé, stocké côté ToolMesh" },
  { value: "none", label: "Sans identifiants", hint: "Le service est appelé sans authentification" },
];

const ACCESS_SCOPES = [
  { value: "all", label: "Tous les utilisateurs connectés" },
  { value: "groups", label: "Des groupes Keycloak" },
  { value: "users", label: "Des utilisateurs précis" },
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
  staticToken: "",
  accessScope: "all",
  accessList: "",
};

const splitList = (s) => s.split(",").map((v) => v.trim()).filter(Boolean);

// Un skill n'est pas appelé par le réseau : il n'a ni URL ni mode d'authentification.
const hasNetworkAccess = (type) => type !== "skill";

function stepsFor(type) {
  if (type === "api") return ["Définition", "Authentification", "Endpoints", "Accès", "Récapitulatif"];
  if (type === "mcp") return ["Définition", "Authentification", "Accès", "Récapitulatif"];
  return ["Définition", "Accès", "Récapitulatif"];
}

function errorsFor(step, f) {
  const e = {};
  if (step === "Définition") {
    if (!f.name.trim()) e.name = "Le nom est obligatoire.";
    if (f.type === "skill" && !f.description.trim()) e.description = "La description est obligatoire pour un skill.";
    if (f.type === "mcp" && !f.url.trim()) e.url = "L'URL est obligatoire.";
    if (f.type === "api" && !f.url.trim()) e.url = "L'URL est obligatoire.";
    if (f.type === "api" && !f.openapiUrl.trim()) e.openapiUrl = "L'URL du Swagger est obligatoire.";
  }
  if (step === "Authentification") {
    if (f.authMode === "token_exchange" && !f.audience.trim()) e.audience = "L'audience est obligatoire.";
    if (f.authMode === "static_token" && !f.staticToken.trim()) e.staticToken = "Le jeton est obligatoire.";
  }
  if (step === "Accès" && f.accessScope !== "all" && splitList(f.accessList).length === 0) {
    e.accessList = "Renseignez au moins une valeur.";
  }
  return e;
}

function buildPayload(f) {
  const network = hasNetworkAccess(f.type);
  return {
    name: f.name.trim(),
    description: f.description.trim() || null,
    type: f.type,
    tags: splitList(f.tags),
    url: network ? f.url.trim() : null,
    openapi_url: f.type === "api" ? f.openapiUrl.trim() : null,
    endpoints:
      f.type === "api"
        ? { include: splitLines(f.includePatterns), exclude: splitLines(f.excludePatterns) }
        : null,
    auth: network
      ? {
          mode: f.authMode,
          audience: f.authMode === "token_exchange" ? f.audience.trim() : null,
          token: f.authMode === "static_token" ? f.staticToken : null,
        }
      : null,
    access: { scope: f.accessScope, values: f.accessScope === "all" ? [] : splitList(f.accessList) },
  };
}

export default function AddTool() {
  const [form, setForm] = useState(INITIAL);
  const [index, setIndex] = useState(0);
  const [showErrors, setShowErrors] = useState(false);
  const [submitted, setSubmitted] = useState(null);

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
  const submit = () => setSubmitted(buildPayload(form));

  if (submitted) {
    return (
      <div>
        <h1>Ajouter un outil</h1>
        <Alert
          severity="info"
          title="Formulaire complet"
          description="L'enregistrement n'est pas encore branché sur le backend : voici la définition qui sera envoyée."
        />
        <pre className="fr-mt-3w"><code>{JSON.stringify({ ...submitted, auth: submitted.auth && { ...submitted.auth, token: submitted.auth.token && "••••••" } }, null, 2)}</code></pre>
        <Link to="/accueil" className="fr-btn fr-mt-2w">Retour à mes outils</Link>
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
          <Input label="Nom" nativeInputProps={{ value: form.name, onChange: set("name"), required: true }} {...fieldState("name")} />
          <Input
            label="Description"
            hintText={form.type === "skill" ? "Obligatoire pour un skill" : "Facultative"}
            textArea
            nativeTextAreaProps={{ value: form.description, onChange: set("description"), rows: 3, required: form.type === "skill" }}
            {...fieldState("description")}
          />
          <Input
            label="Tags"
            hintText="Séparés par des virgules, par exemple : recherche, web"
            nativeInputProps={{ value: form.tags, onChange: set("tags") }}
          />
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
          {form.authMode === "static_token" && (
            <Input
              label="Jeton"
              nativeInputProps={{ value: form.staticToken, onChange: set("staticToken"), type: "password", autoComplete: "off", required: true }}
              {...fieldState("staticToken")}
            />
          )}
        </>
      )}

      {step === "Endpoints" && (
        <EndpointRules form={form} set={set} />
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
          {form.accessScope !== "all" && (
            <Input
              label={form.accessScope === "groups" ? "Groupes Keycloak" : "Utilisateurs"}
              hintText={
                form.accessScope === "groups"
                  ? "Noms des groupes, séparés par des virgules"
                  : "Identifiants des utilisateurs, séparés par des virgules"
              }
              nativeInputProps={{ value: form.accessList, onChange: set("accessList"), required: true }}
              {...fieldState("accessList")}
            />
          )}
        </>
      )}

      {step === "Récapitulatif" && <Summary payload={buildPayload(form)} />}

      <ul className="fr-btns-group fr-btns-group--inline-md fr-mt-4w">
        {index > 0 && (
          <li><Button priority="secondary" onClick={back}>Précédent</Button></li>
        )}
        <li>
          {index < steps.length - 1
            ? <Button onClick={next}>Suivant</Button>
            : <Button onClick={submit}>Ajouter l'outil</Button>}
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
  const rows = [
    ["Catégorie", TYPES.find((t) => t.value === p.type).label],
    ["Nom", p.name],
    ["Description", p.description ?? "—"],
    ["Tags", p.tags.length ? p.tags.join(", ") : "—"],
    ...(p.auth
      ? [
          ["URL", p.url],
          ["Authentification", AUTH_LABELS[p.auth.mode] + (p.auth.audience ? ` (audience ${p.auth.audience})` : "")],
        ]
      : []),
    ...(p.endpoints
      ? [
          ["Swagger", p.openapi_url],
          ["Endpoints inclus", p.endpoints.include.join(", ") || "tous"],
          ["Endpoints exclus", p.endpoints.exclude.join(", ") || "aucun"],
        ]
      : []),
    ["Accès", SCOPE_LABELS[p.access.scope] + (p.access.values.length ? ` : ${p.access.values.join(", ")}` : "")],
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
