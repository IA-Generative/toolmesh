import Button from "@codegouvfr/react-dsfr/Button";
import { headerFooterDisplayItem } from "@codegouvfr/react-dsfr/Display";
import { useAuth } from "../auth/AuthContext";

export default function Topbar({ menuOpen, onMenuToggle }) {
  const { logout } = useAuth();

  return (
    <header className="app-topbar" role="banner">
      <Button
        className="app-topbar__burger"
        iconId="fr-icon-menu-fill"
        priority="tertiary no outline"
        title="Menu"
        nativeButtonProps={{ "aria-expanded": menuOpen, "aria-controls": "navigation", onClick: onMenuToggle }}
      />
      <div className="app-topbar__actions">
        <Button
          iconId="fr-icon-theme-fill"
          priority="tertiary no outline"
          nativeButtonProps={headerFooterDisplayItem.buttonProps}
        >
          Paramètres d'affichage
        </Button>
        <Button iconId="fr-icon-logout-box-r-line" priority="tertiary no outline" onClick={logout}>
          Se déconnecter
        </Button>
      </div>
    </header>
  );
}
