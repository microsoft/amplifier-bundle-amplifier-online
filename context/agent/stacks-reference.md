# Amplifier Online Stacks Reference

A **stack** is a reusable deployment blueprint that combines Infrastructure as Code (Bicep
templates), Azure resource provisioning, container orchestration, and default project
templates. Each stack knows how to provision, deploy, and destroy a specific type of workload.

**Key concept:** Stack vs Project
- **Stack** = the blueprint (e.g., `web-app-aca`) — shared, owned by the platform team
- **Project** = your specific application built on that blueprint — one per team/repo

---

## Selecting a Stack

Match your application's architecture to a stack using these criteria:

| Criteria | `web-app-aca` | `function-app` *(planned)* | `static-site` *(planned)* | `batch-job` *(planned)* |
|----------|:---:|:---:|:---:|:---:|
| Long-running HTTP service | ✅ | ❌ | ❌ | ❌ |
| Event-driven / HTTP triggers | ✅ | ✅ | ❌ | ❌ |
| Static files only | ✅ | ❌ | ✅ | ❌ |
| Scheduled / batch processing | ❌ | ❌ | ❌ | ✅ |
| Needs managed databases | ✅ | ⚠️ | ❌ | ⚠️ |
| Containerized workload | ✅ | ❌ | ❌ | ✅ |
| Entra ID auth (EasyAuth) | ✅ | ❌ | ❌ | ❌ |

**Currently available:** Only `web-app-aca` is live. Roadmap stacks (`function-app`,
`static-site`, `batch-job`, `aks-app`) are planned but not yet available. Frame selection
in architectural terms even when only one stack exists — this framing stays correct after
roadmap stacks land.

**How to see what's available:**
```bash
amplifier-online stacks
```

---

## Stack: `web-app-aca`

**Full name:** Web Application with Azure Container Apps

### What it provisions

- **Container Apps Environment** — shared, managed by the Platform
- **Frontend container app** — for React/Vue/static web (port 3000 or 80)
- **Backend container app** — for API service (port 8000 or custom)
- **Optional: PostgreSQL** (flexible server, shared with other projects)
- **Optional: Cosmos DB** (document database)
- **Optional: Redis** (cache)
- **Optional: ADLS Gen2 Storage** (blob/file storage)
- **Networking** — automatic DNS, TLS certificates, ingress rules
- **Authentication** — EasyAuth with Entra ID (per-project app registration)

### Best for

- Full-stack web applications (frontend + backend API)
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

### Stack-specific manifest fields

```yaml
name: my-project
stack: web-app-aca       # ← must exactly match this string

containers:
  api:                   # ← container name becomes the Azure Container App name
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000           # ← must match the port your API listens on
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 3000           # ← must match the port your web server listens on

resources:
  postgres:
    enabled: true        # ← provisions a database on the shared Postgres server
  cosmos:
    enabled: false
  redis:
    enabled: false
  storage:
    enabled: false
```

**Container naming conventions:**
- `api` → backend API service
- `web` → frontend / static server

You may use different names (e.g., `backend`, `frontend`), but `api` and `web` are the
generated defaults from `amplifier-online init`.

---

## Roadmap Stacks (Not Yet Available)

These are planned but not yet implemented. Do not attempt to use them — `amplifier-online stacks`
will not list them and `amplifier-online up` will fail with an unknown stack error.

| Stack | Description | Expected use case |
|-------|-------------|-------------------|
| `function-app` | Azure Functions with HTTP triggers | Event-driven, serverless APIs |
| `static-site` | Static web hosting with Azure CDN | React/Next.js static exports, documentation |
| `batch-job` | Azure Container Instances for scheduled jobs | ETL, nightly reports, data pipelines |
| `aks-app` | Kubernetes deployment on AKS | Complex microservices, custom networking |

---

## Switching Stacks

Stacks cannot be switched without destroying and re-deploying. Each stack has different
Azure resources, and there is no migration path between stacks.

```bash
amplifier-online destroy          # 1. Tear down current stack resources
# Edit amplifier-online.yaml      # 2. Change the stack: field and adjust containers/resources
amplifier-online up               # 3. Deploy with the new stack
```

**Warning:** `destroy` removes per-project resources including any databases. Back up data first.

---

## Multiple Projects, Same Stack

Many projects can run on `web-app-aca` simultaneously. Each project gets isolated Azure
resources — its own container apps, its own Entra app registration, its own database
(when enabled). The shared infrastructure (Container Apps Environment, ACR, Postgres server)
is shared at the infrastructure level, but project data is isolated.
