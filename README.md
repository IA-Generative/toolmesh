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

## Forwarding identity to another service (token exchange)

`GET /api/mock/downstream` shows the pattern: toolmesh swaps the caller's token for a new one
scoped to the downstream service (RFC 8693) and calls the mock service on :8020 with it.
The downstream only accepts tokens with audience `downstream-service`, so the caller's original
token is rejected there (`curl -H "Authorization: Bearer $TOKEN" localhost:8020/whoami` → 401).

Keycloak setup (see `keycloak/toolmesh-realm.json`): confidential client `toolmesh` with
`standard.token.exchange.enabled` (requires Keycloak ≥ 26.2), client `downstream-service` and its
client role `access`, granted to the users. Dev clients (`toolmesh-cli`, `toolmesh-agent`) have
`fullScopeAllowed=false` so their own tokens never carry that audience.

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
