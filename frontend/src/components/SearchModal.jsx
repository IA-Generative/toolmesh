import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import SearchBar from "@codegouvfr/react-dsfr/SearchBar";
import { fetchMyTools } from "../auth/api";
import { FilterTag } from "../tools/ToolCard";
import { TYPE_LABELS } from "../tools/types";
import { searchModalJS } from "./searchModalJS";

export default function SearchModal() {
  const navigate = useNavigate();
  const [tools, setTools] = useState([]);
  const [type, setType] = useState(null);
  const [tags, setTags] = useState([]);

  useEffect(() => {
    fetchMyTools().then((d) => setTools(d.tools)).catch(() => {
      // Sans la liste, la recherche texte reste utilisable, seulement sans filtres.
    });
  }, []);

  const types = useMemo(() => Object.keys(TYPE_LABELS).filter((t) => tools.some((x) => x.type === t)), [tools]);
  const allTags = useMemo(
    () => [...new Set(tools.flatMap((t) => t.tags ?? []))].sort((a, b) => a.localeCompare(b, "fr")),
    [tools],
  );

  const toggleTag = (tag) => setTags((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]));

  const onSearch = (text) => {
    searchModalJS.close();
    const params = new URLSearchParams();
    if (text) params.set("q", text);
    if (type) params.set("type", type);
    tags.forEach((t) => params.append("tag", t));
    const qs = params.toString();
    navigate(qs ? `/accueil?${qs}` : "/accueil");
  };

  return (
    <searchModalJS.Component title="Rechercher un outil" titleAs="h2" topAnchor>
      <SearchBar label="Rechercher un outil" big allowEmptySearch onButtonClick={onSearch} />

      {types.length > 0 && (
        <>
          <p className="fr-text--sm fr-text--bold fr-mt-3w fr-mb-1w" id="recherche-type">Type</p>
          <ul className="fr-tags-group" aria-labelledby="recherche-type">
            {types.map((t) => (
              <li key={t}>
                <FilterTag label={TYPE_LABELS[t]} pressed={type === t} onClick={() => setType((cur) => (cur === t ? null : t))} />
              </li>
            ))}
          </ul>
        </>
      )}

      {allTags.length > 0 && (
        <>
          <p className="fr-text--sm fr-text--bold fr-mt-2w fr-mb-1w" id="recherche-tags">Tags</p>
          <ul className="fr-tags-group" aria-labelledby="recherche-tags">
            {allTags.map((tag) => (
              <li key={tag}>
                <FilterTag label={tag} pressed={tags.includes(tag)} onClick={() => toggleTag(tag)} />
              </li>
            ))}
          </ul>
        </>
      )}
    </searchModalJS.Component>
  );
}
