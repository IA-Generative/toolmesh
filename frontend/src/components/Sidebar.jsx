import { Link, NavLink } from "react-router";
import UserMenu from "./UserMenu";
import { searchModalJS } from "./searchModalJS";

export default function Sidebar({ id, open, onNavigate }) {
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
        <h2 id="historique-titre" className="fr-text--xs fr-text--bold fr-mb-1w">Historique</h2>
        <p className="fr-text--sm fr-mb-0">Aucun historique pour le moment.</p>
      </section>

      <UserMenu />

      <ul className="app-sidebar__legal fr-text--xs">
        <li><Link to="/mentions-legales" onClick={onNavigate}>Mentions légales</Link></li>
        <li>Accessibilité : non conforme</li>
      </ul>
    </aside>
  );
}
