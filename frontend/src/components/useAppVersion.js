import { useEffect, useState } from "react";
import { fetchVersion } from "../auth/api";

let cached; // une seule requête pour toute la session

export default function useAppVersion(){
    const [version, setVersion] = useState(cached ?? null);
    useEffect(() => {
        if(cached) return;
        fetchVersion().then((v) =>{ cached = v; setVersion(v); }).catch(()=>{});
    }, []);
    return version; // null tant que non chargée ou en cas d'erreur
}