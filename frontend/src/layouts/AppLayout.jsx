import { useEffect, useState } from "react";
import { Outlet } from "react-router";
import { Display } from "@codegouvfr/react-dsfr/Display/Display";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import SearchModal from "../components/SearchModal";
import "./AppLayout.css";

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="app-shell">
      <div className="fr-skiplinks">
        <nav className="fr-container" role="navigation" aria-label="Accès rapide">
          <ul className="fr-skiplinks__list">
            <li><a className="fr-link" href="#contenu">Contenu</a></li>
            <li><a className="fr-link" href="#navigation">Menu</a></li>
          </ul>
        </nav>
      </div>

      <Sidebar id="navigation" open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && (
        <div className="app-shell__scrim" onClick={() => setMenuOpen(false)} aria-hidden="true" />
      )}

      <div className="app-shell__main">
        <Topbar menuOpen={menuOpen} onMenuToggle={() => setMenuOpen((o) => !o)} />
        <main id="contenu" className="app-shell__content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      <Display />      {/* fenêtre « Paramètres d'affichage » : d'ordinaire rendue par le Header DSFR */}
      <SearchModal />
    </div>
  );
}
