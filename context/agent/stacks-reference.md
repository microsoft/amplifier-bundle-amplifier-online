# Amplifier Online Stacks Reference

A **stack** is a reusable deployment blueprint that combines Infrastructure as Code (Bicep
templates), Azure resource provisioning logic, container orchestration or static hosting
configuration, and default project templates. Each stack knows how to provision, deploy, and
destroy a specific type of workload.

**Key concept:** Stack vs Project
- **Stack** = the blueprint (e.g., `web-app-aca`) — shared, owned by the platform team
- **Project** = your specific application built on that blueprint — one per team/repo

---

## Selecting a Stack

Match your application's architecture to a stack using these criteria:

| Criteria | `web-app-aca` | `internal-service-aca` | `web-app-awa` | `static-web-app` |
|----------|:---:|:---:|:---:|:---:|
| Multi-container backend + frontend | ✅ | ❌ | ❌ | ❌ |
| Internal-only backend (no public ingress) | ❌ | ✅ | ❌ | ❌ |
| Single backend container + static frontend | ❌ | ❌ | ✅ | ❌ |
| Pure static site (no backend) | ❌ | ❌ | ❌ | ✅ |
| Persistent volumes | ✅ | ✅ | ✅ | ❌ |
| Needs managed databases | ✅ | ✅ | ✅ | ❌ |
| Container-to-container networking | ✅ | ✅ | ❌ | ❌ |
| GitHub-integrated CI/CD for frontend | ⚠️ | ❌ | ✅ | ✅ |
| PR preview deployments | ⚠️ | ❌ | ✅ | ✅ |
| Entra ID auth (EasyAuth on frontends) | ✅ | ❌ | ✅ | ✅ |
| JWT middleware (API token validation) | ✅ | ✅ | ✅ | ❌ |
| Service-to-service auth (managed identity) | ✅ | ✅ | ❌ | ❌ |

**All four stacks are production-ready and available now.**

**How to see what's available:**
```bash
amplifier-online stack list
```

Output:
```
Available deployment stacks:

  web-app-aca
    Azure Container Apps with Application Insights telemetry and optional Postgres, Cosmos, Redis, and Storage

  web-app-awa
    Azure Web App (Linux container backend) + Static Web App (frontend) with Application Insights telemetry and optional Postgres, Cosmos, Redis, and Storage

  internal-service-aca
    Internal-only Azure Container App — no public ingress, JWT/managed-identity auth, optional Postgres/Cosmos/Redis/Storage

  static-web-app
    Azure Static Web App with GitHub integration for pure static websites (no backend, no database - just static content)
```

---

## Stack: `web-app-aca`

**Full name:** Web Application with Azure Container Apps

### What it provisions

- **Container Apps Environment** — shared, managed by the Platform
- **Container apps** — one per service in the `services:` map (e.g., api, web, worker)
- **Optional: PostgreSQL** (flexible server, shared with other projects)
- **Optional: Cosmos DB** (document database)
- **Optional: Redis** (cache)
- **Optional: ADLS Gen2 Storage** (blob/file storage)
- **Networking** — automatic DNS, TLS certificates, ingress rules, container-to-container communication
- **Authentication** — EasyAuth on web frontends (RedirectToLoginPage, always enforced); JWT middleware on API backends (token validation). Two Entra registrations: `ao-{project}-client` (login/MSAL.js client) and `ao-{project}-api` (audience `api://{apiClientId}`, exposes `access_as_user` + APIM)
- **Observability** — Application Insights (workspace-based)

### Best for

- Full-stack web applications with both backend and frontend containers
- Applications needing container-to-container networking
- Applications needing managed databases
- Internal tools with Entra ID / SSO authentication
- Teams that want infrastructure fully managed

### Repo prerequisites (MUST verify before `amplifier-online up`)

1. **Dockerfiles exist** — one Dockerfile per planned container. The `web-app-aca` stack does
   NOT build images; it deploys pre-built images from ACR. If Dockerfiles don't exist or
   images haven't been built and pushed, the deployment will fail to pull the image.

   Use `glob` to verify:
   ```
   glob("**/Dockerfile*")
   ```

2. **Images are in ACR** — all `image:` values in the manifest MUST use ACR format:
   ```
   <acr-name>.azurecr.io/<project>-<service>:<tag>
   ```
   Docker Hub images (`nginx:latest`, `python:3.11`) will fail because the Container Apps
   Environment is not configured to pull from Docker Hub. ACR credentials are injected by
   the platform automatically.

