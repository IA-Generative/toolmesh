# toolmesh

## Local authentication (Keycloak)

```bash
docker compose up -d --build   # Keycloak (realm `toolmesh` auto-imported) + backend with hot reload on :8010
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

`GET /api/me/tools` returns mock tools filtered by the caller's realm roles: `user` sees 3, `admin` sees all 5.

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

`GET /api/mock/downstream` shows the pattern: toolmesh swaps the caller's token for a new one
scoped to the downstream service (RFC 8693) and calls the mock service on :8020 with it.
The downstream only accepts tokens with audience `downstream-service`. A token from a dev client such as
`toolmesh-cli` is rejected there (`curl -H "Authorization: Bearer $CLI_TOKEN" localhost:8020/whoami` → 401).
A token issued to the `toolmesh` client itself (browser login, `/api/auth/token`) is **also accepted**: that client
must be allowed to exchange for the target (see below), and the allowed roles end up in its own tokens too.

Keycloak setup (see `keycloak/toolmesh-realm.json`): confidential client `toolmesh` with
`standard.token.exchange.enabled` (requires Keycloak ≥ 26.2), client `downstream-service` and its
client role `access`, granted to the users. The `toolmesh` client has `fullScopeAllowed=false`, so each exchange
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
http://localhost:8030/mcp. Its `/mcp` endpoint requires a Keycloak token with audience `mcp-datetime` (401 otherwise). Its only purpose here is to exercise token exchange: `GET /api/mock/mcp-datetime?date=2026-10-13&kind=month` on toolmesh exchanges the caller's token and calls `period_bounds` on it. Tests: `cd mcp-datetime && uv run pytest`.

## Kubernetes

The chart (`helm/`) deploys the backend and `mcp-datetime`. Set `oidc.issuer` and either
`oidc.clientSecret.existingSecret` or `oidc.clientSecret.value` (secret of the `toolmesh` Keycloak client,
required). `TOOLMESH_MCP_DATETIME_URL` is derived from the release automatically; expose the MCP outside the
cluster with `mcpDatetime.ingress.enabled=true`.
