// Opérations simulées d'un Swagger, en attendant la lecture réelle de la spec.
export const MOCK_OPERATIONS = [
  "GET /users",
  "GET /users/{id}",
  "POST /users",
  "DELETE /users/{id}",
  "GET /orders",
  "POST /orders",
  "GET /orders/{id}/items",
  "DELETE /orders/{id}",
  "GET /health",
  "GET /internal/metrics",
];

export const splitLines = (s) => s.split("\n").map((l) => l.trim()).filter(Boolean);

// Joker `*` (n'importe quels caractères, `/` compris) et `?` (un caractère), appliqués à "METHODE /chemin".
export function matchesPattern(pattern, operation) {
  const source = pattern
    .toUpperCase()
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${source}$`).test(operation.toUpperCase());
}

// Inclus si aucun motif d'inclusion n'est défini ou si l'un correspond, et qu'aucun motif d'exclusion ne correspond.
export function isExposed(operation, include, exclude) {
  const included = include.length === 0 || include.some((p) => matchesPattern(p, operation));
  return included && !exclude.some((p) => matchesPattern(p, operation));
}
