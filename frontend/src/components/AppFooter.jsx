import { Footer } from "@codegouvfr/react-dsfr/Footer";
import useAppVersion from "./useAppVersion";

export default function AppFooter() {
  const version = useAppVersion()
  
  return (
    <Footer
      brandTop={<>Ministère<br />de l'Intérieur</>}
      homeLinkProps={{ href: "/", title: "Accueil - toolmesh" }}
      contentDescription="ToolMesh : passerelle d'outils pour agents IA."
      accessibility="non compliant"
      termsLinkProps={{ href: "/mentions-legales" }}
      bottomItems={version ? [{ text: `Version ${version}`, linkProps: { href: "/mentions-legales" } }] : []}
    />
  );
}
