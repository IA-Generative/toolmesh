// Utilitaires JSON Schema -> formulaire. Gère les propriétés de premier niveau d'un schéma "object" ;
// les types non scalaires (objet, tableau d'objets…) sont édités en JSON.

export const propertiesOf = (schema) => Object.entries(schema?.properties ?? {});
export const isRequired = (schema, key) => (schema?.required ?? []).includes(key);

export function kindOf(prop) {
  if (prop.enum) return "enum";
  if (prop.type === "boolean") return "boolean";
  if (prop.type === "integer" || prop.type === "number") return "number";
  if (prop.type === "array" && ["string", "integer", "number"].includes(prop.items?.type)) return "list";
  if (prop.type === "string" || prop.type === undefined) return "string";
  return "json";
}

const toText = (kind, v) => {
  if (v === undefined || v === null) return "";
  if (kind === "list") return v.join("\n");
  if (kind === "json") return JSON.stringify(v, null, 2);
  return String(v);
};

// Valeurs du formulaire (toujours des chaînes, sauf les booléens) à partir de arguments.
export function toFormValues(schema, args = {}) {
  return Object.fromEntries(
    propertiesOf(schema).map(([key, prop]) => {
      const kind = kindOf(prop);
      const v = args[key] ?? prop.default;
      return [key, kind === "boolean" ? Boolean(v) : toText(kind, v)];
    }),
  );
}

// Arguments typés à partir des valeurs du formulaire ; renvoie { args, errors }.
export function toArguments(schema, values) {
  const args = {};
  const errors = {};
  for (const [key, prop] of propertiesOf(schema)) {
    const kind = kindOf(prop);
    const raw = values[key];
    const empty = kind === "boolean" ? false : String(raw ?? "").trim() === "";

    if (kind === "boolean") {
      args[key] = Boolean(raw);
      continue;
    }
    if (empty) {
      if (isRequired(schema, key)) errors[key] = "Ce champ est obligatoire.";
      continue;
    }
    if (kind === "number") {
      const n = Number(raw);
      if (Number.isNaN(n) || (prop.type === "integer" && !Number.isInteger(n))) errors[key] = prop.type === "integer" ? "Entier attendu." : "Nombre attendu.";
      else if (prop.minimum !== undefined && n < prop.minimum) errors[key] = `Minimum : ${prop.minimum}.`;
      else if (prop.maximum !== undefined && n > prop.maximum) errors[key] = `Maximum : ${prop.maximum}.`;
      else args[key] = n;
    } else if (kind === "list") {
      const items = String(raw).split("\n").map((l) => l.trim()).filter(Boolean);
      const typed = items.map((i) => (prop.items.type === "string" ? i : Number(i)));
      if (typed.some((i) => typeof i === "number" && Number.isNaN(i))) errors[key] = "Une valeur n'est pas un nombre.";
      else args[key] = typed;
    } else if (kind === "json") {
      try {
        args[key] = JSON.parse(raw);
      } catch {
        errors[key] = "JSON invalide.";
      }
    } else {
      const s = String(raw);
      if (prop.maxLength !== undefined && s.length > prop.maxLength) errors[key] = `${prop.maxLength} caractères maximum.`;
      else if (prop.minLength !== undefined && s.length < prop.minLength) errors[key] = `${prop.minLength} caractères minimum.`;
      else args[key] = s;
    }
  }
  return { args, errors };
}

// Vérifie un JSON saisi à la main : propriétés obligatoires et types simples.
export function validateArguments(schema, args) {
  if (args === null || typeof args !== "object" || Array.isArray(args)) return ["Un objet JSON est attendu."];
  const errors = (schema?.required ?? []).filter((k) => args[k] === undefined).map((k) => `« ${k} » est obligatoire.`);
  for (const [key, prop] of propertiesOf(schema)) {
    if (args[key] === undefined) continue;
    const kind = kindOf(prop);
    const v = args[key];
    const ok = {
      boolean: typeof v === "boolean",
      number: typeof v === "number",
      list: Array.isArray(v),
      enum: prop.enum?.includes(v),
      string: typeof v === "string",
      json: true,
    }[kind];
    if (!ok) errors.push(`« ${key} » n'a pas le type attendu.`);
  }
  return errors;
}
