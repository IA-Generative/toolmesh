import { useNavigate } from "react-router";
import SearchBar from "@codegouvfr/react-dsfr/SearchBar";
import { searchModal } from "./searchModal";

export default function SearchModal(){
    const navigate = useNavigate();

    const onSearch = (text) => {
        searchModal.close();
        navigate(text ? `/accueil?q=${encodeURIComponent(text)}` : "/accueil");
    };

    return(
        <searchModal.Component title="Rechercher un outil" topAnchor>
            <SearchBar label="Rechercher un outil" big allowEmptySearch onButtonClick={onSearch} />
        </searchModal.Component>
    )
}