3. **Build → Push sequence understood** — images must be built and pushed to ACR BEFORE
   running `amplifier-online up`. The CLI/service does not build images; it deploys whatever
   tag is in the manifest at the time of `up`. Use `az acr build` or Docker push directly.

4. **Health endpoints exist** — each container MUST expose `/health` that returns 200 OK.

### Stack-specific manifest fields

```yaml
name: my-project
stack: web-app-aca       # ← must exactly match this string

services:
  api:
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000           # ← must match the port your API listens on
    # API services never get EasyAuth — validate tokens via JWT middleware
    env:
      - name: LOG_LEVEL
        value: info
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 80             # ← must match the port your web server listens on
    # Web services always get EasyAuth (RedirectToLoginPage)
    auth_exclude: ["/api"]  # ← Don't intercept proxied API calls

resources:
  postgres:
    enabled: true        # ← provisions a database on the shared Postgres server
    sku: B_Gen5_1        # ← optional: Basic tier (default)
    storage_mb: 5120     # ← optional: 5 GB (default)
  cosmos:
    enabled: false
    throughput: 400      # ← optional: RU/s (default)
  redis:
    enabled: false
    sku: Basic           # ← optional: Basic tier (default)
    capacity: 0          # ← optional: C0 (250 MB, default)
  storage:
    enabled: false
    sku: Standard_LRS    # ← optional: Locally-redundant (default)
```

**Key concepts:**
- Uses `services:` map — keys are service names (any name works)
- **Web services** always get EasyAuth with `RedirectToLoginPage` — use `auth_exclude` for path exclusions (e.g., proxied API calls)
- **API services** never get EasyAuth — use JWT middleware (`jwt_middleware.py`) for token validation
- **Two Entra registrations, split by OAuth role:** `ao-{project}-client` (frontend login client) and `ao-{project}-api` (backend audience, `api://{apiClientId}`, exposes `access_as_user` + APIM since user-facing). Frontend gets `AZURE_CLIENT_ID` (the `-client`) + `AZURE_API_CLIENT_ID` (the `-api`, audience for `api://{AZURE_API_CLIENT_ID}/access_as_user`); backend gets `AZURE_CLIENT_ID` = the `-api`
- Volumes attach per-service (not under `resources`). When a volume is configured, the platform
  automatically enforces `maxReplicas=1` (single-instance mode). This is required for safe
  filesystem access over Azure Files (SMB). If using SQLite on a volume, see the
  `services.<name>.volume` section in the manifest schema for VFS and journal mode requirements.

---

## Stack: `web-app-awa`

**Full name:** Azure Web App (backend) + Azure Static Web App (frontend)

### What it provisions

- **Backend:** Azure Web App running a Linux container
- **Frontend:** Azure Static Web App with GitHub integration
- **Optional: PostgreSQL** (flexible server, shared with other projects)
- **Optional: Cosmos DB** (document database)
- **Optional: Redis** (cache)
- **Optional: ADLS Gen2 Storage** (blob/file storage)
- **Authentication:** EasyAuth on SWA frontend (login required, always enforced); JWT middleware on backend API (token validation). Two Entra registrations: `ao-{project}-client` (frontend login client) and `ao-{project}-api` (backend audience `api://{apiClientId}`, exposes `access_as_user` + APIM)
- **Observability:** Application Insights (workspace-based)

### Best for

- Applications where the frontend is a pure static site (React SPA, Vue, etc.)
- Teams wanting built-in GitHub Actions CI/CD for the frontend
- Apps that benefit from Static Web App's automatic PR preview deployments
- Separation of backend (containerized) and frontend (static) deployment lifecycle

### Repo prerequisites

**Backend:**
1. Dockerfile exists for backend container
2. Image pushed to ACR
3. Health endpoint at `/health` returns 200 OK

**Frontend:**
1. Code in GitHub repository (public or private)
2. Build configuration (package.json with build script)
3. Build output directory specified correctly

### Stack-specific manifest fields

```yaml
name: my-project
stack: web-app-awa       # ← must exactly match this string

services:                # ← backend container goes in services (same pattern as web-app-aca)
  api:
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000
    # API service — no EasyAuth, validates tokens via JWT middleware
    env:
      - name: LOG_LEVEL
        value: info

frontend:                # ← separate because Static Web App is not a container
  type: static-web-app   # ← distinguishes from container type
  repo: https://github.com/your-org/your-repo  # ← GitHub repo URL
  branch: main
  app_location: "/"              # ← path to frontend in repo (e.g., "/frontend" for monorepo)
  output_location: "dist"        # ← build output dir (must match vite/webpack config)
  build_command: "npm run build" # ← optional, defaults to "npm run build"
  protected: login               # ← always enforced — sign-in required

resources:
  postgres:
    enabled: true
  cosmos:
    enabled: false
  redis:
    enabled: false
  storage:
    enabled: false
```

