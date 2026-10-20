import { Footer } from "@codegouvfr/react-dsfr/Footer";

export default function AppFooter() {
  return (
    <Footer
      brandTop={<>Ministère<br />de l'Intérieur</>}
      homeLinkProps={{ href: "/", title: "Accueil - toolmesh" }}
      contentDescription="ToolMesh : passerelle d'outils pour agents IA."
      accessibility="non compliant"
      termsLinkProps={{ href: "/mentions-legales" }}
    />
  );
}
