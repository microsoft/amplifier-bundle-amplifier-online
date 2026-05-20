# Project Analysis Guide

This guide teaches you how to analyze a project directory to recommend the appropriate
Amplifier Online deployment stack. Use glob, grep, and read_file to detect patterns.

---

## Detection Strategy

Follow this sequence:

1. **Scan for Dockerfiles** → determines containerization status
2. **Detect frameworks** → identifies backend/frontend technologies
3. **Check GitHub integration** → determines if repo is GitHub-hosted
4. **Detect resource needs** → identifies database/cache/storage requirements
5. **Map to stack** → matches detected pattern to available stacks

---

## Step 1: Scan for Dockerfiles

```bash
glob("**/Dockerfile*")
```

**Patterns:**

| Found | Interpretation |
|-------|----------------|
| `./Dockerfile` only | Single-service containerized app |
| `./api/Dockerfile` + `./web/Dockerfile` | Classic backend + frontend split (both containerized) |
| `./backend/Dockerfile` + `./frontend/Dockerfile` | Classic split (different naming) |
| `./services/*/Dockerfile` | Microservices architecture |
| No Dockerfiles | Either static-only site OR needs Dockerfile creation |

---

## Step 2: Detect Backend Framework

**Python:**
```bash
glob("**/requirements.txt")
glob("**/pyproject.toml")
glob("**/setup.py")
```

Read and search for framework markers:
- `fastapi` → FastAPI (default port: 8000)
- `django` → Django (default port: 8000)
- `flask` → Flask (default port: 5000)
- `uvicorn` → ASGI server (usually FastAPI or Django async)

**Node/TypeScript:**
```bash
glob("**/package.json")
```

Read and search for:
- `"express"` → Express (default port: 3000)
- `"@nestjs/core"` → NestJS (default port: 3000)
- `"fastify"` → Fastify (default port: 3000)
- `"koa"` → Koa (default port: 3000)

**Go:**
```bash
glob("**/go.mod")
```

Read and search for:
- `github.com/gin-gonic/gin` → Gin
- `github.com/gorilla/mux` → Gorilla
- Backend framework presence (no specific port inference)

**Port Inference:**
- FastAPI/Django → Port 8000
- Flask → Port 5000
- Node/Express → Port 3000
- If uncertain, recommend user verifies port in manifest

---

## Step 3: Detect Frontend Framework

**React/Vue/Vite:**
```bash
glob("**/package.json")
```

Read and search for:
- `"react"` + `"@vitejs/plugin-react"` → Vite + React (output: `dist`)
- `"react"` + `"react-scripts"` → Create React App (output: `build`)
- `"vue"` + `"@vitejs/plugin-vue"` → Vite + Vue (output: `dist`)
- `"vue"` + `"@vue/cli-service"` → Vue CLI (output: `dist`)

**Next.js:**
```bash
glob("**/package.json")
```

Read and search for:
- `"next"` → Next.js
  - If SSR (default): Not suitable for static-web-app stack
  - If static export (`output: 'export'` in next.config.js): output directory is `out`

**Static HTML:**
```bash
glob("**/index.html")
```

If no package.json but HTML/CSS/JS files present → Pure static site

**Containerized vs Static:**
- Has `./web/Dockerfile` or `./frontend/Dockerfile` → Containerized frontend
- Has package.json + no Dockerfile + in GitHub → Static Web App candidate
- Pure HTML/CSS/JS + no Dockerfile → Static Web App

---

## Step 4: Check GitHub Integration

```bash
bash("git remote -v")
```

**Patterns:**
- Contains `github.com` → GitHub-hosted (required for static-web-app, web-app-awa frontend)
- No remote or non-GitHub remote → Cannot use Static Web App features
- Not a git repo → Not ready for Static Web App

**Extract repo URL:**
```
origin  https://github.com/org/repo.git (fetch)
```

Store: `github.com/org/repo`

---

## Step 5: Detect Resource Needs

**PostgreSQL:**
```bash
grep("psycopg2|asyncpg|pg|postgres|DATABASE_URL", path=".")
```

Markers:
- Python: `psycopg2`, `asyncpg` in requirements.txt
- Node: `pg`, `postgres` in package.json
- Environment variable references: `DATABASE_URL`, `POSTGRES_`

**MongoDB/Cosmos DB:**
```bash
grep("pymongo|mongodb|cosmosdb|@azure/cosmos", path=".")
```

Markers:
- Python: `pymongo` in requirements.txt
- Node: `mongodb`, `@azure/cosmos` in package.json

**Redis:**
```bash
grep("redis|aioredis|ioredis", path=".")
```

Markers:
- Python: `redis`, `aioredis` in requirements.txt
- Node: `ioredis`, `redis` in package.json

**Storage (File uploads, object storage):**
```bash
grep("boto3|azure-storage|@azure/storage-blob|multer|formidable", path=".")
```

Markers:
- Python: `boto3` (S3), `azure-storage-blob`
- Node: `@azure/storage-blob`, `multer` (file uploads), `formidable`

---

## Mapping: Project Pattern → Stack

### Pattern 1: Backend Container + Frontend Container

**Detected:**
- `./api/Dockerfile` or `./backend/Dockerfile`
- `./web/Dockerfile` or `./frontend/Dockerfile`
- Backend framework (FastAPI, Express, etc.)
- Frontend framework (React, Vue, etc.)

**Recommended Stack:** `web-app-aca`

**Reasoning:**
- Both backend and frontend are containerized
- web-app-aca provides internal networking between containers
- Container Apps Environment handles both

**Alternative:** `web-app-awa` IF frontend code is in GitHub and could be static
- Trade-off: Lose container-to-container networking
- Gain: Static Web App features (PR previews, GitHub integration)

---

