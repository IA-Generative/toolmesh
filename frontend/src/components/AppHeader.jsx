import { Header } from "@codegouvfr/react-dsfr/Header";
import { headerFooterDisplayItem } from "@codegouvfr/react-dsfr/Display";
import { useAuth } from "../auth/AuthContext";
import { useLocation } from "react-router"

export default function AppHeader() {
  const { status, loginUrl, logout } = useAuth();
  const { pathname } = useLocation();


  const navigation =
    status === "authenticated"
      ? [{ text: "Accueil", linkProps: { href: "/accueil" }, isActive: pathname === "/accueil" }]
      : [];

  const authItems =
    status === "authenticated"
      ? [{ iconId: "fr-icon-logout-box-r-line", text: "Se déconnecter", buttonProps: { onClick: logout } }]
      : status === "anonymous"
        ? [{ iconId: "fr-icon-user-fill", text: "Se connecter", linkProps: { href: loginUrl() } }]
        : [];

  return (
    <Header
      brandTop={<>Ministère<br />de l'Intérieur</>}
      homeLinkProps={{ href: "/", title: "Accueil - ToolMesh" }}
      serviceTitle="ToolMesh"
      navigation={navigation}
      quickAccessItems={[headerFooterDisplayItem, ...authItems]}
    />
  );
}

