# Amplifier Online CI/CD Guide

The `amplifier-online cicd create` command generates GitHub Actions workflow files that
automate the build → push → deploy cycle for your containers.

---

## What It Generates

For the `web-app-aca` stack, `cicd create` writes two workflow files to `.github/workflows/`:

```
.github/workflows/
├── <project-name>-api-build-deploy.yaml    # API container build & deploy
└── <project-name>-web-build-deploy.yaml    # Web container build & deploy
```

Each workflow triggers on `push` to `main` when files in the container's source directory change,
plus a `workflow_dispatch` trigger for manual runs.

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

## Workflow Shape

Both generated workflows follow the same pattern:

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

---

## Required GitHub Secrets

After generating workflows, set these three secrets in your GitHub repository:

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

---

## Federated Credentials Setup

The workflows use OIDC, which requires a federated credential on the Entra app registration.

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

Each workflow only triggers when files in its container's directory change:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'api/**'    # ← Only triggers when api/ directory changes
```

The path filter value comes from the container name in your manifest. If your API code is in
`backend/` rather than `api/`, update the path filter in the generated workflow.

---

## Workflow Variables Reference

Generated workflows use these environment variables:

```yaml
env:
  CONTAINER_APP_NAME: <project-name>-api    # Azure Container App to update
  RESOURCE_GROUP: amplifier-online-rg       # From ~/.amplifier-online/config.yaml
  ACR_NAME: amplifieronlinecr               # From ~/.amplifier-online/config.yaml
  IMAGE_NAME: amplifieronlinecr.azurecr.io/<project-name>-api
```

---

## First-Time Setup Checklist

After running `amplifier-online cicd create`:

- [ ] Set `AZURE_CLIENT_ID` secret in GitHub
- [ ] Set `AZURE_TENANT_ID` secret in GitHub
- [ ] Set `AZURE_SUBSCRIPTION_ID` secret in GitHub
- [ ] Verify federated credential exists on the Entra app registration
- [ ] Confirm path filters in workflows match your actual source directory layout
- [ ] Ensure `amplifier-online up` has been run at least once (container apps must exist before
      `az containerapp update` can run)
- [ ] Verify a health endpoint exists at `/health` on each container (the workflow health-checks this)

---

## Idempotency and Re-running

- Running `amplifier-online cicd create` again regenerates the workflows from the current manifest
- Changes to container names or project name in `amplifier-online.yaml` → regenerate workflows
- Workflow files can be committed to git; treat them as generated but version-controlled

---

## Troubleshooting CI/CD Failures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `OIDC: Could not fetch access token` | Missing or wrong federated credential | Verify credential via `az ad app federated-credential list` |
| `ACR login failed` | AZURE_CLIENT_ID secret missing or wrong | Re-set secret in GitHub |
| `az containerapp update: not found` | Container App doesn't exist yet | Run `amplifier-online up` first |
| `Health check failed` | App crashed after deploy or no /health endpoint | Check `amplifier-online logs --container api` |
| Workflow not triggering | Path filter doesn't match changed files | Update path filter in workflow YAML |
