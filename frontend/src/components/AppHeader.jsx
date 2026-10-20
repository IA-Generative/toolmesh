import { Header } from "@codegouvfr/react-dsfr/Header";
import { headerFooterDisplayItem } from "@codegouvfr/react-dsfr/Display";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { status, user, loginUrl, logout } = useAuth();

  const authItems =
    status === "authenticated"
      ? [
          { iconId: "fr-icon-account-circle-fill", text: user.username, linkProps: { href: "#" } },
          { iconId: "fr-icon-logout-box-r-line", text: "Se déconnecter", buttonProps: { onClick: logout } },
        ]
      : status === "anonymous"
        ? [{ iconId: "fr-icon-user-fill", text: "Se connecter", linkProps: { href: loginUrl() } }]
        : []; // "loading" : rien, pour éviter le flash « Se connecter »

  return (
    <Header
      brandTop={<>Ministère<br />de l'Intérieur</>}
      homeLinkProps={{ href: "/", title: "Accueil - ToolMesh" }}
      serviceTitle="ToolMesh"
      quickAccessItems={[headerFooterDisplayItem, ...authItems]}
    />
  );
}

