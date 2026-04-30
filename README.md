# pet

## Launch (only with Docker Desktop)

```sh
uv sync
docker compose up -d --build
```

## Run Tests

### Without Docker Desktop

```sh
uv sync
uv run pytest -m "not integration"
```

### With Docker Desktop

```sh
uv sync
uv run pytest
```

---

## OAuth 2.1 / OIDC Resource Server

This service is a **Resource Server** only:

* it accepts a Bearer **JWT access token** from the client;
* it never logs the user in, never holds the client secret, never performs
  redirects;
* it validates the token's signature against Keycloak's **JWKS** discovered
  through the RFC 8414 metadata endpoint, then enforces `iss`, `aud`/`azp`,
  `exp`, `nbf`, `iat` (with leeway) and a strict algorithm allow-list (RS256).

### Concepts (auth, scopes, realm vs client roles)

| Concept | Where it lives | Used for |
| --- | --- | --- |
| **Authentication** | Verified JWT signature + standard claims | "Who is the request from?" → `Principal` |
| **Scopes** | `scope` (space-separated) or `scp` (list) claim | OAuth-style coarse permissions, e.g. `organizations:read` |
| **Realm role** | `realm_access.roles[]` | Cross-cutting roles in the Keycloak realm, e.g. `admin` |
| **Client role** | `resource_access.<client_id>.roles[]` | Roles scoped to a specific Keycloak client (this service) |

### Required environment variables

See [`.env.example`](.env.example). Minimum for production:

```env
KEYCLOAK__ISSUER_URL=https://auth.example.com/realms/pet
KEYCLOAK__INTERNAL_ISSUER_URL=http://keycloak:8080/realms/pet
KEYCLOAK__CLIENT_ID=pet-backend
KEYCLOAK__AUDIENCE=pet-backend
KEYCLOAK__ALLOWED_ALGORITHMS=RS256
KEYCLOAK__JWKS_CACHE_TTL_SECONDS=300
KEYCLOAK__LEEWAY_SECONDS=30
KEYCLOAK__HTTP_TIMEOUT_SECONDS=5
```

Auth is always enforced. Local development runs against the real Keycloak
from `compose.dev.yaml`; tests inject a fake `TokenVerifier` via
`create_app(token_verifier=...)`.

### Manual Keycloak setup (admin console)

These steps are still relevant for non-local environments. The local
`docker compose` stack now imports a ready-to-use `ukawa-pet` realm
automatically.

1. Create a realm, e.g. `pet`.
2. Create a client `pet-backend` of type **OpenID Connect**, with
   *Client authentication* set so it issues access tokens (typically a public
   front-end client + a *bearer-only*-style backend, or a confidential client
   used only by your front-end). The Resource Server itself does not use the
   client secret.
3. Add **realm roles** (e.g. `admin`) and assign them to test users.
4. Under the client's **Roles** tab, add **client roles** (e.g. `manager`).
5. Under **Client scopes**, define the scopes you want to gate routes with
   (e.g. `organizations:read`, `organizations:write`) and assign them to the
   front-end client as default/optional scopes.
6. Optional but recommended: add an **audience mapper** on the front-end client
   so issued tokens carry `aud=pet-backend` (otherwise we accept the
   client_id via Keycloak's `azp` claim by default).

### Getting a token for local testing

For an existing user with the *Direct Access Grants* flow enabled on the client:

```sh
curl -s -X POST \
  "$KEYCLOAK__ISSUER_URL/protocol/openid-connect/token" \
  -d "grant_type=password" \
  -d "client_id=$KEYCLOAK__CLIENT_ID" \
  -d "username=alice" -d "password=alice" \
  | jq -r .access_token
```

### Calling a protected endpoint

```sh
TOKEN="$(./get-token.sh)"
curl -i -X POST http://localhost:8000/orgs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme"}'
```

Expected error responses:

| Cause | Status | `WWW-Authenticate` |
| --- | --- | --- |
| Missing/invalid header | 401 | `Bearer realm="pet", error="invalid_request"` |
| Bad signature / wrong issuer / expired | 401 | `Bearer realm="pet", error="invalid_token", error_description="..."` |
| Auth ok, missing scope/role | 403 | `Bearer realm="pet", error="insufficient_scope", error_description="..."` |

### Protecting routes in code

```python
from fastapi import APIRouter, Depends
from pet.api.auth import (
    CurrentPrincipal,
    require_scopes,
    require_realm_roles,
    require_client_roles,
)

router = APIRouter()

# 1) Just authenticated:
@router.get("/me")
async def me(principal: CurrentPrincipal):
    return {"sub": principal.subject, "username": principal.username}

# 2) Scope gate via dependencies (no extra arg in handler):
@router.post(
    "/orgs/",
    dependencies=[Depends(require_scopes("organizations:write"))],
)
async def create_org(...): ...

# 3) Realm role gate:
@router.delete(
    "/orgs/{id}",
    dependencies=[Depends(require_realm_roles("admin"))],
)
async def delete_org(...): ...

# 4) Client role gate (per-client roles in resource_access[<client_id>].roles):
@router.post(
    "/admin/sync",
    dependencies=[Depends(require_client_roles("pet-backend", "manager"))],
)
async def sync(...): ...
```

All checkers require **all** specified items to be present; combine multiple
`Depends` if a route needs both a scope and a role.