### Pattern 2: Backend Container + Static Frontend (GitHub)

**Detected:**
- `./api/Dockerfile` or `./backend/Dockerfile`
- `./web/package.json` or `./frontend/package.json` (NO Dockerfile)
- Frontend is React/Vue/static build output
- Project is in GitHub

**Recommended Stack:** `web-app-awa`

**Reasoning:**
- Backend needs containerization (Azure Web App)
- Frontend can be deployed via Static Web App (GitHub integration, PR previews)
- Separation of backend and frontend deployment lifecycles

**Alternative:** `web-app-aca` IF you containerize the frontend
- Trade-off: Lose Static Web App features
- Gain: Internal networking, simpler single-stack deployment

---

### Pattern 3: Backend Only (API service, no frontend)

**Detected:**
- `./Dockerfile` or `./api/Dockerfile`
- Backend framework
- No frontend directory or files

**Recommended Stack:** `web-app-aca` (backend-only)

**Reasoning:**
- Pure API service
- Container Apps provides auto-scaling, ingress, health probes
- Can add frontend later without re-deploying backend

**Alternative:** `web-app-awa` (backend-only)
- Trade-off: Different compute platform (Azure Web App vs Container Apps)
- Gain: Easier to add Static Web App frontend later

---

### Pattern 4: Pure Static Site (No Backend)

**Detected:**
- No Dockerfiles
- `./package.json` with React/Vue/static framework OR pure HTML/CSS/JS
- No backend framework detected
- Project is in GitHub

**Recommended Stack:** `static-web-app`

**Reasoning:**
- No server-side logic needed
- Static Web App handles hosting, CDN, automatic deployments
- Built-in GitHub integration for PR previews
- Lowest cost (no containers)

**Not suitable if:**
- Needs server-side rendering (Next.js SSR, Nuxt SSR)
- Needs database access (no backend)
- Needs authentication beyond Static Web App's built-in auth

---

### Pattern 5: Microservices (Multiple Containers)

**Detected:**
- `./services/service1/Dockerfile`
- `./services/service2/Dockerfile`
- Multiple backend services

**Recommended Stack:** `web-app-aca`

**Reasoning:**
- Multiple containers need orchestration
- Container Apps Environment supports multiple apps
- Internal networking between services

**Not suitable for:** `web-app-awa` or `static-web-app` (single backend only)

---

### Pattern 6: No Dockerfiles (Needs Guidance)

**Detected:**
- Backend framework present (FastAPI, Express, etc.)
- No Dockerfiles

**Action:**
- Guide user to create Dockerfile(s) first
- Provide template Dockerfiles for detected framework
- Re-run analysis after Dockerfiles are created

**Do NOT recommend a stack yet** — containerization is a prerequisite for web-app-aca and web-app-awa.

---

## Analysis Output Format

Present findings in this structure:

```
PROJECT PROFILE

Backend: [FastAPI | Django | Flask | Express | NestJS | Go | None]
  - Dockerfile: [✅ path/to/Dockerfile | ❌ missing]
  - Framework evidence: [files/dependencies found]
  - Detected port: [8000 | 5000 | 3000 | unknown]

Frontend: [React (Vite) | React (CRA) | Vue | Next.js | Static HTML | None]
  - Dockerfile: [✅ path/to/Dockerfile | ❌ missing] (for container-based)
  - GitHub repo: [✅ github.com/org/repo | ❌ not in GitHub]
  - Framework evidence: [package.json dependencies]
  - Build output: [dist | build | out | n/a]

Resources Detected:
  - Database: [PostgreSQL | MongoDB/Cosmos | None]
  - Cache: [Redis | None]
  - Storage: [File uploads/object storage | None]

STACK RECOMMENDATION: [web-app-aca | web-app-awa | static-web-app]

Reasoning:
- [Why this stack matches the detected architecture]
- [Specific criteria from stacks-reference.md]
- [What resources to enable in manifest]

Alternative Options:
- [Other stacks that could work]
- [Trade-offs compared to recommended stack]
```

---

## Edge Cases

### Next.js with SSR

**Detected:**
- `"next"` in package.json
- No `output: 'export'` in next.config.js (or no next.config.js)

**Recommendation:**
- ❌ **NOT suitable for static-web-app** (SSR requires a server)
- ✅ Containerize Next.js (runs `next start` server)
- Use `web-app-aca` or `web-app-awa` with containerized frontend

### Monorepo (Multiple Apps in One Repo)

**Detected:**
- `./apps/api/` + `./apps/web/`
- Multiple package.json files

**Recommendation:**
- Analyze each app directory separately
- Create separate `amplifier-online.yaml` manifests OR
- Use a single manifest with multiple containers

### Frontend Not in GitHub

**Detected:**
- Static frontend (React/Vue)
- No GitHub remote OR non-GitHub remote (GitLab, Bitbucket)

**Recommendation:**
- ❌ Cannot use `static-web-app` stack (requires GitHub)
- ✅ Containerize the frontend (nginx serving static build)
- Use `web-app-aca` with containerized frontend

---

## Implementation Notes

**When running this analysis in the recipe:**

1. **Use glob first** — fastest way to find files
2. **Read package.json/requirements.txt** — get exact dependencies
3. **Use grep sparingly** — only for specific patterns in large codebases
4. **Store findings in context** — recipe stages pass this forward
5. **Don't guess** — if uncertain, present options and let user choose

**Common Pitfalls:**

- Assuming port without checking application code
- Recommending static-web-app for SSR frameworks
- Missing nested Dockerfiles in monorepos
- Not checking if GitHub integration exists before recommending static-web-app

---

## Related Documentation

For stack criteria details: @amplifier-online:context/agent/stacks-reference.md
For manifest schema: @amplifier-online:context/agent/manifest-schema.md
