import { useSyncExternalStore } from "react";

// Historique des tests de l'utilisateur, gardé dans le navigateur en attendant le backend.
const KEY = "toolmesh.testHistory";
const MAX = 15;

let entries = load();
const listeners = new Set();

function load() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY));
    // Les entrées d'avant les ids (sans `toolId`) ne mènent plus à un outil : on les oublie.
    return Array.isArray(parsed) ? parsed.filter((e) => e.toolId) : [];
  } catch {
    return [];
  }
}

function commit(next) {
  entries = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // Stockage indisponible : l'historique reste en mémoire pour la session.
  }
  listeners.forEach((l) => l());
}

const newId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;

// entry : { toolId, tool (nom), type, args, model?, ok, ms }
export function addHistory(entry) {
  commit([{ ...entry, id: newId(), at: Date.now() }, ...entries].slice(0, MAX));
}

export const clearHistory = () => commit([]);
export const getHistoryEntry = (id) => entries.find((e) => e.id === id) ?? null;

const subscribe = (l) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export const useHistory = () => useSyncExternalStore(subscribe, () => entries);

const rtf = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });
export function timeAgo(at) {
  const s = Math.round((at - Date.now()) / 1000);
  if (Math.abs(s) < 60) return "à l'instant";
  if (Math.abs(s) < 3600) return rtf.format(Math.round(s / 60), "minute");
  if (Math.abs(s) < 86400) return rtf.format(Math.round(s / 3600), "hour");
  return rtf.format(Math.round(s / 86400), "day");
}
