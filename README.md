# toolmesh

## Local authentication (Keycloak)

```bash
docker compose up -d --build   # Keycloak (realm `toolmesh` auto-imported), PostgreSQL, SearXNG, the MCP servers, backend (hot reload) on :8010 and frontend on :3000
```

Backend: http://localhost:8010/docs (override with `TOOLMESH_BACKEND_PORT`). Keycloak admin console: http://localhost:8080 (`admin` / `admin`).

| Account | Password | Realm roles |
|---------|----------|-------------|
| `user`  | `user`   | `user` |
| `admin` | `admin`  | `user`, `admin` |

Human flow (password grant on the dev client `toolmesh-cli`):

```bash
TOKEN=$(curl -s http://localhost:8080/realms/toolmesh/protocol/openid-connect/token \
  -d grant_type=password -d client_id=toolmesh-cli -d username=user -d password=user | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/me/tools
```

Service flow (client credentials, `toolmesh-agent` / `toolmesh-agent-secret`):

```bash
curl -s http://localhost:8080/realms/toolmesh/protocol/openid-connect/token \
  -d grant_type=client_credentials -d client_id=toolmesh-agent -d client_secret=toolmesh-agent-secret
```

`GET /api/me/tools` lists the tools of the registry (PostgreSQL) visible to the caller: a source can require a realm role.
The registry starts empty: add sources from the app (http://localhost:3000, "Ajouter un outil") or with `POST /api/sources`,
for example the MCP servers of this stack (`mcp-datetime`, `mcp-search`, see below). `POST /api/me/tools/{name}/call`
runs a tool as the caller (the "Tester" button of the app); skills cannot be run yet, as no model provider is configured.

## Browser login (BFF)

For a web SPA, the backend acts as its BFF: it runs the OIDC authorization code flow with PKCE against the
confidential Keycloak client `toolmesh` (via python-keycloak, same client as the token exchange), keeps the tokens in Redis, and gives the browser only an opaque
`HttpOnly` cookie (`toolmesh_session`). Bearer tokens keep working for CLIs and agents, and token exchange is unchanged.

| Endpoint | Role |
|----------|------|
| `GET /api/auth/login?redirect=/path` | redirects to Keycloak (PKCE + state) |
| `GET /api/auth/callback` | swaps the code for tokens, opens the session, redirects to the SPA |
| `GET /api/auth/me` | current user (cookie or bearer) |
| `POST /api/auth/token` | password grant for scripts/SDK, JSON body `{"username","password"}` |
| `POST /api/auth/refresh` | refresh grant for scripts/SDK, JSON body `{"refresh_token"}` |
| `POST /api/auth/logout` | drops the session, returns `{"redirectUrl"}` (Keycloak end-session) for the SPA to open |

The SPA calls the API with `credentials: "include"`. Settings: `TOOLMESH_FRONTEND_URL` (post-login redirect and the
only CORS origin, default `http://localhost:3000`), `TOOLMESH_BACKEND_PUBLIC_URL`, `TOOLMESH_REDIS_URL`,
`TOOLMESH_KEYCLOAK_URL` / `_PUBLIC_URL` / `_REALM` / `_CLIENT_ID` / `_CLIENT_SECRET`, `TOOLMESH_SESSION_COOKIE_SECURE` (set `true` behind HTTPS).

Try it without a frontend by pointing the post-login redirect at the backend itself:

```bash
TOOLMESH_FRONTEND_URL=http://localhost:8010 docker compose up -d --build
```

1. Open http://localhost:8010/api/auth/login?redirect=/api/auth/me in a browser and sign in as `user` / `user`.
   Keycloak sends you back to `/api/auth/me`, which shows your profile (the session cookie is set).
2. Open http://localhost:8010/api/me/tools: the same cookie works on every route.
3. Log out from http://localhost:8010/docs (`POST /api/auth/logout`, same cookie), then open the returned `redirectUrl`.

Scripts: `curl -s -X POST localhost:8010/api/auth/token -H 'Content-Type: application/json' -d '{"username":"user","password":"user"}'`.

## Forwarding identity to another service (token exchange)

A source registered with the authentication "Token exchange" (and an audience) is called with a token toolmesh obtains by
swapping the caller's one for a token scoped to that audience (RFC 8693), for the discovery of its tools
(`POST /api/sources/discover`) as well as for running them. The target only accepts tokens with its own audience: a
token from a dev client such as `toolmesh-cli` is rejected by `mcp-datetime` (401). A token issued to the `toolmesh`
client itself (browser login, `/api/auth/token`) is **also accepted**: that client must be allowed to exchange for the
target (see below), and the allowed roles end up in its own tokens too.

Keycloak setup (see `keycloak/toolmesh-realm.json`): confidential client `toolmesh` with
`standard.token.exchange.enabled` (requires Keycloak ≥ 26.2), the exchange targets (`mcp-datetime`, `mcp-search`), each with a
client role `access` granted to the users. The `toolmesh` client has `fullScopeAllowed=false`, so each exchange
target's `access` role is added to its scope (`clientScopeMappings`): without it Keycloak answers
`Requested audience not available`. Adding a new exchange target therefore means a client, its `access` role, the
role granted to the users, and a `clientScopeMappings` entry for `toolmesh`. The dev clients (`toolmesh-cli`,
`toolmesh-agent`) have `fullScopeAllowed=false` and no such mapping, so their tokens never carry that audience.

The exchange request is built by `app/auth/exchange.py` and not by python-keycloak, whose `exchange_token` always
sends an empty `requested_subject` and no `subject_token_type`, both rejected by a standard token exchange.

Keycloak only imports `--import-realm` when the realm does not exist: after changing `toolmesh-realm.json`, recreate
the container (`docker compose up -d --force-recreate keycloak`) for the change to apply. This resets its dev data.

## MCP datetime (separate service)

`mcp-datetime/` is a standalone MCP server (own project, Dockerfile and tests) for dates and periods:
`now`, `convert_timezone`, `add_to_date`, `date_diff`, `weekday`, `period_bounds`, `business_days`,
`add_business_days`. It is started by `docker compose up -d --build` and serves streamable HTTP on
http://localhost:8030/mcp. Its `/mcp` endpoint requires a Keycloak token with audience `mcp-datetime` (401 otherwise). Register it as a source of type MCP (URL `http://mcp-datetime:8000/mcp`, authentication "Token exchange", audience `mcp-datetime`) to try the token exchange. Tests: `cd mcp-datetime && uv run pytest`.

## MCP search (separate service)

`mcp-search/` is a standalone MCP server (own project, Dockerfile and tests) that gives an agent the web:

- `web_search(query, max_results, language, time_range, category)`: results (title, url, snippet, engine) from a
  [SearXNG](https://docs.searxng.org) meta-search engine, started by the compose stack (`searxng/settings.yml` enables its
  JSON output; try it on http://localhost:8888).
- `fetch_page(url, max_chars)`: title and readable text of a page. Loopback, private and link-local addresses (and
  redirects towards them) are refused, unless `MCP_SEARCH_ALLOW_PRIVATE_HOSTS` is set.

It serves streamable HTTP on http://localhost:8040/mcp and, like `mcp-datetime`, requires a token with audience
`mcp-search` (client `mcp-search` in the realm, `access` role, exchange allowed for the `toolmesh` client). To use it from
the app, add a source of type MCP with the URL `http://mcp-search:8000/mcp`, authentication "Token exchange" and the
audience `mcp-search`, then "Découvrir maintenant" (the demo data already declares it as `search-mcp`).
Tests: `cd mcp-search && uv run pytest`. After changing the realm, recreate Keycloak (see above).

## Searching the tools

`GET /api/me/tools/search?q=…&type=…&tag=…&source=…&version=…` searches the tools visible to the caller and/or filters
them; the app's search modal and "Mes outils" page use it. Tools are indexed in Qdrant (started by the compose stack, on
:6333) when a source is added, refreshed or deleted:

- keywords: a BM25-like sparse vector computed by the backend (accents and stop words folded);
- meaning: a dense vector from an OpenAI-compatible embeddings API, **optional** (`TOOLMESH_EMBEDDINGS_URL`,
  `TOOLMESH_EMBEDDINGS_API_KEY`, `TOOLMESH_EMBEDDINGS_MODEL`, e.g. in your shell before `docker compose up`).

Qdrant fuses both rankings (reciprocal rank fusion) and applies the filters and the role of the caller. The response's `mode`
says what happened: `hybrid`, `keyword` (no embeddings API), `basic` (no Qdrant, or it failed: plain keyword match on the
registry) or `filter` (no query). `POST /api/admin/reindex` (role `admin`) rebuilds the index, e.g. after changing the
embedding model.

How tools are indexed, the settings, the choice of the model and how to measure the quality of the search with your own
model (`backend/eval`): see [docs/search.md](docs/search.md).

Users can say whether a search found what they wanted; an admin reviews the verdicts, which then feed a dataset and teach the
index, and follows the quality on a dashboard ("Qualité de la recherche"): see "Learning from the users" in
[docs/search.md](docs/search.md).

Each source has a `version`: the `info.version` of its OpenAPI document or the version announced by the MCP server, read when
its tools are discovered (and again on refresh), unless you set one by hand. It is shown on the tool and can be filtered on.

## Kubernetes

The chart (`helm/`) deploys the backend and `mcp-datetime`. Set `oidc.issuer` and either
`oidc.clientSecret.existingSecret` or `oidc.clientSecret.value` (secret of the `toolmesh` Keycloak client,
required). `TOOLMESH_MCP_DATETIME_URL` is derived from the release automatically; expose the MCP outside the
cluster with `mcpDatetime.ingress.enabled=true`.

It also deploys `mcp-search` (`mcp_search`) and the SearXNG it reads (`searxng` dependency, `searxng.enabled`), reachable
only from inside the cluster; the secrets they need are listed in `helm/SECRETS.md`.
