// Modèles proposés pour tester un skill. Liste simulée, elle viendra du backend.
export const MODELS = [
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5" },
  { id: "claude-opus-5-5", label: "Claude Opus 5.5" },
  { id: "claude-haiku-5-5", label: "Claude Haiku 5.5" },
];
export const DEFAULT_MODEL = MODELS[0].id;
export const modelLabel = (id) => MODELS.find((m) => m.id === id)?.label ?? id;