**Important:** `output_location` must match your actual build output:
- Vite → `dist`
- Webpack → `dist` or `build`
- Next.js (static export) → `out`
- Create React App → `build`

**Key concepts:**
- Uses `services:` for the backend container (same pattern as `web-app-aca`) plus `frontend:` for the Static Web App.
- **API backend** never gets EasyAuth — use JWT middleware (`jwt_middleware.py`) for token validation.
- **SWA frontend** always gets authentication enforced via `staticwebapp.config.json` route rules (`protected: login`).
- **Two Entra registrations:** `ao-{project}-client` (frontend login) and `ao-{project}-api` (backend audience, `access_as_user` + APIM). Frontend gets `AZURE_CLIENT_ID` (the `-client`) + `AZURE_API_CLIENT_ID` (the `-api`); backend gets `AZURE_CLIENT_ID` = the `-api`.
- Volumes are supported on the API service. Add `volume` with `mount_path` and `size_gib`
  under `services.api:`. The `mount_path` **must** start with `/mounts/` (e.g., `/mounts/data`)
  — this is an Azure Web App platform requirement. The platform enforces single-instance
  mode when a volume is configured. If using SQLite on a volume, see the
  `services.<name>.volume` section in the manifest schema for VFS and journal mode
  requirements — the same Azure Files (SMB) guidance applies to both stacks.

### Frontend ↔ Backend Communication

Frontend calls backend via public URL. Backend MUST configure CORS to allow frontend origin:

```python
# FastAPI example
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.azurestaticapps.net",  # Production
        "http://localhost:5173"            # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Stack: `static-web-app`

**Full name:** Azure Static Web App (pure static hosting)

### What it provisions

- **Frontend:** Azure Static Web App with GitHub integration
- **Optional serverless API:** Azure Functions (if `api_location` specified)
- **Authentication:** EasyAuth with Entra ID (login always enforced via `staticwebapp.config.json` route rules). One Entra registration: `ao-{project}-client` ONLY (no `-api`, no `access_as_user`) — it calls external APIs (e.g. Microsoft Graph) with their own scopes
- **No databases:** This stack does not support PostgreSQL, Cosmos, Redis, or Storage

### Best for

- Pure static sites (HTML/CSS/JS, React SPA, Vue SPA)
- Documentation sites
- Portfolios and landing pages
- Applications with NO backend needs
- Teams wanting automatic PR preview deployments

### What this stack does NOT support

❌ Server-Side Rendering (SSR)
❌ Backend APIs (except optional serverless functions)
❌ Database access
❌ Server-side logic

**Need backend or SSR?** Use `web-app-aca` or `web-app-awa` instead.

### Repo prerequisites

1. Code in GitHub repository (public or private)
2. Build configuration (if using a framework with build step)
3. Build output directory specified correctly

### Stack-specific manifest fields

```yaml
name: my-static-site
stack: static-web-app    # ← must exactly match this string

frontend:
  type: static-web-app   # ← required for this stack
  repo: https://github.com/your-org/your-repo
  branch: main
  app_location: "/"              # ← path to source in repo
  output_location: "dist"        # ← build output directory
  build_command: "npm run build" # ← optional, defaults to "npm run build"
  api_location: "api"            # ← optional: serverless functions directory
  protected: login               # ← always enforced — sign-in required
