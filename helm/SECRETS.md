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

Deux secrets KV v2. Le premier, `keycloak`, est lu par le backend et le MCP ; le second, `redis`, par le backend.

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
| `TOOLMESH_KEYCLOAK_URL` | URL de Keycloak, **sans** `/realms/...` (`https://<keycloak>`). Le backend s'en sert pour joindre Keycloak et le navigateur pour s'y connecter | ✔ | |
| `TOOLMESH_KEYCLOAK_CLIENT_SECRET` | **Secret** du client `toolmesh` (login navigateur, grants password/refresh, token exchange) | ✔ | |
| `MCP_DATETIME_OIDC_ISSUER` | Issuer Keycloak du serveur MCP (`https://<keycloak>/realms/<realm>`) | | ✔ |
| `MCP_DATETIME_OIDC_AUDIENCE` | Audience attendue par le serveur MCP (`mcp-datetime`) | | ✔ |

Le realm (`TOOLMESH_KEYCLOAK_REALM`) et le client (`TOOLMESH_KEYCLOAK_CLIENT_ID`, `toolmesh`) ne sont pas secrets :
ils sont dans `backend.env` de [`values/common-values.yaml`](values/common-values.yaml), comme pour Muffin. L'issuer
du backend en est déduit (`<URL>/realms/<realm>`) et doit correspondre exactement au claim `iss` des tokens :
`MCP_DATETIME_OIDC_ISSUER` doit donc valoir la même chose.

Seul `TOOLMESH_KEYCLOAK_CLIENT_SECRET` est réellement secret ; les autres sont rangés avec lui pour que tout vienne d'une
seule source.

Exemple (CLI Vault) :

```bash
vault kv put exploration/dev/toolmesh/keycloak \
  TOOLMESH_KEYCLOAK_URL="https://keycloak.example.org" \
  TOOLMESH_KEYCLOAK_CLIENT_SECRET="<secret du client Keycloak toolmesh>" \
  MCP_DATETIME_OIDC_ISSUER="https://keycloak.example.org/realms/toolmesh" \
  MCP_DATETIME_OIDC_AUDIENCE="mcp-datetime"
```

Variable optionnelle à ajouter dans `backend.env` si le navigateur joint Keycloak par une autre adresse que le
backend : `TOOLMESH_KEYCLOAK_PUBLIC_URL`.

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
2. Mettez à jour `TOOLMESH_KEYCLOAK_CLIENT_SECRET` dans Vault (`vault kv patch ...`).
3. Attendez le prochain rafraîchissement : le backend redémarre tout seul.
4. Vérifiez : `kubectl rollout status deployment/toolmesh-backend -n <namespace>`.
