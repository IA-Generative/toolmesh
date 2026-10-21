import { Header } from "@codegouvfr/react-dsfr/Header";
import { headerFooterDisplayItem } from "@codegouvfr/react-dsfr/Display";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { status, loginUrl, logout } = useAuth();

  const authItems =
    status === "authenticated"
      ? [{ iconId: "fr-icon-logout-box-r-line", text: "Se déconnecter", buttonProps: { onClick: logout } }]
      : status === "anonymous"
        ? [{ iconId: "fr-icon-user-fill", text: "Se connecter", linkProps: { href: loginUrl(), reloadDocument: true } }]
        : [];

  return (
    <Header
      brandTop={<>Ministère<br />de l'Intérieur</>}
      homeLinkProps={{ href: "/", title: "Accueil - ToolMesh" }}
      serviceTitle="ToolMesh"
      quickAccessItems={[headerFooterDisplayItem, ...authItems]}
    />
  );
}
