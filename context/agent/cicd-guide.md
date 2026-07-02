# Amplifier Online CI/CD Guide

`amplifier-online cicd create` generates GitHub Actions workflow files that automate the
build → push → deploy cycle for your containers and/or static sites.

> **Container CI/CD is push-to-deploy, not `az`-based.** Container and Web-App stacks do **not**
> run `az acr login` / `az containerapp update` and do **not** need `AZURE_CLIENT_ID` /
> `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` secrets or an Entra federated credential. The workflow
> builds and pushes the image to **GitHub Container Registry (ghcr.io)**, then calls the
> **provisioner service** over HTTPS, authenticating with a **GitHub Actions OIDC token**. The
> provisioner validates the token, imports the image into ACR, and rolls the deployment. Only
> **Static Web App** frontends use a stored secret (`AZURE_STATIC_WEB_APPS_API_TOKEN`).

---

## How Container CI/CD Works

```
push to main (path filter)          ┌──────────────────────────────────────────┐
        │                           │            Provisioner service             │
        ▼                           │                                            │
┌───────────────┐  build job        │  1. Validate GitHub OIDC token             │
│ GitHub Actions │  ───────────────▶ │     (JWKS sig, issuer, aud, exp)           │
│                │  push image to    │  2. Authorize: OIDC claims vs RG tags      │
│  build + push  │  ghcr.io          │     repository_id == ao-deploy-repo-id     │
│  ───────────▶  │                   │     ref/environment == ao-deploy-ref/-env  │
│  deploy job    │  OIDC token +     │  3. Import ghcr.io image → ACR             │
│  POST /deploy ─┼──────────────────▶│  4. stack.deploy_image (roll revision)     │
└───────────────┘  Bearer $OIDC      └──────────────────────────────────────────┘
```

- **Build** (`build` job): log in to `ghcr.io` with the built-in `GITHUB_TOKEN`, build and push
  `:<sha>` + `:latest`, scan with **Trivy** (fails on CRITICAL/HIGH), generate an **SBOM**, and
  **attest build provenance**. No Azure credentials are used here.
- **Deploy** (`deploy` job, `environment: production`): mint a GitHub OIDC token for the
  provisioner's audience, then `POST` the image reference + manifest to the provisioner. The
  provisioner authenticates the token and authorizes the deploy against resource-group tags — there
  is **no long-lived Azure credential in GitHub at all** for container stacks.

Why this shape: the Microsoft tenant blocks client secrets, and per-repo Entra federated credentials
were fragile (they required the repo to live in a tenant-linked GitHub Enterprise org). Trusting
GitHub's OIDC directly at the provisioner removes both the secret and the federation requirement.

---

## What It Generates

Generated workflows depend on the stack:

| Stack | Files in `.github/workflows/` | Deploy mechanism |
|-------|-------------------------------|------------------|
| `web-app-aca` | `api-build-deploy.yaml`, `web-build-deploy.yaml` | ghcr.io + OIDC → provisioner (both containers) |
| `internal-service-aca` | `api-build-deploy.yaml` | ghcr.io + OIDC → provisioner |
| `web-app-awa` | `backend-build-deploy.yaml`, `frontend-build-deploy.yaml` | backend: ghcr.io + OIDC → provisioner; frontend: SWA deploy action |
| `static-web-app` | `azure-static-web-apps.yaml` | SWA deploy action (token) |

Container images are named by service: `ghcr.io/<owner>/<repo>-api`, `-web`, or `-backend`.

---

## Running the Command

**Always preview first:**
```bash
amplifier-online cicd create --dry-run    # Lists the workflows it would generate; writes nothing
```

**Generate for real:**
```bash
amplifier-online cicd create              # Writes .github/workflows/, enrolls the repo, sets GH secrets/vars
```

`cicd create` does three things:
1. **Detects the repo** via the `gh` CLI (`gh repo view`) — its `nameWithOwner` and numeric
   `repository_id` — and reads the manifest's `deploy:` block for `ref`/`environment`.
