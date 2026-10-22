export const TYPE_LABELS = { mcp: "Serveur MCP", api: "API", skill: "Skill"};

// Minuscules + sans accents : "Réunion" ≈ "reunion"
const normalize = (s) =>
    String(s ?? "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

export function filterTools(tools, query){
    const q = normalize(query).trim();
    if(!q) return tools;
    return tools.filter((t) =>
        [t.name, t.description, t.type, TYPE_LABELS[t.type], t.required_role].some((champ) =>
             normalize(champ).includes(q)
        ),
    );
}