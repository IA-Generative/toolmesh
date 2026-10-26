import { useEffect, useState } from "react";
import Alert from "@codegouvfr/react-dsfr/Alert";
import Button from "@codegouvfr/react-dsfr/Button";
import Select from "@codegouvfr/react-dsfr/Select";
import { useAuth } from "../auth/AuthContext";
import {
  evaluateSearch,
  fetchDataset,
  fetchFeedback,
  fetchMyTools,
  fetchSearchStats,
  reviewFeedback,
} from "../auth/api";
import { BarList, LineChart, Meter, Stat } from "../tools/charts";
import "./SearchQuality.css";

const PERIODS = [7, 30, 90];
const MODE_LABELS = { hybrid: "mots-clés + sens", keyword: "mots-clés", dense: "sens", basic: "registre" };
const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)} %`);
const num = (v, digits = 2) => (v == null ? "—" : v.toFixed(digits));

function ReviewItem({ item, tools, onReviewed }) {
  const [expected, setExpected] = useState(item.expected[0] ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const act = async (status) => {
    setBusy(true);
    setError(null);
    try {
      await reviewFeedback(item.id, { status, expected: expected ? [expected] : [] });
      onReviewed();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <li className="review__item">
      <p className="review__query">« {item.query} »</p>
      <p className="review__meta">
        {new Date(item.created_at).toLocaleString("fr-FR")} · classement {MODE_LABELS[item.mode] ?? item.mode}
        {Object.keys(item.filters).length > 0 && ` · filtres ${JSON.stringify(item.filters)}`}
      </p>
      <p className="fr-text--sm fr-mb-1v">
        <strong>{item.verdict === "found" ? "A trouvé" : "N'a pas trouvé"}</strong>
        {item.comment && <> — {item.comment}</>}
      </p>
      <p className="fr-text--sm fr-mb-0">
        Résultats : {item.results.length ? item.results.map((r) => <code key={r} className="fr-mr-1w">{r}</code>) : "aucun"}
      </p>
      {error && <Alert className="fr-mt-1w" severity="error" small description={error} />}
      <div className="review__actions">
        <Select
          label="Outil attendu"
          nativeSelectProps={{ value: expected, onChange: (e) => setExpected(e.target.value) }}
        >
          <option value="">Aucun outil du catalogue</option>
          {tools.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
        </Select>
        <Button size="small" iconId="fr-icon-check-line" onClick={() => act("approved")} disabled={busy || (item.verdict === "found" && !expected)}>
          Approuver
        </Button>
        <Button size="small" priority="secondary" iconId="fr-icon-close-line" onClick={() => act("rejected")} disabled={busy}>
          Rejeter
        </Button>
      </div>
    </li>
  );
}

function Evaluation({ report }) {
  const modes = Object.keys(report.metrics);
  return (
    <div className="fr-mt-2w">
      <p className="fr-text--sm">
        {report.queries} requêtes du jeu de données, classées sur un index temporaire construit <strong>sans</strong> les alias appris :
        ce que la stratégie de recherche réussit seule.
      </p>
      <table className="metrics">
        <thead>
          <tr><th scope="col">Classement</th><th scope="col">Requêtes</th><th scope="col">Bon outil en 1er</th><th scope="col">Dans les 3 premiers</th><th scope="col">MRR</th><th scope="col">Sans réponse (aucun résultat)</th></tr>
        </thead>
        <tbody>
          {modes.map((m) => {
            const r = report.metrics[m];
            return (
              <tr key={m}>
                <th scope="row">{MODE_LABELS[m] ?? m}</th>
                <td>{r.queries}</td><td>{pct(r.hit1)}</td><td>{pct(r.hit3)}</td><td>{num(r.mrr)}</td><td>{pct(r.no_answer)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function SearchQuality() {
  const { user } = useAuth();
  const isAdmin = user?.roles?.includes("admin");
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const [pending, setPending] = useState([]);
  const [tools, setTools] = useState([]);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const [evaluating, setEvaluating] = useState(false);

  const [reload, setReload] = useState(0); // incrémenté pour relire les chiffres après une relecture de retour

  useEffect(() => {
    if (!isAdmin) return;
    let current = true;
    Promise.all([fetchSearchStats(days), fetchFeedback("pending")])
      .then(([s, p]) => {
        if (!current) return;
        setStats(s);
        setPending(p);
        setError(null);
      })
      .catch((e) => current && setError(e.message));
    return () => {
      current = false;
    };
  }, [isAdmin, days, reload]);
  useEffect(() => {
    if (isAdmin) fetchMyTools().then((d) => setTools(d.tools)).catch(() => {});
  }, [isAdmin]);

  if (!isAdmin) {
    return (
      <div>
        <h1>Qualité de la recherche</h1>
        <Alert severity="warning" title="Accès réservé" description="Cette page est réservée aux administrateurs." />
      </div>
    );
  }

  const download = async () => {
    const data = await fetchDataset();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "search-dataset.json" });
    a.click();
    URL.revokeObjectURL(url);
  };
  const evaluate = async () => {
    setEvaluating(true);
    setReport(null);
    try {
      setReport(await evaluateSearch());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="viz-root">
      <h1>Qualité de la recherche</h1>
      <p className="fr-text--lead">Ce que les utilisateurs cherchent, ce qu'ils trouvent, et ce qu'ils disent des résultats.</p>

      <div className="fr-mb-3w" style={{ maxWidth: "14rem" }}>
        <Select label="Période" nativeSelectProps={{ value: days, onChange: (e) => setDays(Number(e.target.value)) }}>
          {PERIODS.map((d) => <option key={d} value={d}>{d} derniers jours</option>)}
        </Select>
      </div>

      {error && <Alert className="fr-mb-3w" severity="error" title="Chargement impossible" description={error} />}
      {!stats && !error && <p role="status">Chargement…</p>}

      {stats && (
        <>
          <section className="viz-kpis" aria-label="Indicateurs">
            <Stat label="Recherches" value={stats.searches} hint={`sur ${stats.days} jours · ${stats.latency_ms.mean} ms en moyenne (p95 ${stats.latency_ms.p95} ms)`} />
            <Stat label="Sans résultat" value={stats.zero_results} hint={`${pct(stats.zero_result_rate)} des recherches`} />
            <Stat label="Recherches suivies d'un clic" value={pct(stats.click_rate)} hint={stats.click_mrr == null ? "pas encore de clic" : `rang moyen inverse (MRR) ${num(stats.click_mrr)}`} />
            {stats.found_rate == null ? (
              <Stat label="Jugées satisfaisantes" value="—" hint="pas encore de retour" />
            ) : (
              <Meter label="Jugées satisfaisantes" ratio={stats.found_rate} hint={`${stats.verdicts.found} oui · ${stats.verdicts.not_found} non`} />
            )}
            <Stat label="Jeu de données" value={stats.dataset.approved} hint={`${stats.dataset.pending} retour${stats.dataset.pending > 1 ? "s" : ""} à examiner`} />
          </section>

          <section className="viz-panel" aria-label="Évolution">
            <LineChart
              title="Recherches par jour"
              days={stats.by_day}
              series={[
                { key: "searches", label: "Recherches", color: "--series-1" },
                { key: "zero_results", label: "Sans résultat", color: "--series-2" },
              ]}
            />
            {Object.keys(stats.by_mode).length > 0 && (
              <p className="fr-text--sm viz-muted fr-mt-1w">
                Classement :{" "}
                {Object.entries(stats.by_mode).map(([m, n]) => `${MODE_LABELS[m] ?? m} ${n}`).join(" · ")}
              </p>
            )}
          </section>

          <div className="viz-columns">
            <section className="viz-panel">
              <BarList
                title="Requêtes sans résultat"
                rows={stats.top_zero_result_queries.map((r) => ({ label: r.query, value: r.count }))}
                empty="Aucune recherche sans résultat."
              />
            </section>
            <section className="viz-panel">
              <BarList
                title="Outils les plus choisis"
                rows={stats.tools_chosen.map((r) => ({ label: r.tool, value: r.count }))}
                empty="Aucun outil choisi pour l'instant."
              />
            </section>
            <section className="viz-panel">
              <BarList
                title="Requêtes jugées non satisfaisantes"
                rows={stats.top_missed.map((r) => ({
                  label: r.expected.length ? `${r.query} → ${r.expected.join(", ")}` : r.query,
                  value: r.count,
                }))}
                empty="Aucun retour négatif."
              />
            </section>
          </div>

          <section className="viz-panel" aria-labelledby="revue">
            <h2 id="revue" className="fr-h5">Retours à examiner ({pending.length})</h2>
            <p className="fr-text--sm viz-muted fr-mb-2w">
              Un retour approuvé entre dans le jeu de données et apprend la requête à l'outil attendu ; un retour rejeté est ignoré.
            </p>
            {pending.length === 0 ? (
              <p className="viz-muted">Rien à examiner.</p>
            ) : (
              <ul className="review">
                {pending.map((p) => <ReviewItem key={p.id} item={p} tools={tools} onReviewed={() => setReload((n) => n + 1)} />)}
              </ul>
            )}
          </section>

          <section className="viz-panel" aria-labelledby="jeu">
            <h2 id="jeu" className="fr-h5">Jeu de données</h2>
            <p className="fr-text--sm">
              {stats.dataset.approved} retour{stats.dataset.approved > 1 ? "s" : ""} approuvé{stats.dataset.approved > 1 ? "s" : ""}. Le fichier
              exporté a le format de <code>backend/eval/queries.json</code> : il se rejoue avec <code>eval.run</code> pour comparer
              des modèles ou des réglages avant de les déployer.
            </p>
            <div className="review__actions">
              <Button size="small" priority="secondary" iconId="fr-icon-download-line" onClick={download} disabled={stats.dataset.approved === 0}>Télécharger (JSON)</Button>
              <Button size="small" iconId="fr-icon-bar-chart-box-line" onClick={evaluate} disabled={stats.dataset.approved === 0 || evaluating}>{evaluating ? "Évaluation…" : "Évaluer la recherche sur ce jeu"}</Button>
            </div>
            {report && <Evaluation report={report} />}
          </section>
        </>
      )}
    </div>
  );
}