```

**Frontend auth:**
- `protected: login` — always enforced. Sign-in required via `staticwebapp.config.json` route rules.
- The platform registers the `ao-{project}-client` login app (no `-api`) and injects auth env vars for MSAL.js. Token acquisition for external APIs (e.g. Microsoft Graph) uses those APIs' own scopes.

**Auth environment variables (SWA-specific):**

The `static-web-app` Bicep template injects two app settings into the SWA resource:

| SWA App Setting | Value | How your SPA reads it |
|-----------------|-------|----------------------|
| `VITE_AZURE_CLIENT_ID` | Entra app registration client ID | `import.meta.env.VITE_AZURE_CLIENT_ID` |
| `VITE_AZURE_TENANT_ID` | Entra tenant ID | `import.meta.env.VITE_AZURE_TENANT_ID` |

Azure SWA exposes app settings as environment variables during the Oryx build. Build tools like
Vite automatically bake `VITE_*` env vars into the JavaScript bundle via `import.meta.env`. This
means auth configuration is injected at **build time** (not runtime) — no `/auth-config.json`
fetch is needed for SWA-hosted SPAs.

**Your SPA code must use these exact names.** Using custom env var names (e.g.,
`VITE_MSAL_CLIENT_ID`) will result in empty strings at runtime because the platform only injects
the `VITE_AZURE_*` variants.

```typescript
// Correct: reads platform-injected values
const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
  },
};
```

> **Migrating from custom env var names?** If your app currently reads `VITE_MSAL_CLIENT_ID` or
> similar, update your config module to read `VITE_AZURE_CLIENT_ID` and `VITE_AZURE_TENANT_ID`
> instead. No changes to `amplifier-online.yaml` are needed — the platform handles injection.


**Existing `staticwebapp.config.json` reconciliation:**

When `amplifier-online init` detects an existing `staticwebapp.config.json`, it skips generation
to avoid overwriting user customizations. However, the existing config may be missing sections the
platform expects. **Always audit** the existing file against this checklist:

| Section | Required? | What to check |
|---------|-----------|---------------|
| `auth.identityProviders` | **Yes** | Must contain `azureActiveDirectory` with `openIdIssuer` (pinned to tenant) and `clientIdSettingName: "AZURE_CLIENT_ID"`. Without this, SWA falls back to its built-in multi-tenant AAD app — login is not pinned to the project's Entra registration or tenant. |
| `routes` | **Yes** | Must have `"route": "/*", "allowedRoles": ["authenticated"]` to enforce login. Explicitly unprotecting `/.auth/*` is a best practice. |
| `navigationFallback` | **Yes** (for SPAs) | Must rewrite to `index.html`. The `exclude` patterns should match the build tool's actual output (Vite uses `/assets/*`, not generic `/images/*`, `/css/*`, `/js/*`). |
| `responseOverrides` | Recommended | 401 → redirect to `/.auth/login/aad`. Adding `?post_login_redirect_uri=/` improves UX. |
| `globalHeaders` (CSP) | Recommended | If a CSP is present, verify `connect-src` includes `https://login.microsoftonline.com` (MSAL.js token requests) and `frame-src` includes `https://login.microsoftonline.com` (silent token renewal iframes). |

**The `auth.identityProviders` section** is the most commonly missing piece. The correct shape is:

```json
"auth": {
  "identityProviders": {
    "azureActiveDirectory": {
      "registration": {
        "openIdIssuer": "https://login.microsoftonline.com/{tenant-id}/v2.0",
        "clientIdSettingName": "AZURE_CLIENT_ID"
      }
    }
  }
}
```

The `clientIdSettingName` tells SWA to read the app setting named `AZURE_CLIENT_ID` (injected by
the Bicep template) and use it as the OAuth client ID for the built-in AAD login flow. The
`openIdIssuer` pins login to a specific tenant — without it, any Microsoft account can log in.

> **User configs are often better than platform-generated ones.** The platform generates a minimal
> `staticwebapp.config.json` with no security headers, generic exclude patterns, and no
> `post_login_redirect_uri`. When a user has invested in their config (custom CSP, refined routes,
> build-tool-specific excludes), preserve their customizations and only merge in the `auth` section.

### Optional Serverless API Functions

You can add serverless functions alongside your static site:

**Add an `api/` directory:**
```javascript
// api/hello.js
module.exports = async function (context, req) {
  return {
    body: { message: 'Hello from API' }
  };
};
```

**Call from frontend:**
```javascript
const response = await fetch('/api/hello');
const data = await response.json();
```

**Update manifest:**
```yaml
frontend:
  app_location: "/"
  api_location: "api"      # ← Add this for API functions
  output_location: "dist"
```

---

## Stack: `internal-service-aca`

**Full name:** Internal-Only Azure Container App

### What it provisions

- **Container App** -- single API container with `external: false` (internal-only ingress)
- **Container Apps Environment** -- shared, managed by the Platform (same CAE as `web-app-aca`)
- **Optional: PostgreSQL** (flexible server, shared with other projects)
- **Optional: Cosmos DB** (document database)
- **Optional: Redis** (cache)
- **Optional: ADLS Gen2 Storage** (blob/file storage)
- **Networking** -- internal DNS only (`<project>-api.internal.<env-default-domain>`), reachable only within the Container Apps Environment; no public FQDN
- **Authentication** -- no EasyAuth, no login client; one Entra registration `ao-{project}-api` (audience only, internal posture: no `access_as_user`, no APIM). Service-to-service auth via JWT middleware or managed identity tokens
- **Observability** -- Application Insights (workspace-based)

### Best for

- Backend microservices consumed by other services in the same Container Apps Environment
- Background workers and job processors
- Internal APIs that should never be exposed to the public internet
- Service-to-service architectures where callers authenticate via managed identity or JWT tokens

### What this stack does NOT support

- Public ingress (no browser-facing traffic)
- EasyAuth or CORS (no browser auth flows)
- Frontend containers or static web apps
- Login client (`-client`), MSAL.js, or SSO — only an audience-only `ao-{project}-api` registration (no `access_as_user`, no APIM)

**Need public access?** Use `web-app-aca` instead.

### Repo prerequisites (MUST verify before `amplifier-online up`)

1. **Dockerfile exists** -- one Dockerfile for the API container. The `internal-service-aca` stack
   does NOT build images; it deploys pre-built images from ACR. If the Dockerfile doesn't exist or
   the image hasn't been built and pushed, the deployment will fail to pull the image.

   Use `glob` to verify:
   ```
   glob("**/Dockerfile*")
   ```

2. **Image is in ACR** -- the `image:` value in the manifest MUST use ACR format:
   ```
   <acr-name>.azurecr.io/<project>-<service>:<tag>
   ```
   Docker Hub images will fail because the Container Apps Environment is not configured to pull
   from Docker Hub. ACR credentials are injected by the platform automatically.

3. **Build -> Push sequence understood** -- the image must be built and pushed to ACR BEFORE
   running `amplifier-online up`. The CLI/service does not build images.

4. **Health endpoint exists** -- the container MUST expose `/health` that returns 200 OK.

### Stack-specific manifest fields

```yaml
name: my-internal-service
stack: internal-service-aca   # <-- must exactly match this string

