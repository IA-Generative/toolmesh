# Searching the tools

How a tool is found, why it works that way, and how to check it still does when something changes (embedding model,
text, weights). The numbers below come from `backend/eval` and are a **starting point for one small multilingual
model**: run the evaluation with your own model before trusting them.

## What is indexed

One Qdrant point per tool, with two vectors and a payload.

| Part | Content | Why |
|---|---|---|
| keyword vector (sparse) | the words of the tool, **weighted by where they come from**: name ×3, tags ×2, description, endpoint, inputs, source ×1 | exact terms and identifiers; Qdrant applies the IDF |
| dense vector | a short natural-language text: `find pets by status. <description>` / `Tags: …` / `Inputs: …` / `Endpoint: …` / `Source: …` | meaning, across wordings and languages |
| payload (indexed) | `type`, `source`, `source_id`, `version`, `tags`, `required_role`, `enabled` | filters, and what the caller may see |

Three choices come from how both indexes read text (`app/toolsearch/text.py`, `sparse.py`):

- **Identifiers are split into words**: `findPetsByStatus` → `find pets by status`. An embedding model sees the raw
  identifier as one rare word, and a keyword index cannot match "pets" to it. Camel case is split *before* the case is
  lost; accents, case, stop words (French and English) and a plural `s` are folded.
- **The inputs of the tool are searched**: parameter names and descriptions (`city: Nom de la ville`). Users describe
  what they have ("a city") as much as what they want.
- **Short text, most telling parts first.** The full structured text gave the best recall@3; shorter variants (name and
  description only, with or without tags) were worse (see `--dense-text` in `eval/run.py`).

## How a query is answered

1. The query becomes a keyword vector and, if an embeddings API is configured, a dense vector (with the query prefix
   if the model wants one).
