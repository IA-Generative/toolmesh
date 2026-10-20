# Secrets de toolmesh

Ce document dit quels secrets l'application attend, où les écrire dans Vault, comment ils arrivent dans les pods
(Vault Secrets Operator, comme Muffin) et comment les renouveler. Il ne contient aucune valeur réelle.

Chaque composant (`backend`, `frontend`, `mcp_datetime`) charge des `Secret` dans son environnement avec `envFrom`, et
`extraObjects` déclare les `VaultStaticSecret` qui créent ces `Secret`. Le `frontend` (SPA statique servie par nginx) n'a **aucun** secret. Tout est écrit dans
[`values/common-values.yaml`](values/common-values.yaml), `values.yaml` ne contenant que les valeurs par défaut du chart.

## Règles

1. Aucun secret dans Git, dans `values.yaml` ni dans une image.
2. `env:` ne sert qu'à la configuration non secrète. Il est visible dans les valeurs Helm et dans le secret de
   release Helm : n'y mettez jamais un identifiant, même « temporaire ».
3. Un secret par environnement : ne réutilisez jamais une valeur de dev en production.
4. Le dépôt est scanné par gitleaks (pre-commit et CI) : un secret commité fait échouer le contrôle mais reste dans
   l'historique. S'il arrive quand même dans Git, considérez-le comme compromis et renouvelez-le.

## Où les écrire dans Vault

Deux secrets KV v2. Le premier, `keycloak`, est lu par le backend et le MCP pour qu'ils ne puissent pas diverger sur l'issuer ; le second, `redis`, par le backend.

### `keycloak`

| Élément | Valeur |
|---|---|
| Montage KV v2 | `global.vaultMount` (défaut `exploration`) |
| Chemin | `<global.vaultEnv>/toolmesh/keycloak` (`vaultEnv` : `dev`, `staging`, `prod`...) |
| `Secret` Kubernetes créé | `toolmesh-keycloak` |
| Lu par | `backend`, `mcp_datetime` |

Clés à y écrire :

| Clé | Rôle | Backend | MCP datetime |
|---|---|:-:|:-:|
| `TOOLMESH_OIDC_ISSUER` | Issuer Keycloak, doit correspondre exactement au claim `iss` des tokens (`https://<keycloak>/realms/<realm>`) | ✔ | |
| `TOOLMESH_OIDC_AUDIENCE` | Audience attendue dans les tokens entrants du backend | ✔ | |
| `TOOLMESH_OIDC_CLIENT_ID` | Client confidentiel autorisé à faire du token exchange | ✔ | |
| `TOOLMESH_OIDC_CLIENT_SECRET` | **Secret** de ce client dans Keycloak | ✔ | |
| `TOOLMESH_BFF_CLIENT_ID` | Client confidentiel du login navigateur (code + PKCE), `toolmesh-bff` | ✔ | |
| `TOOLMESH_BFF_CLIENT_SECRET` | **Secret** de ce client dans Keycloak | ✔ | |
| `MCP_DATETIME_OIDC_ISSUER` | Issuer Keycloak du serveur MCP | | ✔ |
| `MCP_DATETIME_OIDC_AUDIENCE` | Audience attendue par le serveur MCP (`mcp-datetime`) | | ✔ |

Seuls `TOOLMESH_OIDC_CLIENT_SECRET` et `TOOLMESH_BFF_CLIENT_SECRET` sont réellement secrets ; les autres sont rangés avec lui pour que tout vienne d'une
seule source.

Exemple (CLI Vault) :

```bash
vault kv put exploration/dev/toolmesh/keycloak \
  TOOLMESH_OIDC_ISSUER="https://keycloak.example.org/realms/toolmesh" \
  TOOLMESH_OIDC_AUDIENCE="toolmesh" \
  TOOLMESH_OIDC_CLIENT_ID="toolmesh" \
  TOOLMESH_OIDC_CLIENT_SECRET="<secret du client Keycloak>" \
  TOOLMESH_BFF_CLIENT_ID="toolmesh-bff" \
  TOOLMESH_BFF_CLIENT_SECRET="<secret du client toolmesh-bff>" \
  MCP_DATETIME_OIDC_ISSUER="https://keycloak.example.org/realms/toolmesh" \
  MCP_DATETIME_OIDC_AUDIENCE="mcp-datetime"
```

Variables optionnelles à ajouter dans le même secret si Keycloak est joint par une autre adresse dans le cluster :
`TOOLMESH_OIDC_JWKS_URL`, `TOOLMESH_OIDC_TOKEN_URL`.

### `redis`

Sessions du login navigateur : le navigateur ne détient qu'un cookie opaque, les tokens restent dans Redis.

| Élément | Valeur |
|---|---|
| Chemin | `<global.vaultEnv>/toolmesh/redis` |
| `Secret` Kubernetes créé | `toolmesh-redis` |
| Lu par | `backend` et le Redis embarqué (`redis.auth.existingSecret`) |
| Clé à écrire | `REDIS_PASSWORD` |

L'opérateur construit lui-même `TOOLMESH_REDIS_URL` (`redis://:<mot de passe>@toolmesh-redis:6379/0`) à partir du mot de passe.

```bash
vault kv put exploration/dev/toolmesh/redis REDIS_PASSWORD="$(openssl rand -base64 32)"
```

### Configuration

Le chemin et le montage se règlent dans le fichier d'environnement (`global.vaultMount`, `global.vaultEnv`), le
`vaultAuthRef` (`vault-auth` par défaut) dans `extraObjects`.

## Comment ça arrive dans les pods

1. Les `VaultStaticSecret` `toolmesh-keycloak` et `toolmesh-redis` lisent leur chemin toutes les 60 s (`refreshAfter`).
2. Le Vault Secrets Operator crée les `Secret` Kubernetes correspondants.
3. Les pods les chargent via `envFrom`.
4. Si une valeur change dans Vault, les Deployments concernés sont redémarrés (`rolloutRestartTargets`).

## Renouveler le client secret

1. Régénérez le secret du client `toolmesh` dans Keycloak (onglet *Credentials*).
2. Mettez à jour `TOOLMESH_OIDC_CLIENT_SECRET` (ou `TOOLMESH_BFF_CLIENT_SECRET` pour le client `toolmesh-bff`) dans Vault (`vault kv patch ...`).
3. Attendez le prochain rafraîchissement : le backend redémarre tout seul.
4. Vérifiez : `kubectl rollout status deployment/toolmesh-backend -n <namespace>`.
