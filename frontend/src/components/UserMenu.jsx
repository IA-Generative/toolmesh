import { useEffect, useId, useRef, useState } from "react";
import Button from "@codegouvfr/react-dsfr/Button";
import { useAuth } from "../auth/AuthContext";

export default function UserMenu(){
    const { user, logout } = useAuth();
    const [open, setOpen] = useState(false);
    const rootRef = useRef(null);
    const triggerRef = useRef(null);
    const panelId = useId();

    useEffect(() => {
        if (!open) return;
        const onKey = (e) => {
            if(e.key === "Escape"){
                setOpen(false);
                triggerRef.current?.focus(); // le focus revient sur le bouton
            }
        };
        const onPointer = (e) => {
            if(!rootRef.current?.contains(e.target)) setOpen(false)
        };
        document.addEventListener("keydown", onKey);
        document.addEventListener("mousedown", onPointer);
        return() => {
            document.removeEventListener("keydown", onKey);
            document.removeEventListener("mousedown", onPointer);
        };
    }, [open])

    return (
        <div className="user-menu" ref={rootRef}>
            <button
            ref={triggerRef}
            type="button"
            className="user-menu__trigger"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((o) => !o)}
            >
                <span className="user-menu__avatar" aria-hidden="true">
                    {user.username.slice(0,2).toUpperCase()}
                </span>
                <span className="user-menu__name">{user.username}</span>
                <span className="fr-icon-arrow-up-s-line fr-icon--sm" aria-hidden="true"/>
            </button>

            {/* après le bouton dans le DOM : Tab y mène directement */}
            <div id={panelId} className="user-menu__panel" hidden={!open} role="group" aria-label="Menu du compte">
                {user.email && <p className="fr-text--sm fr-mb-1w">{user.email}</p>}
                <ul className="fr-raw-list">
                    <li>
                        <Button iconId="fr-icon-logout-box-r-line" priority="tertiary no outline" onClick={logout}>
                            Se déconnecter
                        </Button>
                    </li>
                </ul>
            </div>
        </div>
    )
}