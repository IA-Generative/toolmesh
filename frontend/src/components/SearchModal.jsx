import { useNavigate } from "react-router";
import SearchBar from "@codegouvfr/react-dsfr/SearchBar";
import { searchModalJS } from "./searchModalJS";

export default function SearchModal(){
    const navigate = useNavigate();

    const onSearch = (text) => {
        searchModalJS.close();
        navigate(text ? `/accueil?q=${encodeURIComponent(text)}` : "/accueil");
    };

    return(
        <searchModalJS.Component title="Rechercher un outil" titleAs="h2" topAnchor>
            <SearchBar label="Rechercher un outil" big allowEmptySearch onButtonClick={onSearch} />
        </searchModalJS.Component>
    )
}