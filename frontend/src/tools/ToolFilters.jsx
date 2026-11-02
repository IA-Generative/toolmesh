import { useRef } from "react";
import Button from "@codegouvfr/react-dsfr/Button";
import { FilterTag } from "./ToolCard";
import { TYPE_LABELS } from "./types";

function Group({ legend, items, isPressed, onToggle, labelOf = (v) => v}){
    if(items.length === 0) return null;
    return(
        <fieldset className="fr-fieldset fr-mb-2w">
            <legend className="fr-fieldset__legend fr-text--sm fr-text--bold">{legend}</legend>
            <ul className="fr-tags-group">
                {items.map((item) => (
                    <li key={item}>
                        <FilterTag label={labelOf(item)} pressed={isPressed(item)} onClick={() => onToggle(item)}/>
                    </li>
                ))}
            </ul>
        </fieldset>
    );
}

// Section de filtres de l'accueil : titre visible, un groupe par critère, compteur et réinitialisation.
export default function ToolFilters({ types, versions, tags, active, onType, onVersion, onTag, count, total, filtered, onReset}) {
    const titleRef = useRef(null);

    return (
        <section className="home-filters fr-p-2w fr-mb-3w" aria-labelledby="filtres-titre">
            <h2 id="filtres-titre" ref={titleRef} tabIndex={-1} className="fr-h6">Filtrer les outils</h2>
            <Group legend="Type" items={types} labelOf={(t) => TYPE_LABELS[t] ?? t} isPressed={(t) => active.type === t} onToggle={onType}/>
            <Group legend="Version" items={versions} isPressed={(v) => active.version === v} onToggle={onVersion} />
            <Group legend="Tags" items={tags} isPressed={(t) => active.tags.includes(t)} onToggle={onTag} />
            <div className="home-filters__footer">
                <p className="fr-text--sm fr-mb-0" role="status">
                    {count === undefined ? "Recherche en cours..." : `${count} outil${count > 1 ? "s" : ""} sur ${total}`}
                </p>
                {filtered && (
                    <Button type="button" priority="tertiary no outline" size="small" iconId="fr-icon-close-line" onClick={() => {onReset(); titleRef.current?.focus();}}>
                        Réinitialiser les filtres
                    </Button>
                )}
            </div>
        </section>
    );
}
