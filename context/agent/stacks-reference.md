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

| Criteria | `web-app-aca` | `web-app-awa` | `static-web-app` |
|----------|:---:|:---:|:---:|
| Multi-container backend + frontend | ✅ | ❌ | ❌ |
| Single backend container + static frontend | ❌ | ✅ | ❌ |
| Pure static site (no backend) | ❌ | ❌ | ✅ |
| Persistent volumes | ✅ | ✅ | ❌ |
| Needs managed databases | ✅ | ✅ | ❌ |
| Container-to-container networking | ✅ | ❌ | ❌ |
| GitHub-integrated CI/CD for frontend | ⚠️ | ✅ | ✅ |
| PR preview deployments | ⚠️ | ✅ | ✅ |
| Entra ID auth (EasyAuth) | ✅ | ✅ | ✅ |

**All three stacks are production-ready and available now.**

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
- **Authentication** — EasyAuth with Entra ID (per-project app registration)
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
    protected: validate  # ← validate (401) | login (redirect) | false (no auth)
    env:
      - name: LOG_LEVEL
        value: info
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 80             # ← must match the port your web server listens on
    protected:           # ← EasyAuth forces sign-in for this service
      mode: login
      exclude: ["/api"]  # ← Don't intercept proxied API calls

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
- Per-service `protected` field controls EasyAuth: `validate`, `login`, or `false` (shorthand string), or an object with `mode` + `exclude` for path exclusions
- Per-service `auth` field (implied when protected) controls Entra identity
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
- **Authentication:** EasyAuth with Entra ID (per-project app registration)
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
  protected: login               # ← login (require sign-in) | false (no auth, default)
  # auth: true                   # ← implied by protected: login; set explicitly for MSAL.js without sign-in enforcement

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
- Frontend supports `protected` (`login` or `false`) and `auth` fields — same pattern as services, but enforced via `staticwebapp.config.json` route rules instead of EasyAuth sidecar. The orchestrator checks both services and frontend when deciding whether to create an Entra app registration.
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
- **Authentication:** EasyAuth with Entra ID (per-project app registration)
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
  protected: false               # ← login (require sign-in) | false (no auth, default)
  # auth: true                   # ← set explicitly for MSAL.js token acquisition without sign-in enforcement
```

**Frontend auth options:**
- `protected: login` — require sign-in (configures route-level auth via `staticwebapp.config.json`)
- `protected: false` — no authentication (default)
- `auth: true` — register Entra app and inject `AZURE_CLIENT_ID` for MSAL.js token acquisition (implied when `protected: login`)

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
resources — its own container apps or web apps, its own Entra app registration, its own database
(when enabled). The shared infrastructure (Container Apps Environment, ACR, Postgres server)
is shared at the infrastructure level, but project data is isolated.