2. **Calls the provisioner**, which renders the workflow files and (best-effort) writes the deploy
   **binding tags** onto the project's resource group.
3. **Writes the workflow files** and **sets the GitHub repository secrets and variables for you**
   via `gh secret set` / `gh variable set`. If `gh` isn't installed or authenticated, it prints the
   exact commands to run instead.

**Prerequisites:** `gh` installed and authenticated (`gh auth status`), run from inside the git repo
that has a GitHub remote.

---

## Enrollment: Binding Tags

Authorization is anchored to tags the provisioner writes on the project resource group (`ao-<name>-rg`)
during `cicd create`:

| Tag | Value | Checked against OIDC claim |
|-----|-------|----------------------------|
| `ao-deploy-repo-id` | Numeric GitHub repository ID | `repository_id` (must match) |
| `ao-deploy-ref` | Git ref, e.g. `refs/heads/main` | `ref` (this **or** environment must match) |
| `ao-deploy-environment` | GitHub environment name, if set | `environment` (this **or** ref must match) |
| `ao-deploy-repo` | `owner/repo` (informational) | — |

Using the numeric `repository_id` (not the name) means renaming or transferring the repo does not
silently re-authorize a different repository. To change which repo/ref may deploy, edit the manifest's
`deploy:` block and re-run `cicd create`.

---

## Container Workflow Shape (`web-app-aca`, `internal-service-aca`, `web-app-awa` backend)

```
Trigger: push to main (path filter) or workflow_dispatch

build job  (permissions: id-token: write, contents: read, packages: write, attestations: write)
  1. Checkout
  2. Set up Docker Buildx
  3. Log in to ghcr.io  (username: github.actor, password: secrets.GITHUB_TOKEN)
  4. Build & push  ghcr.io/<owner>/<repo>-<svc>:<sha>  and  :latest   (registry buildcache)
  5. Trivy scan (severity CRITICAL,HIGH — fails the build on findings)
  6. Generate SBOM (anchore)
  7. Attest build provenance (pushed to the registry)

deploy job  (needs: build, environment: production, permissions: id-token: write, contents: read)
  1. Checkout
  2. Get OIDC token:  core.getIDToken('${{ vars.AO_PROVISIONER_AUDIENCE }}')
  3. POST ${{ vars.AO_PROVISIONER_URL }}/deploy/projects/${{ vars.AO_PROJECT_NAME }}
       Authorization: Bearer <oidc-token>
       body: { image, service, ghcr_token, manifest }   # manifest = amplifier-online.yaml as JSON
```

- The deploy is **stateless**: the workflow sends the checked-out `amplifier-online.yaml` (as JSON) in
  the request body, so the provisioner needs no server-side copy of the manifest.
