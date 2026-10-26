import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import Alert from "@codegouvfr/react-dsfr/Alert";
import { useAuth } from "../auth/AuthContext";
import { fetchMyTools, searchTools, sendClick } from "../auth/api";

import { TYPE_LABELS } from "../tools/types";
import SearchFeedback from "../tools/SearchFeedback";
import ToolCard, { FilterTag } from "../tools/ToolCard";


const MODE_HINTS = {
  hybrid: "Résultats classés par pertinence (mots-clés et sens).",
  keyword: "Résultats classés par pertinence (mots-clés).",
  basic: "Résultats par mots-clés.",
};

export default function Home() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [tools, setTools] = useState(null);
  const [error, setError] = useState(null);
  const [found, setFound] = useState(null); // { key, tools, mode } : réponse de la recherche pour la clé `key`
  const rawQuery = (params.get("q") ?? "").trim();
  const activeTags = params.getAll("tag");
  const activeType = params.get("type");
  const activeVersion = params.get("version");
  const searchKey = JSON.stringify([rawQuery, activeType, activeTags, activeVersion]);

  useEffect(() => {
    fetchMyTools().then((d) => setTools(d.tools)).catch((e) => setError(e.message));
  }, []);

  // Avec une requête, le backend classe les outils par pertinence ; sans requête, les filtres suffisent côté client.
  useEffect(() => {
    if (!rawQuery) return;
    let current = true;
    searchTools({ q: rawQuery, type: activeType, tags: activeTags, version: activeVersion })
      .then((r) => current && setFound({ key: searchKey, tools: r.tools, mode: r.mode, searchId: r.search_id }))
      .catch((e) => current && setError(e.message));
    return () => {
      current = false;
    };
    // `searchKey` résume toutes les entrées de la recherche.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey]);

  const allTags = useMemo(
    () => [...new Set((tools ?? []).flatMap((t) => t.tags ?? []))].sort((a, b) => a.localeCompare(b, "fr")),
    [tools],
  );
  const allTypes = useMemo(() => [...new Set((tools ?? []).map((t) => t.type))], [tools]);
  const allVersions = useMemo(
    () => [...new Set((tools ?? []).map((t) => t.source_version).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr", { numeric: true })),
    [tools],
  );

  const update = (mutate) => {
    const next = new URLSearchParams(params);
    mutate(next);
    setParams(next, { replace: true });
  };
  const toggleTag = (tag) =>
    update((p) => {
      const next = activeTags.includes(tag) ? activeTags.filter((t) => t !== tag) : [...activeTags, tag];
      p.delete("tag");
      next.forEach((t) => p.append("tag", t));
    });
  const toggleType = (type) =>
    update((p) => (activeType === type ? p.delete("type") : p.set("type", type)));
  const toggleVersion = (version) =>
    update((p) => (activeVersion === version ? p.delete("version") : p.set("version", version)));
  const reset = () => update((p) => { p.delete("tag"); p.delete("type"); p.delete("version"); });

  const searching = Boolean(rawQuery);
  const results = found?.key === searchKey ? found : null;
  const visible = searching
    ? results?.tools
    : tools?.filter(
        (t) =>
          (!activeType || t.type === activeType) &&
          (!activeVersion || t.source_version === activeVersion) &&
          activeTags.every((tag) => (t.tags ?? []).includes(tag)),
      );
  const filtered = Boolean(rawQuery || activeType || activeVersion || activeTags.length);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
        <h1 className="fr-mb-0">Mes outils</h1>
        <Link to="/outils/nouveau" className="fr-btn fr-icon-add-line fr-btn--icon-left">
          Ajouter un outil
        </Link>
      </div>
      <p className="fr-text--lead fr-mt-2w">Bonjour {user.username}, voici les outils auxquels vous avez accès.</p>

      {error && <Alert severity="error" title="Impossible de charger vos outils" description={error} />}
      {!tools && !error && <p role="status">Chargement…</p>}
      {tools?.length === 0 && (
        <Alert severity="info" title="Aucun outil disponible" description="Votre compte n'a accès à aucun outil pour le moment." />
      )}

      {tools?.length > 0 && (
        <>
          <section aria-label="Filtres" className="fr-mb-3w">
            <p className="fr-text--sm fr-text--bold fr-mb-1w" id="filtre-type">Type</p>
            <ul className="fr-tags-group" aria-labelledby="filtre-type">
              {allTypes.map((type) => (
                <li key={type}>
                  <FilterTag label={TYPE_LABELS[type] ?? type} pressed={activeType === type} onClick={() => toggleType(type)} />
                </li>
              ))}
            </ul>
            {allVersions.length > 0 && (
              <>
                <p className="fr-text--sm fr-text--bold fr-mb-1w fr-mt-2w" id="filtre-version">Version</p>
                <ul className="fr-tags-group" aria-labelledby="filtre-version">
                  {allVersions.map((v) => (
                    <li key={v}>
                      <FilterTag label={v} pressed={activeVersion === v} onClick={() => toggleVersion(v)} />
                    </li>
                  ))}
                </ul>
              </>
            )}
            {allTags.length > 0 && (
              <>
                <p className="fr-text--sm fr-text--bold fr-mb-1w fr-mt-2w" id="filtre-tags">Tags</p>
                <ul className="fr-tags-group" aria-labelledby="filtre-tags">
                  {allTags.map((tag) => (
                    <li key={tag}>
                      <FilterTag label={tag} pressed={activeTags.includes(tag)} onClick={() => toggleTag(tag)} />
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="fr-mt-2w" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <p className="fr-text--sm fr-mb-0" role="status">
                {visible
                  ? `${visible.length} outil${visible.length > 1 ? "s" : ""} sur ${tools.length}`
                  : "Recherche en cours…"}
                {searching && results && MODE_HINTS[results.mode] ? `. ${MODE_HINTS[results.mode]}` : ""}
              </p>
              {filtered && (
                <button type="button" className="fr-btn fr-btn--tertiary-no-outline fr-btn--sm" onClick={reset}>
                  Réinitialiser les filtres
                </button>
              )}
            </div>
          </section>

          {results?.searchId && (
            <SearchFeedback key={results.searchId} searchId={results.searchId} results={results.tools} allTools={tools} />
          )}

          {visible?.length === 0 && (
            <Alert severity="info" title="Aucun résultat" description="Aucun outil ne correspond à votre recherche ou à vos filtres." />
          )}
        </>
      )}

      {visible?.length > 0 && (
        <ul className="fr-grid-row fr-grid-row--gutters fr-raw-list">
          {visible.map((t, i) => (
            <li key={t.name} className="fr-col-12 fr-col-md-6 fr-col-lg-4">
              <ToolCard
                tool={t}
                to={`/outils/${encodeURIComponent(t.name)}`}
                activeTags={activeTags}
                onTag={toggleTag}
                onOpen={results?.searchId ? () => sendClick(results.searchId, t.name, i + 1) : undefined}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
