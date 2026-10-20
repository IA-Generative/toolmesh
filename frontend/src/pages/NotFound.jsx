import Button from "@codegouvfr/react-dsfr/Button";

export default function NotFound() {
  return (
    <main id="contenu" className="fr-container">
      <div className="fr-my-7w fr-mt-md-12w fr-mb-md-10w fr-grid-row fr-grid-row--gutters fr-grid-row--middle fr-grid-row--center">
        <div className="fr-py-0 fr-col-12 fr-col-md-6">
          <h1>Page non trouvée</h1>
          <p className="fr-text--sm fr-mb-3w">Erreur 404</p>
          <p className="fr-text--lead fr-mb-3w">
            La page que vous cherchez est introuvable. Excusez-nous pour la gêne occasionnée.
          </p>
          <p className="fr-text--sm fr-mb-5w">
            Si vous avez tapé l'adresse web dans le navigateur, vérifiez qu'elle est correcte.
            Si vous avez cliqué sur un lien, il est peut-être obsolète.
          </p>
          <Button linkProps={{ href: "/" }}>Page d'accueil</Button>
        </div>
      </div>
    </main>
  );
}