- `ghcr_token` (the run's `GITHUB_TOKEN`) lets the provisioner pull the image from ghcr.io to import
  it into ACR. The deployed image is the **SHA-tagged** one for determinism.
- There is **no `az` CLI, no ACR login, and no `az containerapp/webapp` call** in these workflows.

## SWA Workflow Shape (`static-web-app`, `web-app-awa` frontend)

```
Trigger: push to <branch>, pull_request (opened/synchronize/reopened/closed), or workflow_dispatch

build_and_deploy_job:
  1. Checkout (submodules: true)
  2. Azure/static-web-apps-deploy@v1
       azure_static_web_apps_api_token: secrets.AZURE_STATIC_WEB_APPS_API_TOKEN
       repo_token: secrets.GITHUB_TOKEN
       env VITE_AZURE_CLIENT_ID / VITE_AZURE_API_CLIENT_ID / VITE_AZURE_TENANT_ID / VITE_AO_CONSUMES
           (from vars.*, injected at build time)
close_pull_request_job (on PR close): tears the preview environment down
```

This is the one stack family that authenticates with a stored **secret** rather than the provisioner
OIDC path, and the one that gets automatic **PR preview** environments.

---

## Secrets and Variables

`cicd create` sets these for you (via `gh`); the tables document what ends up in the repo.

### Secrets

| Secret | When | Source |
|--------|------|--------|
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Projects with an SWA frontend (`static-web-app`, `web-app-awa`) | Fetched live from the deployed SWA via ARM. Only available **after `amplifier-online up`** has created the SWA — if you run `cicd create` before the first `up`, it prints a note; re-run `cicd create` afterward. |

**Container-only projects need no secrets.** There is no `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/
`AZURE_SUBSCRIPTION_ID` deploy secret and no federated credential — the built-in `GITHUB_TOKEN`
(ghcr push) plus the run's OIDC token (provisioner deploy) are all the container path uses.

### Variables (`vars.*`, not secrets)

| Variable | When | What it is |
|----------|------|------------|
| `AO_PROVISIONER_URL` | Projects with container services | Base URL the deploy job POSTs to |
| `AO_PROVISIONER_AUDIENCE` | Projects with container services | Expected `aud` of the GitHub OIDC token |
| `AO_PROJECT_NAME` | Projects with container services | Project name → deploy path + resource group |
| `AZURE_TENANT_ID` | Always | Entra tenant → `VITE_AZURE_TENANT_ID` for frontends |
| `AZURE_CLIENT_ID` | When a login registration exists | `ao-{project}-client` appId → `VITE_AZURE_CLIENT_ID` |
| `AZURE_API_CLIENT_ID` | When an API registration exists | `ao-{project}-api` appId → `VITE_AZURE_API_CLIENT_ID` |
| `AO_CONSUMES` | When `auth.consumes` is set | JSON map of cross-project consumed APIs → `VITE_AO_CONSUMES` |

Note the `AZURE_CLIENT_ID` **variable** here is the SPA's login client id used by MSAL.js at build
time — unrelated to CI/CD deploy identity (there is no CI/CD `AZURE_CLIENT_ID` **secret**).

### `cicd update-vars`

```bash
amplifier-online cicd update-vars
```

Re-resolves the variables above (app-registration ids + provisioner connection details) from live
Azure state and updates the GitHub repository variables. Run it after `amplifier-online up` has
recreated app registrations, or whenever the GitHub variables have gone stale. It does **not**
regenerate workflow files.

---

## Security Model

- **Authentication:** the provisioner validates the GitHub Actions OIDC JWT — signature via GitHub's
  JWKS, `iss = https://token.actions.githubusercontent.com`, `aud = AO_PROVISIONER_AUDIENCE`, and
  expiry. An invalid/absent token → **401**.
- **Authorization:** the validated token's `repository_id` must equal `ao-deploy-repo-id`, and its
  `ref` **or** `environment` must equal `ao-deploy-ref` / `ao-deploy-environment`. Mismatch → **403**.
- **Blast radius:** GitHub secrets hold no Azure credential for container stacks, so a leaked repo
  secret cannot be replayed against Azure. The provisioner performs the privileged ACR-import and
  deploy on the caller's behalf, only for the enrolled repo/ref.

---

## Path Filters

Each workflow triggers only when files under its service directory change (plus `workflow_dispatch`):

```yaml
# api-build-deploy.yaml
on:
  push:
    branches: [main]
    paths:
      - 'api/**'      # ← the API service's source directory
```

The path value comes from your project layout. If your API lives in `backend/` rather than `api/`,
update the `paths:` filter in the generated workflow. SWA workflows additionally trigger on
`pull_request` for preview environments.

---

## First-Time Setup Checklist

After `amplifier-online cicd create`:

**All container stacks (`web-app-aca`, `internal-service-aca`, `web-app-awa` backend):**
- [ ] `AO_PROVISIONER_URL`, `AO_PROVISIONER_AUDIENCE`, `AO_PROJECT_NAME` variables are set
      (`cicd create` sets them; verify with `gh variable list`).
- [ ] The project resource group carries `ao-deploy-repo-id` and `ao-deploy-ref`/`-environment` tags
      (written by `cicd create`; a `403` at deploy time means these don't match the repo/ref).
- [ ] `amplifier-online up` has been run once so the project + resource group exist (a deploy to a
      non-existent project returns `404`).
- [ ] Path filters match your actual source directories.
- [ ] Each backend container serves `/health`.

**SWA frontends (`static-web-app`, `web-app-awa` frontend):**
- [ ] `AZURE_STATIC_WEB_APPS_API_TOKEN` secret is set (run `up` first, then `cicd create`).
- [ ] `AZURE_CLIENT_ID`, `AZURE_API_CLIENT_ID`, `AZURE_TENANT_ID`, `AO_CONSUMES` **variables** are set.
- [ ] `output_location` in `amplifier-online.yaml` matches your build tool's output.
- [ ] Local `npm run build` produces files in the expected output directory.

---

## Idempotency and Re-running

- `cicd create` regenerates workflows from the current manifest and re-enrolls the repo — safe to
  re-run after changing stack, services, or the `deploy:` block.
- Commit the generated workflow files: treat them as generated but version-controlled.

---

## Troubleshooting CI/CD Failures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `denied: ... ghcr.io` on push | Workflow lacks `packages: write`, or the org restricts ghcr | Keep the generated `permissions:` block; enable GitHub Packages for the repo/org |
| Deploy step **401** (`OIDC_VALIDATION_FAILED` / `UNAUTHORIZED`) | Wrong/missing OIDC audience, or `id-token: write` missing on the deploy job | Confirm `AO_PROVISIONER_AUDIENCE` variable matches the platform; keep `permissions: id-token: write` |
| Deploy step **403** (`DEPLOY_FORBIDDEN`) | OIDC `repository_id`/`ref`/`environment` don't match the `ao-deploy-*` tags | Re-run `cicd create` from the correct repo; align the manifest `deploy:` `ref`/`environment` |
| Deploy step **404** (`PROJECT_NOT_FOUND`) | Project/resource group doesn't exist, or wrong `AO_PROJECT_NAME` | Run `amplifier-online up` first; verify the `AO_PROJECT_NAME` variable |
| `Image import failed` in provisioner logs | Provisioner couldn't pull from ghcr | Ensure the image is public or the workflow sends `ghcr_token`; check the image ref |
| `gh: command not found` during `cicd create` | `gh` not installed/authed | Install + `gh auth login`, or run the printed `gh secret/variable set` commands manually |
| Trivy fails the build | CRITICAL/HIGH CVE in the image | Patch the base image/deps, or adjust the scan step's `severity`/`exit-code` |
| Workflow not triggering | Path filter doesn't match changed files | Update the `paths:` filter |
| SWA build fails / `AZURE_STATIC_WEB_APPS_API_TOKEN` invalid | Wrong `output_location`, or token missing/expired | Test `npm run build`; re-run `cicd create` after `up` to refresh the token |

---

## PR Preview Deployments

**SWA frontends** (`static-web-app`, `web-app-awa` frontend) get automatic preview environments: open
a PR → Static Web Apps builds a preview at `https://<site>-<pr-number>.<region>.azurestaticapps.net`;
pushes update it; closing the PR tears it down. No extra configuration.

**Container stacks** deploy only from the enrolled ref (`main` by default) — no automatic per-PR
environments. Per-PR container previews would require custom workflow work (separate apps per PR,
cleanup on close, per-PR backing resources).

---

## Related Documentation

- [Stacks Reference](stacks-reference.md) — per-stack deployment details
- [Manifest Schema](manifest-schema.md) — the `deploy:` block and full manifest reference
- [CLI Reference](cli-reference.md) — `cicd create` and `cicd update-vars`
