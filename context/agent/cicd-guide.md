# Amplifier Online CI/CD Guide

The `amplifier-online cicd create` command generates GitHub Actions workflow files that
automate the build → push → deploy cycle for your containers and/or static sites.

---

## What It Generates

Generated workflows depend on which stack you're using:

### For `web-app-aca` (Container Apps)

Generates two workflow files in `.github/workflows/`:

```
.github/workflows/
├── api-build-deploy.yaml    # Backend container build & deploy
└── web-build-deploy.yaml    # Frontend container build & deploy
```

Each workflow triggers on `push` to `main` when files in the container's source directory change,
plus a `workflow_dispatch` trigger for manual runs.

### For `web-app-awa` (Web App + Static Web App)

Generates two workflow files in `.github/workflows/`:

```
.github/workflows/
├── backend-build-deploy.yaml     # Backend container to Azure Web App
└── frontend-build-deploy.yaml    # Frontend to Static Web App
```

Backend workflow triggers on backend code changes; frontend workflow uses Static Web Apps Deploy action.

### For `internal-service-aca` (Internal Container App)

Generates one workflow file in `.github/workflows/`:

```
.github/workflows/
└── api-build-deploy.yaml    # API container build & deploy
```

Same container build pattern as `web-app-aca` but API service only -- no web workflow, no frontend deploy.

### For `static-web-app` (Static Site Only)

Generates one workflow file in `.github/workflows/`:

```
.github/workflows/
└── azure-static-web-apps.yaml    # Frontend to Static Web App
```

Uses Azure Static Web Apps Deploy action with automatic PR previews.

---

## Running the Command

**Always preview first:**
```bash
amplifier-online cicd create --dry-run    # Preview without writing files
```

**Generate for real:**
```bash
amplifier-online cicd create              # Writes to .github/workflows/
```

**Verify output:**
```bash
ls .github/workflows/
```

---

## Workflow Shapes by Stack

### Stack: `web-app-aca`

Both generated workflows (`api-build-deploy.yaml`, `web-build-deploy.yaml`) follow this pattern:

```
Trigger: push to main (path filter) or workflow_dispatch
  ↓
1. Checkout repository
2. Set up Docker Buildx
3. Azure login (OIDC — no stored passwords)
4. Log in to Azure Container Registry (az acr login)
5. Build Docker image (with SHA tag + latest tag)
6. Push both tags to ACR
7. Update Container App (az containerapp update --image <SHA-tagged-image>)
8. Health check (curl FQDN/health with retries)
```

**Key design choices:**
- Uses **OIDC federated credentials** — no long-lived secrets, no stored service principal passwords
- Builds with **two tags**: `<image>:<sha>` for traceability AND `<image>:latest` for convenience
- Deploys the **SHA-tagged** image for determinism (not `:latest`)
- Adds a **revision suffix** from git SHA + run number for easy rollback identification
- Runs a **health check** after deploy to fail fast on broken deployments

### Stack: `internal-service-aca`

Single generated workflow (`api-build-deploy.yaml`) follows the same pattern as `web-app-aca` API workflows:

```
Trigger: push to main (path filter) or workflow_dispatch
  |
1. Checkout repository
2. Set up Docker Buildx
3. Azure login (OIDC -- no stored passwords)
4. Log in to Azure Container Registry (az acr login)
5. Build Docker image (with SHA tag + latest tag)
6. Push both tags to ACR
7. Update Container App (az containerapp update --image <SHA-tagged-image>)
8. Health check (curl internal endpoint/health with retries)
```

**Key difference from `web-app-aca`:** Only one workflow (API only) -- no web/frontend workflow generated.

### Stack: `web-app-awa`

**Backend workflow (`backend-build-deploy.yaml`):**

```
Trigger: push to main (backend path filter) or workflow_dispatch
  ↓
1. Checkout repository
2. Set up Docker Buildx
3. Azure login (OIDC)
4. Log in to Azure Container Registry
5. Build Docker image
6. Push to ACR
7. Update Azure Web App (az webapp config container set)
8. Health check (curl backend FQDN/health with retries)
```

**Frontend workflow (`frontend-build-deploy.yaml`):**

```
Trigger: push to main (frontend path filter), pull_request (for PR previews), or workflow_dispatch
  ↓
1. Checkout repository
2. Azure Static Web Apps Deploy action
   - Builds frontend (npm run build)
   - Deploys to Static Web App
   - Creates PR preview environments
3. Cleanup on PR close
```