services:
  api:
    image: amplifieronlinecr.azurecr.io/my-internal-service-api:latest
    port: 8000               # <-- must match the port your API listens on
    # No EasyAuth, no login client; audience-only ao-{project}-api registration
    # Authenticate callers via JWT middleware or managed identity tokens
    env:
      - name: LOG_LEVEL
        value: info

resources:
  postgres:
    enabled: true            # <-- provisions a database on the shared Postgres server
  cosmos:
    enabled: false
  redis:
    enabled: false
  storage:
    enabled: false
```

**Key concepts:**
- Uses `services:` map -- single API service (no `web` or `frontend` service)
- **No EasyAuth, no CORS, no public FQDN** -- the container is only reachable within the CAE
- **Audience-only Entra registration** -- `ao-{project}-api` (no login client, no `access_as_user`, no APIM); no browser auth flows, callers authenticate via service-to-service patterns
- **Internal DNS** -- the container is reachable at `<project>-api.internal.<env-default-domain>` from other containers in the same CAE
- Volumes attach per-service (same as `web-app-aca`). When a volume is configured, the platform
  automatically enforces `maxReplicas=1` (single-instance mode).
- Same optional resources as `web-app-aca`: postgres, cosmos, redis, storage

---

## Roadmap Stacks (Not Yet Available)

These are planned but not yet implemented. Do not attempt to use them — `amplifier-online stack list`
will not list them and `amplifier-online up` will fail with an unknown stack error.

| Stack | Description | Expected use case |
|-------|-------------|-------------------|
| `function-app` | Azure Functions with HTTP triggers | Event-driven, serverless APIs |
| `batch-job` | Azure Container Instances for scheduled jobs | ETL, nightly reports, data pipelines |
| `aks-app` | Kubernetes deployment on AKS | Complex microservices, custom networking |

---

## Switching Stacks

Stacks cannot be switched without destroying and re-deploying. Each stack has different
Azure resources, and there is no migration path between stacks.

```bash
amplifier-online destroy          # 1. Tear down current stack resources
# Edit amplifier-online.yaml      # 2. Change the stack: field and adjust services/resources
amplifier-online up               # 3. Deploy with the new stack
```

**Warning:** `destroy` removes per-project resources including any databases. Back up data first.

---

## Multiple Projects, Same Stack

Many projects can run on the same stack simultaneously. Each project gets isolated Azure
resources -- its own container apps or web apps, its own Entra app registration (when applicable),
its own database (when enabled). The shared infrastructure (Container Apps Environment, ACR,
Postgres server) is shared at the infrastructure level, but project data is isolated.
