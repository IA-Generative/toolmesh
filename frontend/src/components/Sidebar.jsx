import { Link, NavLink } from "react-router";
import UserMenu from "./UserMenu";
import { searchModalJS } from "./searchModalJS";
import useAppVersion from "./useAppVersion";
import { clearHistory, timeAgo, useHistory } from "../tools/history";
import { TYPE_ICONS } from "../tools/types";

export default function Sidebar({ id, open, onNavigate }) {
  const version = useAppVersion();
  const history = useHistory();

  return (
    <aside
      id={id}
      tabIndex={-1}
      aria-label="Barre latérale"
      className={`app-sidebar${open ? " app-sidebar--open" : ""}`}
    >
      <Link to="/accueil" className="app-sidebar__brand" onClick={onNavigate}>
        <p className="fr-logo">Ministère<br />de l'Intérieur</p>
        <span className="app-sidebar__name">ToolMesh</span>
        <span className="fr-sr-only">, accueil</span>
      </Link>

      <nav aria-label="Navigation principale">
        <ul className="app-sidebar__list">
          <li>
            <button type="button" className="app-sidebar__link" {...searchModalJS.buttonProps}>
              <span className="fr-icon-search-line fr-icon--sm" aria-hidden="true" />
              Rechercher
            </button>
          </li>
          <li>
            <NavLink to="/accueil" end className="app-sidebar__link" onClick={onNavigate}>
              <span className="fr-icon-home-4-line fr-icon--sm" aria-hidden="true" />
              Accueil
            </NavLink>
          </li>
          {/* futurs onglets : une <li><NavLink …> par page */}
        </ul>
      </nav>

      <section className="app-sidebar__history" aria-labelledby="historique-titre">
        <div className="app-sidebar__history-head">
          <h2 id="historique-titre" className="fr-text--xs fr-text--bold fr-mb-0">Historique des tests</h2>
          {history.length > 0 && (
            <button type="button" className="app-sidebar__clear" onClick={clearHistory}>Effacer</button>
          )}
        </div>
        {history.length === 0 ? (
          <p className="fr-text--sm fr-mb-0">Aucun test pour le moment.</p>
        ) : (
          <ul className="app-sidebar__list">
            {history.map((h) => (
              <li key={h.id}>
                <Link
                  to={`/outils/${encodeURIComponent(h.tool)}?replay=${h.id}`}
                  className="app-sidebar__link app-sidebar__entry"
                  onClick={onNavigate}
                >
                  <span className={`${TYPE_ICONS[h.type] ?? "fr-icon-settings-5-line"} fr-icon--sm`} aria-hidden="true" />
                  <span className="app-sidebar__entry-text">
                    <span className="app-sidebar__entry-name">{h.tool}</span>
                    <span className="app-sidebar__entry-meta">{timeAgo(h.at)} · {h.ms} ms{h.ok === false ? " · échec" : ""}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <UserMenu />

      <ul className="app-sidebar__legal fr-text--xs">
        <li><Link to="/mentions-legales" onClick={onNavigate}>Mentions légales</Link></li>
        <li>Accessibilité : non conforme</li>
        {version && <li>Version {version}</li>}
      </ul>
    </aside>
  );
}