### Stack: `static-web-app`

**Single workflow (`azure-static-web-apps.yaml`):**

```
Trigger: push to main, pull_request (for PR previews), or workflow_dispatch
  ↓
1. Checkout repository
2. Azure Static Web Apps Deploy action
   - Builds static site
   - Deploys to Static Web App
   - Creates PR preview environments
3. Cleanup on PR close
```

---

## Required GitHub Secrets

After generating workflows, set these secrets in your GitHub repository.

### For all container-based stacks (`web-app-aca`, `internal-service-aca`, `web-app-awa` backend)

Navigate to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret | What it is | How to find it |
|--------|-----------|----------------|
| `AZURE_CLIENT_ID` | Client ID of the Entra app registration with federated credentials | Azure portal → App Registrations → your app → Application (client) ID |
| `AZURE_TENANT_ID` | Tenant ID of your Azure AD directory | Azure portal → Entra ID → Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription containing your resources | Azure portal → Subscriptions |

**Set via GitHub CLI:**
```bash
gh secret set AZURE_CLIENT_ID --body "<value>"
gh secret set AZURE_TENANT_ID --body "<value>"
gh secret set AZURE_SUBSCRIPTION_ID --body "<value>"
```

**Or via GitHub UI:** Settings → Secrets and variables → Actions → New repository secret

### For Static Web App deployments (`web-app-awa` frontend, `static-web-app`)

Add this additional secret:

```
AZURE_STATIC_WEB_APPS_API_TOKEN  # Get from Azure Portal (Static Web App → Manage deployment token)
```

**How to get the token:**
1. Azure Portal → Static Web App → Overview
2. Click **Manage deployment token**
3. Copy and add to GitHub repository secrets

---

## Federated Credentials Setup

The container workflows use OIDC, which requires a federated credential on the Entra app registration.

**Verify the federated credential exists:**
```bash
az ad app federated-credential list --id <client-id>
```

The credential should be configured for your GitHub organization/repo and the `main` branch.
If it's missing, the platform operator sets this up as part of platform provisioning — the
`setup-identity.sh` script creates the `ao-provisioner` app registration with federated
credentials. For per-project app registrations, `amplifier-online up` handles this automatically.

---

## Path Filters

Each workflow only triggers when files in its relevant directory change:

### `web-app-aca` workflows

```yaml
# api-build-deploy.yaml
on:
  push:
    branches:
      - main
    paths:
      - 'api/**'    # ← Only triggers when api/ directory changes

# web-build-deploy.yaml
on:
  push:
    branches:
      - main
    paths:
      - 'web/**'    # ← Only triggers when web/ directory changes
```

The path filter value comes from your project structure. If your API code is in
`backend/` rather than `api/`, update the path filter in the generated workflow.

### `internal-service-aca` workflow

```yaml
# api-build-deploy.yaml
on:
  push:
    branches:
      - main
    paths:
      - 'api/**'    # <-- Only triggers when api/ directory changes
```

### `web-app-awa` workflows

```yaml
# backend-build-deploy.yaml
on:
  push:
    branches:
      - main
    paths:
      - 'backend/**'    # ← Backend directory

# frontend-build-deploy.yaml
on:
  push:
    branches:
      - main
    paths:
      - 'frontend/**'   # ← Frontend directory
  pull_request:
    branches:
      - main
    paths:
      - 'frontend/**'
```

### `static-web-app` workflow

```yaml
# azure-static-web-apps.yaml
on:
  push:
    branches:
      - main
  pull_request:
    types: [opened, synchronize, reopened, closed]
    branches:
      - main
```

---

## Workflow Variables Reference

Generated workflows use environment variables to identify target resources:

### `web-app-aca`

```yaml
env:
  CONTAINER_APP_NAME: <project-name>-api    # Azure Container App to update
  RESOURCE_GROUP: amplifier-online-rg       # From ~/.amplifier-online/config.yaml
  ACR_NAME: amplifieronlinecr               # From ~/.amplifier-online/config.yaml
  IMAGE_NAME: amplifieronlinecr.azurecr.io/<project-name>-api
```

### `internal-service-aca`