2. Qdrant ranks the 50 nearest by each vector, **with the filters applied** (type, source, version, every requested
   tag, the tool enabled, and `required_role` empty or among the caller's roles).
3. The backend fuses the two rankings with a weighted reciprocal rank fusion (`k` = 10, weights 1 and 1) and adds a
   **bonus to the tools whose whole name is in the query** (`get weather` → `get_weather`, `findPetsByStatus` →
   `findPetsByStatus`): an identifier typed as such must come first whatever the embedding thinks.
4. Dense matches under `TOOLMESH_SEARCH_MIN_DENSE_SCORE` are dropped before the fusion, so an unrelated question
   ("recette de la tarte aux pommes") can answer nothing instead of the nearest tools.
5. The registry has the last word: only tools visible to the caller are returned, whatever the index says.

Without an embeddings API only step 1–3 on keywords run (`mode: keyword`); without Qdrant, or if it fails, the registry
answers by plain keyword match (`mode: basic`).

## Keeping the index true

- Each tool stores a hash of what its vectors were computed from (text, embedding model, prefix, dimensions). Refreshing
  a source embeds **only the tools whose text changed**; a change of version, role, tags or `enabled` only updates the
  payload.
- At startup, a collection that does not fit the embeddings (none before, another vector size now) is recreated and
  refilled from the registry. Changing the **model** with the same vector size is not detected: call
  `POST /api/admin/reindex`.

## Learning from the users

The search is only as good as the queries it was tested on, so real ones are collected, reviewed and fed back.

1. **Every search with a query is logged** (`search_events`: who, what, filters, how it was ranked, which tools came back,
   how long it took) and answered with a `search_id`. Searches older than `TOOLMESH_SEARCH_LOG_RETENTION_DAYS` (90) are
   deleted at startup, except those with an approved verdict; `TOOLMESH_SEARCH_LOG_ENABLED=false` logs nothing. A user
   only sees their own searches' ids, and queries are free text: treat the log as personal data.
2. **The user evaluates the search** in the app: "Cette recherche a-t-elle trouvé ce que vous cherchiez ?" → yes (and which
   tool) or no (and which tool it should have been, or none, i.e. the catalogue has nothing for this question), with an
   optional comment (`POST /api/search/{search_id}/feedback`). Opening a result is recorded as a click
   (`POST /api/search/{search_id}/click`, rank included). Tools are always referred to by **id** (the name of a tool
   is only unique within its source), in the search results, the clicks and the verdicts.
3. **An admin reviews each verdict** (dashboard, "Retours à examiner"): approve it (possibly correcting the expected
   tool) or reject it. Nothing a user says is used before that, so a mistake or an attempt to push a tool is not learned.
4. **An approved verdict does two things**:
   - it joins the **dataset** (`GET /api/admin/search/dataset`, same format as `backend/eval/queries.json`, except that the
     expected tools are ids; `eval.run` accepts names or ids in `queries.json`, so it can be replayed there or kept as the test set for the next model);
   - the query becomes an **alias of the expected tool** (at most 10 per tool, the newest): it is added to the text of
     the tool, in the keyword vector (weight 2) and in the dense text ("Also searched as: …"), and that tool alone is
     re-embedded. The next person asking in the same words finds it, whatever the model thinks. Rejecting or reopening
     the verdict removes the alias.
5. **The dashboard** (admin, "Qualité de la recherche"): searches per day with and without result, the share followed by a
   click and the mean reciprocal rank of the first click, the share of searches judged satisfactory, the queries with no
   result, the queries judged unsatisfactory (with the tool that was expected), the tools users choose, latency, and the
   verdicts waiting for review.
6. **"Évaluer la recherche sur ce jeu"** (`POST /api/admin/search/evaluate`) measures hit@1, hit@3 and MRR on the dataset
   with a temporary index of the registry built **without the aliases**: what the strategy achieves on real queries, not
   what it was taught by the very same queries (which would be 100 % by construction). Compare it before and after a
   change of model, prefix or weight; it embeds every tool, so it takes a few seconds with an embeddings API.

## Settings

| Variable | Default | Role |
|---|---|---|
| `TOOLMESH_QDRANT_URL`, `_QDRANT_API_KEY`, `_QDRANT_COLLECTION` | – / – / `toolmesh-tools` | the index; unset: no index |
| `TOOLMESH_EMBEDDINGS_URL`, `_API_KEY`, `_MODEL` | – | OpenAI-compatible `POST <url>/embeddings`; unset: keywords only |
| `TOOLMESH_EMBEDDINGS_DIMENSIONS` | probed | size of the vectors (sent as `dimensions` too) |
| `TOOLMESH_EMBEDDINGS_QUERY_PREFIX`, `_DOCUMENT_PREFIX` | empty | for models trained with instructions (e5: `query: ` / `passage: `; bge: an instruction on the query) |
| `TOOLMESH_SEARCH_MIN_DENSE_SCORE` | unset | cosine score under which a dense match is ignored |
| `TOOLMESH_SEARCH_DENSE_WEIGHT`, `_KEYWORD_WEIGHT`, `_RRF_K`, `_NAME_BONUS` | 1, 1, 10, 0.15 | the fusion |
| `TOOLMESH_SEARCH_LOG_ENABLED`, `_LOG_RETENTION_DAYS` | true, 90 | the log of the searches (see below) |

**Choose a multilingual model** (the tools and the questions are in French and English): e.g. `bge-m3`,
`multilingual-e5-*`, or an equivalent of the hub. An English-only model cannot link "quel temps fait-il" to a weather tool.

## Checking it: `backend/eval`

`eval/catalog.json` is a catalogue of 34 tools (MCP servers, a Swagger with camelCase operations, skills, French and
English descriptions); `eval/queries.json` has 51 queries by category (identifiers, paraphrases in both languages,
vague intents, cross-language, filters, questions with no answer). The runner indexes the catalogue in an in-memory
Qdrant through the same code as the API and ranks every query with keywords, dense vectors and both fused.

```bash
cd backend
uv run python -m eval.run                      # keywords only
uv run python -m eval.run --embedder api       # TOOLMESH_EMBEDDINGS_* from the environment (add the prefixes you use)
uv run --with fastembed python -m eval.run \
    --embedder fastembed:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2   # a local model, no API
uv run python -m eval.run --embedder api --verbose --min-dense-score 0.25 --rrf-k 10
```

It prints hit@1 / hit@3 / MRR per category and mode, and, for the dense vectors, the cosine score of the right tool
against the best score of a question with no answer: the threshold goes between the two. Add your own tools and queries
to the two JSON files, it is the only way to know how the search behaves on *your* catalogue.

### What it showed (paraphrase-multilingual-MiniLM-L12-v2, 46 queries with an answer)

| | hit@1 | hit@3 | MRR |
|---|---|---|---|
| keywords, first version (whole identifiers, no plural) | 0.59 | 0.65 | 0.62 |
| keywords, now | 0.61 | 0.70 | 0.65 |
| dense, now | 0.70 | 0.91 | 0.81 |
| **hybrid, first version** (Qdrant's RRF, no bonus) | 0.65 | 0.89 | 0.79 |
| **hybrid, now** | 0.72 | 0.93 | 0.83 |

- Identifiers: 0.60 → 1.00 hit@1 (split names, name bonus).
- The weights, `k` and the bonus value hardly matter around the defaults (±0.01 MRR); the text and the threshold do.
- With `--min-dense-score 0.25` this model answers nothing to 4 of 5 unrelated questions for −0.01 MRR; its right tools
  score from 0.25 (median 0.52), unrelated questions up to 0.44 (median 0.18). **The threshold is model-specific.**
- Weak spots left: vague intents ("un animal à adopter") and queries where the tools are siblings (`get_weather` vs
  `get_forecast`); a reranker or better descriptions are the next levers.
