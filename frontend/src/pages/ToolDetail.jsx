import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import Button from "@codegouvfr/react-dsfr/Button";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Badge from "@codegouvfr/react-dsfr/Badge";
import { fetchMyTools } from "../auth/api";
import "./ToolDetail.css";
import ToolTester from "./ToolTester";
import { getHistoryEntry } from "../tools/history";
import { TYPE_ICONS, TYPE_LABELS } from "../tools/types";

export default function ToolDetail() {
  const { name } = useParams();
  const [tools, setTools] = useState(null);
  const [error, setError] = useState(null);
  const [testing, setTesting] = useState(false);
  const [params, setParams] = useSearchParams();
  const replayId = params.get("replay");
  const replay = replayId ? getHistoryEntry(replayId) : null;
  const closeTester = () => {
    setTesting(false);
    if (replayId) {
      const next = new URLSearchParams(params);
      next.delete("replay");
      setParams(next, { replace: true });
    }
  };

  useEffect(() => {
    fetchMyTools().then((d) => setTools(d.tools)).catch((e) => setError(e.message));
  }, []);

  const tool = tools?.find((t) => t.name === name);
  const back = (
    <p>
      <Link to="/accueil" className="fr-link fr-icon-arrow-left-line fr-link--icon-left">Retour à mes outils</Link>
    </p>
  );

  if (error) {
    return (
      <div>
        {back}
        <Alert severity="error" title="Impossible de charger l'outil" description={error} />
      </div>
    );
  }
  if (!tools) return <p role="status">Chargement…</p>;
  if (!tool) {
    return (
      <div>
        {back}
        <Alert severity="warning" title="Outil introuvable" description={`Aucun outil « ${name} » n'est disponible pour votre compte.`} />
      </div>
    );
  }

  const tags = tool.tags ?? [];
  const isApi = tool.type === "api";
  const sourceLabel = { mcp: "Serveur MCP", api: "API", skill: "Skill" }[tool.type] ?? "Source";
  const facts = [
    ["Catégorie", TYPE_LABELS[tool.type] ?? tool.type],
    ["Source", tool.source],
    ["Accès", tool.required_role ? `Rôle requis : ${tool.required_role}` : "Accessible à tous"],
  ];

  return (
    <div>
      {back}

      <header className="tool-hero">
        <span className={`tool-hero__icon ${TYPE_ICONS[tool.type] ?? "fr-icon-settings-5-line"}`} aria-hidden="true" />
        <div>
          <h1>{tool.name}</h1>
          <ul className="fr-badges-group">
            <li><Badge as="span" severity="info" noIcon>{TYPE_LABELS[tool.type] ?? tool.type}</Badge></li>
            <li>
              <Badge as="span" severity={tool.required_role ? "warning" : "success"} noIcon>
                {tool.required_role ? `Rôle : ${tool.required_role}` : "Accessible à tous"}
              </Badge>
            </li>
          </ul>
        </div>
        <Button className="tool-hero__action" iconId="fr-icon-play-circle-line" onClick={() => setTesting(true)}>
          Tester
        </Button>
      </header>
      <ToolTester key={`${tool.name}:${replay?.id ?? ""}`} tool={tool} initial={replay} open={testing || Boolean(replay)} onClose={closeTester} />

      <div className="tool-layout">
        <div>
          <section className="tool-panel" aria-labelledby="tool-desc">
            <h2 id="tool-desc" className="tool-panel__title">Description</h2>
            <p>{tool.description || "Aucune description."}</p>
            {tags.length > 0 && (
              <ul className="fr-tags-group fr-mt-2w">
                {tags.map((tag) => (
                  <li key={tag}>
                    <Link to={`/accueil?tag=${encodeURIComponent(tag)}`} className="fr-tag">{tag}</Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="tool-panel" aria-labelledby="tool-origin">
            <h2 id="tool-origin" className="tool-panel__title">Origine</h2>
            <ol className="tool-origin">
              <li className="tool-origin__node">
                <span className="tool-origin__label">{sourceLabel}</span>
                <strong>{tool.source}</strong>
                {tool.source_url && <span className="tool-origin__url">{tool.source_url}</span>}
              </li>
              <li className="tool-origin__arrow fr-icon-arrow-right-line" aria-hidden="true" />
              <li className="tool-origin__node">
                <span className="tool-origin__label">{isApi ? "Endpoint" : "Outil"}</span>
                <strong>{tool.name}</strong>
              </li>
            </ol>
            {tool.method && tool.path && (
              <p className="tool-route">
                <span className={`tool-method tool-method--${tool.method.toLowerCase()}`}>{tool.method}</span>
                <code>{tool.path}</code>
              </p>
            )}
          </section>

        </div>

        <aside className="tool-panel" aria-labelledby="tool-facts">
          <h2 id="tool-facts" className="tool-panel__title">Informations</h2>
          <dl className="tool-facts">
            {facts.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>
    </div>
  );
}
