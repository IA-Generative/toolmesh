const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

// Coloration JSON minimale, sans dépendance : clés, chaînes, nombres, booléens/null.
function highlight(json) {
  const parts = [];
  let last = 0;
  for (const m of json.matchAll(TOKEN)) {
    if (m.index > last) parts.push(json.slice(last, m.index));
    const [full, str, colon, word, num] = m;
    const cls = str ? (colon ? "json-key" : "json-string") : word ? "json-word" : num ? "json-number" : "";
    parts.push(
      <span key={m.index} className={cls}>
        {str && colon ? str : full}
      </span>,
    );
    if (colon) parts.push(colon);
    last = m.index + full.length;
  }
  parts.push(json.slice(last));
  return parts;
}

export default function JsonView({ value, label }) {
  return (
    <pre className="json-view" tabIndex={0} aria-label={label}>
      <code>{highlight(JSON.stringify(value, null, 2))}</code>
    </pre>
  );
}