```yaml
env:
  CONTAINER_APP_NAME: <project-name>-api    # Azure Container App to update
  RESOURCE_GROUP: amplifier-online-rg       # From ~/.amplifier-online/config.yaml
  ACR_NAME: amplifieronlinecr               # From ~/.amplifier-online/config.yaml
  IMAGE_NAME: amplifieronlinecr.azurecr.io/<project-name>-api
```

### `web-app-awa` (backend)

```yaml
env:
  WEB_APP_NAME: <project-name>-api          # Azure Web App name
  RESOURCE_GROUP: amplifier-online-rg
  ACR_NAME: amplifieronlinecr
  IMAGE_NAME: amplifieronlinecr.azurecr.io/<project-name>-api
```

### `web-app-awa` and `static-web-app` (frontend)

```yaml
env:
  AZURE_STATIC_WEB_APPS_API_TOKEN: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
  # Other configuration comes from amplifier-online.yaml
```

---

## First-Time Setup Checklist

After running `amplifier-online cicd create`:

### For `web-app-aca`, `internal-service-aca`, and `web-app-awa` (backend)

- [ ] Set `AZURE_CLIENT_ID` secret in GitHub
- [ ] Set `AZURE_TENANT_ID` secret in GitHub
- [ ] Set `AZURE_SUBSCRIPTION_ID` secret in GitHub
- [ ] Verify federated credential exists on the Entra app registration
- [ ] Confirm path filters in workflows match your actual source directory layout
- [ ] Ensure `amplifier-online up` has been run at least once (container apps/web apps must exist before
      `az containerapp update` or `az webapp config` can run)
- [ ] Verify a health endpoint exists at `/health` on each backend container (workflows health-check this)

### For `web-app-awa` and `static-web-app` (frontend)

- [ ] Set `AZURE_STATIC_WEB_APPS_API_TOKEN` secret in GitHub
- [ ] Get token from Azure Portal → Static Web App → Manage deployment token
- [ ] Confirm `output_location` in `amplifier-online.yaml` matches your build tool's actual output
- [ ] Verify GitHub repository URL in `amplifier-online.yaml` is correct
- [ ] Test build locally: `npm run build` produces files in the expected output directory

---

## Idempotency and Re-running

- Running `amplifier-online cicd create` again regenerates the workflows from the current manifest
- Changes to stack, service images, or frontend repo in `amplifier-online.yaml` → regenerate workflows
- Workflow files can be committed to git; treat them as generated but version-controlled

---

## Troubleshooting CI/CD Failures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `OIDC: Could not fetch access token` | Missing or wrong federated credential | Verify credential via `az ad app federated-credential list` |
| `ACR login failed` | AZURE_CLIENT_ID secret missing or wrong | Re-set secret in GitHub |
| `az containerapp update: not found` | Container App doesn't exist yet (web-app-aca or internal-service-aca) | Run `amplifier-online up` first |
| `az webapp config: not found` | Azure Web App doesn't exist yet | Run `amplifier-online up` first |
| `Health check failed` | App crashed after deploy or no /health endpoint | Check `amplifier-online logs --container api` |
| Workflow not triggering | Path filter doesn't match changed files | Update path filter in workflow YAML |
| Static Web App build fails | `output_location` wrong or build command fails | Test build locally; verify `output_location` matches actual output |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` invalid | Token expired or wrong | Get new token from Azure Portal |

---

## PR Preview Deployments

### For `web-app-awa` and `static-web-app` frontends

The generated frontend workflows automatically create preview deployments for pull requests:

**What happens:**
1. Open a PR → Azure Static Web Apps creates a preview environment
2. Preview URL: `https://<your-site>-<pr-number>.azurestaticapps.net`
3. Push new commits → Preview updates automatically
4. Close/merge PR → Preview environment deleted automatically

**No additional configuration needed** — this is built into Azure Static Web Apps Deploy action.

### For `web-app-aca`, `internal-service-aca`, and backend containers

PR previews are NOT generated automatically. Backend containers deploy only from `main` branch.

If you want PR previews for containers, you would need to:
1. Extend the workflow to create separate Container Apps or Web Apps per PR
2. Add cleanup steps when PR closes
3. Manage per-PR resources (databases, etc.) if needed

This is beyond the default generated workflows but can be customized.

---

## Related Documentation

For more details on deployment configuration:
- [Stack Users Guide](../stack-users-guide.md) - Complete guide for all stacks
- [Manifest Schema](manifest-schema.md) - Project configuration reference
- [CLI Reference](cli-reference.md) - All CLI commands including `cicd create`
