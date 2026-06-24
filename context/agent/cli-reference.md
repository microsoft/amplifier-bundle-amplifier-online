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

### Calling a deployed project's API from a script/CLI

To call a deployed project's API (EasyAuth- or JWT-protected) from a script or the CLI, acquire
a bearer token for the project's **`-api`** registration audience:

```python
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("api://<api-client-id>/access_as_user")
# → send as: Authorization: Bearer <token.token>
```

- The Azure CLI app id `04b07795-8ddb-461a-bbee-02f9e1bf7b46` is pre-authorized on the project's
  `-api` registration (and on the `web-app-aca` stack it is in the EasyAuth `allowedApplications`
  list), so `az`/scripts can call the API without triggering an admin-consent prompt.
- Request the **`api://<api-client-id>/access_as_user`** scope. Requesting the wrong scope (e.g.
  `https://graph.microsoft.com/.default`, or a bare client id) yields a **401 audience mismatch** —
  the token's `aud` won't match `api://<api-client-id>`.
- Wrong-tenant login is a common cause of failures; fix it with `az login --tenant <tenantId>`.
- If a token still reflects stale roles/groups after a change, clear the token cache — see the
  cache-clear recipe in `authorization-guide.md`.

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
```

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
- Docker images already built and pushed to ACR (for container stacks)
- Images in manifest reference ACR (`<acr-name>.azurecr.io/...` format)

**Always suggest `--dry-run` first** when a user is about to run `up` for the first time.

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

Generate GitHub Actions workflow files for building and deploying containers. Writes to
`.github/workflows/` in the current directory.

```bash
amplifier-online cicd create            # Write workflow files
amplifier-online cicd create --dry-run  # Preview without writing
```

**Generated files (example for `web-app-aca` with 2 containers):**
- `.github/workflows/api-build-deploy.yaml`
- `.github/workflows/web-build-deploy.yaml`

**Auth variables (resolved and set automatically):** `cicd create` resolves the project's `-client`
and `-api` appIds (plus any cross-project producer `-api` appIds from `auth.consumes`) and sets them
as GitHub Actions variables — `AZURE_CLIENT_ID`, `AZURE_API_CLIENT_ID`, and `AO_CONSUMES` — so SWA
frontend builds receive them. This is separate from the CI/CD deploy identity below.

**Required GitHub secrets (must be set after generating) — the deploy identity:**
- `AZURE_CLIENT_ID`  (the GitHub-OIDC deploy app — distinct from the project's auth `-client` registration)
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

See cicd-guide.md for the full workflow shape and secret setup instructions.

---

## Common Workflows

### First deployment
```bash
amplifier-online config           # 1. Set global config (once)
# Browser auth happens automatically when needed
# Build and push images to ACR    # 2. Build and push (outside CLI, for container stacks)
amplifier-online init             # 3. Scaffold manifest
# Edit amplifier-online.yaml      # 4. Set images/ports/resources
amplifier-online up --dry-run     # 5. Preview
amplifier-online up               # 6. Deploy
amplifier-online status           # 7. Check
```

### Subsequent deployments
```bash
# Rebuild and push image to ACR (for container stacks)
amplifier-online up               # Re-deploy (idempotent)
```

### Switching stacks
```bash
amplifier-online destroy          # 1. Tear down current stack
# Edit amplifier-online.yaml      # 2. Change stack: field
amplifier-online up               # 3. Deploy with new stack
```
