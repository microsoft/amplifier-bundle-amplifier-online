# Amplifier Online CLI Reference

The **Amplifier Online CLI** (`amplifier-online`) is the developer-facing tool for deploying
projects onto the shared Azure Container Apps infrastructure. Install via:

```bash
uv tool install git+https://github.com/microsoft/amplifier-online#subdirectory=cli
```

---

## Authentication

The Amplifier Online CLI uses Azure credential chaining to authenticate. When you run commands
that require Azure access, the CLI automatically tries multiple credential methods:

1. **InteractiveBrowserCredential** (default) — Opens your browser for Azure login
2. **AzureCliCredential** — Uses `az login` session if available

**No explicit `az login` required** — the CLI will prompt for browser authentication when needed.

### First-time authentication

Run any command that requires Azure access (like `amplifier-online stack list`) and the CLI will
guide you through browser authentication:

```bash
amplifier-online stack list
# → Browser opens for Azure login (if not already authenticated)
```

### Microsoft tenant device code limitation

If you're in a Microsoft-managed tenant, the device code flow may be blocked for security
reasons. The CLI uses browser-based authentication by default, which avoids this issue.

### Manual authentication (optional)

If you prefer to use `az login`:

```bash
az login
amplifier-online stack list  # Will use existing az login session
```

---

## `amplifier-online config`

Create or update the global config file at `~/.amplifier-online/config.yaml`. Prompts for
each field with current values as defaults — press Enter to keep or type a new value.

```bash
amplifier-online config
```

**Writes to:** `~/.amplifier-online/config.yaml`

**Fields prompted:**
```yaml
subscription_id: <azure-subscription-id>
location: westus2
resource_group: amplifier-online-rg
keyvault_name: amplifier-online-kv
postgres_admin_login: aoadmin
service_tree_id: <service-tree-id>
admin_group: <entra-group-object-id>
user_group: <entra-group-object-id>
log_analytics_workspace_id: <workspace-id>
acr_name: amplifieronlinecr
service_url: https://<provisioner-fqdn>
```

**When to run:** One-time setup, or when platform config changes. Must exist before `init`.

---

## `amplifier-online stack list`

List all deployment stacks available from the Amplifier Provisioner Service.

```bash
amplifier-online stack list
```

**Example output:**
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

  vm
    Private Linux VM in the platform VNet (no public IP) with a system-assigned managed identity, cloud-init setup, and optional keyless access to Cosmos, Redis, Storage, and Cognitive Services
