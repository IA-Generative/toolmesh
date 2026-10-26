export const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];
export const NAME_RE = /^[A-Za-z0-9_.:-]{1,100}$/;
export const NAME_HINT = "Lettres, chiffres, _ . : - uniquement (100 caractères max).";

let nextId = 1;
export const emptyTool = () => ({ id: nextId++, name: "", description: "", tags: "", method: "GET", path: "", schema: "" });

// Brouillon d'un outil renvoyé par la découverte (affiché en ligne compacte).
export const draftFromDiscovered = (t) => ({
  id: nextId++,
  discovered: true,
  name: t.name,
  description: t.description ?? "",
  tags: (t.tags ?? []).join(", "),
  method: t.method ?? "GET",
  path: t.path ?? "",
  schema: t.input_schema ? JSON.stringify(t.input_schema) : "",
});

export function parseSchema(text) {
  if (!text.trim()) return { value: null };
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== "object" || Array.isArray(value)) return { error: "Un objet JSON est attendu." };
    return { value };
  } catch {
    return { error: "JSON invalide." };
  }
}

// Erreurs par outil : tableau parallèle à `tools`, vide si tout est valide.
export function toolErrors(tools, isApi) {
  const names = new Map();
  return tools.map((t) => {
    const e = {};
    const name = t.name.trim();
    if (!name) e.name = "Le nom est obligatoire.";
    else if (!NAME_RE.test(name)) e.name = NAME_HINT;
    else if (names.has(name)) e.name = "Ce nom est déjà utilisé plus haut.";
    names.set(name, true);
    if (isApi && !t.path.trim().startsWith("/")) e.path = "Le chemin doit commencer par « / ».";
    const schema = parseSchema(t.schema);
    if (schema.error) e.schema = schema.error;
    return e;
  });
}
