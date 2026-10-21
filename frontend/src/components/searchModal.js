import { createModal } from "@codegouvfr/react-dsfr/Modal";

//Dans un fichier séparé de SearchModal par rapport à une règle ESLint

export const searchModal = createModal({ id: "recherche-outils", isOpenedByDefault: false });