```

---

## `amplifier-online stack manifest`

Print the default YAML manifest template for a stack. Useful for previewing what
`amplifier-online init` would generate without writing any files.

```bash
amplifier-online stack manifest <stack-name>                     # Show template with placeholder values
amplifier-online stack manifest <stack-name> --project-name foo  # Show template with custom project name
```

If an `amplifier-online.yaml` exists in the current directory, the project name from it is used
for template substitution. Otherwise, placeholder values are shown.

---

## `amplifier-online init`

Scaffold an `amplifier-online.yaml` in the current directory from the selected stack
template. Requires global config (`amplifier-online config`) to exist first.

```bash
amplifier-online init                      # Interactive: prompts for stack (if multiple) and project name
amplifier-online init --stack web-app-aca          # Non-interactive: specify stack directly
amplifier-online init --stack internal-service-aca  # Internal-only Container App (no public ingress)
amplifier-online init --stack vm                    # Private Linux VM (cloud-init, no container image)
```

**`vm` stack scaffolds differently:** it writes a `vm:` block (VM size, `ssh_public_key`,
`cloud_init` path, `ports`, optional `data_disk_gib`) instead of `services:`, and you supply a
`cloud-init.yaml` next to the manifest to install your software on first boot. There is no
Dockerfile and no ACR image to build/push. See the vm sections in `stacks-reference.md` and
`manifest-schema.md`.

**Interactive flow:**
1. If one stack → auto-selects it
2. If multiple stacks → shows a menu
3. Prompts for project name
4. Generates `amplifier-online.yaml` in the current directory

**After `init`:** Edit `amplifier-online.yaml` to set correct image names, ports, and resource flags.

**Use `--stack` flag in scripts** — the interactive prompt is intended for manual use, not CI/CD.

---

## `amplifier-online up`

Deploy the project defined in `amplifier-online.yaml`. The Provisioner Service:
1. Creates or validates the role-based registrations the project needs — `ao-{project}-client`
   (if it has a frontend) and/or `ao-{project}-api` (if it hosts an API). If a BYO appId is set
   per role (`auth.client_app_id` / `auth.api_app_id`), that role is validated read-only instead of created.
2. Deploys the Bicep template for the selected stack
3. Configures EasyAuth redirect URIs (for web services / frontends) — **only for
   platform-managed registrations. A BYO client app (`auth.client_app_id`) is never
   modified**: you must enable 'ID tokens' (Implicit grant) and add its redirect URIs
   yourself. The deploy prints exactly what to add — including the
   `…/.auth/login/aad/callback` callback — at the end of `up`.

```bash
amplifier-online up            # Deploy for real
amplifier-online up --dry-run  # Preview what would happen without making changes
```

**Prerequisites:**
- Global config exists (`amplifier-online config`)
- `amplifier-online.yaml` present in current directory
- Images in manifest reference ACR (`<acr-name>.azurecr.io/...` format)
- Image delivery is handled by push-to-deploy (`amplifier-online cicd create`, then `git push`) —
  CI builds and pushes to your ghcr.io and the provisioner imports into ACR. You do **not** build
  or push to the shared ACR yourself. On a first `up` the image may not exist until the first
  workflow run completes.

**Always suggest `--dry-run` first** when a user is about to run `up` for the first time.

**`vm` stack:** `up` skips all of the above auth/registration/EasyAuth steps (a VM has no login
client, `-api`, or redirect URIs) and simply deploys the VM Bicep. The CLI **inlines your
`vm.cloud_init` file** into the deployment at `up` time, and prints the VM's **private IP** on
success. There are no images to build or push. `up` is idempotent — re-running updates the VM in
place and **preserves the data disk**. To change installed software, update cloud-init and re-run
`up`, or use `az vm run-command` (there is no public SSH; see the vm section in
`stacks-reference.md`).

---

## `amplifier-online status`

Show the current state of deployed container apps and enabled resources for the project.

```bash
amplifier-online status
```

**Output includes:** Container app names, revision status, ingress FQDNs, enabled databases.

---

## `amplifier-online logs`

Tail container logs via Log Analytics. Defaults to last 30 minutes, all containers.

```bash
amplifier-online logs                    # Last 30 min, all containers
amplifier-online logs --since 60         # Last 60 minutes
amplifier-online logs --container api    # Only the api container
```

---

## `amplifier-online destroy`

Tear down all per-project resources: container apps, databases, storage, and the platform-created
role registrations (`ao-{project}-client` / `ao-{project}-api`). BYO (per-role) registrations are
skipped. Prompts for confirmation unless `--dry-run` is used.

```bash
amplifier-online destroy            # With confirmation prompt
amplifier-online destroy --dry-run  # Show what would be deleted
```

**Warning:** This is irreversible. Use `--dry-run` first to review.

---

## `amplifier-online cicd create`

Generate GitHub Actions workflow files and enroll the repo for push-to-deploy. Writes to
`.github/workflows/` in the current directory.

```bash
amplifier-online cicd create            # Generate workflows, enroll repo, set GH secrets/vars
amplifier-online cicd create --dry-run  # List the workflows it would generate; write/set nothing
```

**Generated files (example for `web-app-aca` with 2 containers):**
- `.github/workflows/api-build-deploy.yaml`
- `.github/workflows/web-build-deploy.yaml`

**What it does:** detects the repo via `gh`, reads the manifest's `deploy:` block for
`ref`/`environment` (default `refs/heads/main`), then renders the workflow files, enrolls the repo
with the provisioner, and **sets the GitHub repository secrets and variables for you** via `gh`. If `gh` is missing/unauthenticated it
prints the `gh secret set` / `gh variable set` commands instead.

**Prerequisites:** `gh` installed and authenticated; run inside the git repo with a GitHub remote.

**GitHub secrets (container stacks need NONE):** container/Web-App deploys authenticate to the
provisioner with a GitHub OIDC token — there is no `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/
`AZURE_SUBSCRIPTION_ID` deploy secret and no federated credential. The only secret is
`AZURE_STATIC_WEB_APPS_API_TOKEN`, set for SWA frontends and only available **after** `amplifier-online up`
(re-run `cicd create` after the first `up`).

**GitHub variables (set automatically):** `AO_PROVISIONER_URL`, `AO_PROVISIONER_AUDIENCE`,
`AO_PROJECT_NAME` (container deploy target), plus `AZURE_CLIENT_ID`, `AZURE_API_CLIENT_ID`,
`AZURE_TENANT_ID`, `AO_CONSUMES` for frontend (MSAL.js/`VITE_*`) builds.

See `cicd-guide.md` for the full push-to-deploy architecture and security model.

---

## `amplifier-online cicd update-vars`

Re-resolve the GitHub repository **variables** (app-registration ids + provisioner connection
details) from live Azure state and update them via `gh variable set`. Does not regenerate workflows.

```bash
amplifier-online cicd update-vars
```

Use after `amplifier-online up` has recreated app registrations, or whenever the GitHub variables are
stale.

---

## Common Workflows

### First deployment
```bash
amplifier-online config           # 1. Set global config (once)
# Browser auth happens automatically when needed
amplifier-online init             # 2. Scaffold manifest (fills in ACR image URIs)
# Edit amplifier-online.yaml      # 3. Set ports/resources
amplifier-online up --dry-run     # 4. Preview
amplifier-online up               # 5. Provision Azure resources
amplifier-online cicd create      # 6. Generate deploy workflows (container stacks)
git add .github/workflows/ && git commit -m "add deploy workflows" && git push   # 7. CI builds → ghcr → provisioner imports into ACR → deploys
amplifier-online status           # 8. Check
```

### Subsequent deployments
```bash
# For container stacks: git push — CI rebuilds the image and the provisioner redeploys it.
amplifier-online up               # For infra/manifest changes (idempotent)
```

### Switching stacks
```bash
amplifier-online destroy          # 1. Tear down current stack
# Edit amplifier-online.yaml      # 2. Change stack: field
amplifier-online up               # 3. Deploy with new stack
```
