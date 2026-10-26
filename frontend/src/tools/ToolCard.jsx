import { Link } from "react-router";
import Badge from "@codegouvfr/react-dsfr/Badge";
import { TYPE_ICONS, TYPE_LABELS } from "./types";

export function FilterTag({ label, pressed, onClick }) {
  return (
    <button type="button" className="fr-tag" aria-pressed={pressed} onClick={onClick}>
      {label}
    </button>
  );
}

// Carte d'un outil. Avec `to`, toute la carte est un lien ; avec `onTag`, les tags sont des boutons de filtre.
export default function ToolCard({ tool, to, activeTags = [], onTag, titleAs: Title = "h2" }) {
  const tags = tool.tags ?? [];
  const label = (
    <>
      <span className={`${TYPE_ICONS[tool.type] ?? "fr-icon-settings-5-line"} fr-icon--sm fr-mr-1w`} aria-hidden="true" />
      {tool.name}
    </>
  );
  return (
    <div className={`fr-card${to ? " fr-enlarge-link" : ""}`}>
      <div className="fr-card__body">
        <div className="fr-card__content">
          <Title className="fr-card__title">
            {to ? <Link to={to} className="fr-card__link">{label}</Link> : label}
          </Title>
          <p className="fr-card__desc">{tool.description}</p>
          <div className="fr-card__start">
            <ul className="fr-badges-group">
              <li><Badge as="span" small severity="info" noIcon>{TYPE_LABELS[tool.type] ?? tool.type}</Badge></li>
              {tool.required_role && <li><Badge as="span" small noIcon>Rôle : {tool.required_role}</Badge></li>}
            </ul>
          </div>
          <p className="fr-card__detail fr-icon-links-line">Source : {tool.source}{tool.source_version ? ` · ${tool.source_version}` : ""}</p>
          {tool.method && tool.path && <p className="fr-card__detail"><code>{tool.method} {tool.path}</code></p>}
        </div>
        {tags.length > 0 && (
          <div className="fr-card__footer">
            <ul className="fr-tags-group">
              {tags.map((tag) => (
                <li key={tag}>
                  {onTag
                    ? <FilterTag label={tag} pressed={activeTags.includes(tag)} onClick={() => onTag(tag)} />
                    : <span className="fr-tag">{tag}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
