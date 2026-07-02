# Amplifier Online Troubleshooting Playbook

Use this playbook by mapping the user's symptom to a named failure mode, then applying the
concrete remediation. **Never speculate** when a diagnostic command is available — run it.

---

## Failure Mode 1: Docker Hub Image Reference

**Symptom:** `amplifier-online up` fails with a container pull error:
```
failed to pull image nginx:latest
failed to pull image python:3.11-slim
Error: registry.docker.io: authentication required
```

**Diagnostic:**
```bash
grep -E "image:" amplifier-online.yaml
```

**Root cause:** The manifest references a Docker Hub image instead of ACR. The Container Apps
Environment is configured to pull only from the shared ACR; Docker Hub pulls fail because no
registry credentials are configured.

**Fix:**
1. Build the image locally:
   ```bash
   docker build -t amplifieronlinecr.azurecr.io/<project>-<service>:<tag> ./path-to-dockerfile/
   ```
2. Log in to ACR:
   ```bash
   az acr login --name amplifieronlinecr
   ```
3. Push to ACR:
   ```bash
   docker push amplifieronlinecr.azurecr.io/<project>-<service>:<tag>
   ```
4. Update `amplifier-online.yaml` to use the ACR reference
5. Re-run `amplifier-online up`

**Rule:** Every `image:` in `amplifier-online.yaml` MUST follow: `<acr-name>.azurecr.io/<project>-<service>:<tag>`

---

## Failure Mode 2: Container Port Mismatch

**Symptom:** Deployment succeeds but the app is unreachable, returns 502/503, or health checks fail:
```
Error: container app health check failed after 3 attempts
Revision is failing: target port 3000 not responding
```

**Diagnostic:**
```bash
amplifier-online logs --container api    # Look for "listening on port" messages
grep "port:" amplifier-online.yaml
```

**Root cause:** The `port:` in the manifest doesn't match the port the application actually
listens on. The ingress layer tries to route to the wrong port, and the container ignores
those requests.

**Fix:**
1. Check what port the app listens on from logs or source code:
   - FastAPI/uvicorn default: `8000`
   - Flask/gunicorn default: `5000`
   - Express/Node default: `3000`
   - Nginx default: `80`
2. Update the service port in `amplifier-online.yaml`:
   ```yaml
   services:
     api:
       port: 8000    # ← must match actual application port
   ```
3. Re-run `amplifier-online up`

---

## Failure Mode 3: Missing Dockerfile / Image Not Pushed to ACR

**Symptom:** `amplifier-online up` fails with:
```
failed to pull image amplifieronlinecr.azurecr.io/my-project-api:latest
The requested image's platform (linux/amd64) does not match
manifest unknown: manifest tagged by "latest" is not found
```

**Diagnostic:**
```bash
# Check Dockerfiles exist
find . -name "Dockerfile*" -type f

# Check if image exists in ACR
az acr repository show-tags --name amplifieronlinecr --repository my-project-api
```

**Root cause:** The manifest references an ACR image that doesn't exist yet — the image
was never built and pushed. Amplifier Online deploys images; it does not build them.

**Fix:**
1. Ensure a Dockerfile exists for each container
2. Build the image:
   ```bash
   docker build -t amplifieronlinecr.azurecr.io/<project>-<service>:latest ./path/
   ```
3. Authenticate and push:
   ```bash
   az acr login --name amplifieronlinecr
   docker push amplifieronlinecr.azurecr.io/<project>-<service>:latest
   ```
4. Re-run `amplifier-online up`

---

## Failure Mode 4: Missing Global Config

**Symptom:** CLI commands fail immediately:
```
Error: global config not found at ~/.amplifier-online/config.yaml
Error: no service_url configured
Error: failed to connect to provisioner service
```

**Diagnostic:**
```bash
cat ~/.amplifier-online/config.yaml
```

**Root cause:** `amplifier-online config` was never run, or was run without providing a
`service_url`, or the Provisioner Service URL has changed.

**Fix:**
```bash
amplifier-online config
# Set service_url to the Provisioner Service FQDN
# (get this from the operator who set up the platform, or from Azure portal)
```

**Key fields to verify:**
- `service_url` — must be the HTTPS FQDN of the Amplifier Provisioner Service Container App
- `acr_name` — must match the ACR name in use (default: `amplifieronlinecr`)
- `subscription_id`, `resource_group` — must match the target Azure subscription

---

## Failure Mode 5: EasyAuth / Entra ID Misconfiguration (Web Frontends)

**Symptom:** Web frontend deploys and runs but returns redirect loops or users can't sign in:
```
Redirect loop: app → AAD → app → AAD...
Error creating app registration: insufficient permissions
```

**Note:** EasyAuth is only deployed on web/frontend services (RedirectToLoginPage). API/backend
services never have EasyAuth — they use JWT middleware for token validation. If your API returns
401, see Failure Mode 14 (JWT middleware not configured).

**Diagnostic:**
```bash
amplifier-online logs --container web    # Look for auth-related errors on the web frontend
amplifier-online status                  # Check if container apps are running
```

**Root cause:** One of several causes:
- The user account running `amplifier-online up` doesn't have permission to create Entra app registrations
- The redirect URI wasn't updated after deployment (can happen on first deploy)
- The app registration was manually deleted outside of Amplifier Online
- **`enableIdTokenIssuance` is off on the `-client` registration.** ACA EasyAuth runs secretless
  in this tenant, so it relies on the implicit `id_token` from `/authorize`; without it sign-in
  fails with `AADSTS700054: response_type 'id_token' is not enabled for the application`. (Every
  login client needs this — SWA/AWA hybrid OIDC and ACA EasyAuth alike. The platform sets it on
  managed registrations; a BYO/reused reg must set it manually.)

**Fix:**
1. Verify you have permission to create app registrations in the tenant
2. Re-run `amplifier-online up` to re-create/update the Entra registration — it's idempotent
3. If redirect loops persist, check that the Container App's FQDN matches the redirect URI in the Entra app registration
4. If sign-in fails with `AADSTS700054`, enable ID-token issuance on the `-client` reg:
   `az ad app update --id <client-app-id> --enable-id-token-issuance true`
5. If the app registration is missing: `amplifier-online up` will recreate it

**Note:** `up` automatically handles app registration creation and redirect URI configuration
**only for platform-managed registrations**. A BYO client app (`auth.client_app_id`) is never
modified — you must enable 'ID tokens' (Implicit grant) and add the `…/.auth/login/aad/callback`
redirect URI yourself (the deploy prints both). **Reusing an app reg from a prior deploy puts you
on this BYO read-only path.** If permissions issues persist, escalate to the platform operator.

---

## Failure Mode 6: Resource Quota / Provisioning Failure

**Symptom:** `amplifier-online up` partially succeeds then fails:
```
Error: quota exceeded for PostgreSQL flexible servers in westus2
Error: deployment failed: ContainerAppOperationError
Error: resource group amplifier-online-rg already has maximum Cosmos DB accounts
```

**Diagnostic:**
```bash
amplifier-online up --dry-run    # See what resources would be provisioned
amplifier-online status          # Check current state
```

**Root cause:** The Azure subscription or region has hit a quota limit for a resource type,
or the shared infrastructure has a constraint on per-project resource counts.

**Fix:**
1. Check if the resource is actually needed:
   ```yaml
   resources:
     postgres:
       enabled: false    # ← disable if not actually needed
   ```
2. If the resource IS needed, contact the platform operator to request a quota increase
3. Use `--dry-run` to verify the planned resources before re-deploying

---

## Failure Mode 7: Dockerfile Build Failure (in CI/CD)

**Symptom:** GitHub Actions workflow fails at the build step:
```
ERROR [2/4] RUN pip install -r requirements.txt
#8 1.234 ERROR: Could not find a version that satisfies the requirement
docker build exited with code 1
```

**Root cause:** The Dockerfile or application dependencies have an issue. This is not an
Amplifier Online problem — it's an application build issue.

**Diagnostic:**
```bash
docker build -t test-build . --no-cache    # Reproduce locally
```

**Fix:**
1. Reproduce the build failure locally with `docker build`
2. Fix the Dockerfile or dependency issue
3. Verify with a local build before pushing
4. Once local build succeeds, push to ACR and redeploy

---

## Failure Mode 8: Stale / Wrong Image Tag

**Symptom:** App deploys but runs old code:
```
# Status shows revision deployed, but new features aren't present
# Logs show old code running
```

**Diagnostic:**
```bash
amplifier-online status    # Check running revision
grep "image:" amplifier-online.yaml    # Check what tag is configured
```

**Root cause:** The manifest uses `:latest` tag but the new image wasn't pushed, or a SHA
tag was updated but the manifest still references the old SHA.

**Fix:**
1. Verify the new image is in ACR:
   ```bash
   az acr repository show-tags --name amplifieronlinecr --repository <image-name>
   ```
2. Push the updated image to ACR
3. For `:latest` tags — `latest` is resolved at pull time; re-running `amplifier-online up`
   will pick up the newly pushed `latest`
4. Consider using SHA-based tags in CI/CD (generated by `amplifier-online cicd create`) for
   deterministic deployments

---

## Failure Mode 11: EasyAuth Intercepts Proxied API Calls (Frontend Fetch Fails)

**Symptom:** Frontend `fetch("/api/...")` calls return HTML instead of JSON, or fail silently.
Browser DevTools shows a 302 redirect to the Microsoft login page:
```
fetch("/api/items") → 302 → https://login.microsoftonline.com/...
TypeError: Failed to fetch (or CORS error on the redirect)
```
The web app loads fine (user is logged in), but all JavaScript API calls through the same
hostname are broken.

**Diagnostic:**
```bash
amplifier-online logs --container web    # Look for 302 responses on /api/* paths
# In browser DevTools → Network tab: check if /api/* requests get a 302 to login.microsoftonline.com
```

**Root cause:** EasyAuth is always enabled on web services with `RedirectToLoginPage`, which
enforces authentication on **all** paths — including `/api/...` paths that the frontend proxies
to the API service. When the browser's `fetch()` hits EasyAuth on a proxied path, EasyAuth
returns a 302 redirect to the login page. `fetch()` cannot follow cross-origin auth redirects,
so the call fails.

**Fix:**

Add `auth_exclude` to the web service to bypass EasyAuth on the proxied paths:

```yaml
services:
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 80
    auth_exclude: ["/api"]      # ← EasyAuth skips /api/* paths; proxy forwards them directly
  api:
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000
    # API service validates tokens via JWT middleware (no EasyAuth)
```

Then redeploy:
```bash
amplifier-online up
```

**Key insight:** The API service validates tokens via JWT middleware, so the excluded paths are
still authenticated — just by the API service (via JWT middleware) rather than by EasyAuth on
the web service (via redirect). The `auth_exclude` field only removes the web service's EasyAuth
gate on those path prefixes.

---

## Failure Mode 12: SQLite Errors on Azure Files Volume

**Applies to:** `web-app-aca`, `internal-service-aca`, and `web-app-awa` (all use Azure Files SMB-backed volumes).

**Symptom:** SQLite operations fail with locking or I/O errors, or data is silently corrupted:
```
sqlite3.OperationalError: database is locked (SQLITE_BUSY)
sqlite3.OperationalError: disk I/O error (SQLITE_IOERR)
Data corruption or missing rows after WAL checkpoint
```

**Diagnostic:**
```bash
amplifier-online logs --container api    # Look for SQLITE_BUSY, SQLITE_IOERR
grep "volume:" amplifier-online.yaml     # Confirm service/backend has a volume mount
```

**Root cause:** Both stacks back volumes with Azure Files (SMB), which does not reliably
support POSIX advisory file locks. SQLite's default VFS uses `fcntl()` locks that silently
fail on SMB. WAL mode creates `-wal` and `-shm` shared memory files that SMB cannot reliably
back, leading to corruption or I/O errors.

**Fix:**

1. Connect using the `unix-none` VFS (disables file locking) and `DELETE` journal mode.
   Adjust the path to match your stack's mount point:
   ```python
   import sqlite3

   # web-app-aca: mount_path can be any absolute path (e.g., /data)
   # web-app-awa: mount_path must start with /mounts/ (e.g., /mounts/data)
   conn = sqlite3.connect("file:/data/app.db?vfs=unix-none", uri=True)
   conn.execute("PRAGMA journal_mode = DELETE")
   conn.execute("PRAGMA synchronous = NORMAL")
   conn.execute("PRAGMA foreign_keys = ON")
   ```

2. Verify the volume is configured in `amplifier-online.yaml` — both stacks automatically
   enforce single-instance mode (`maxReplicas=1` or equivalent) when a volume is present,
   which makes the lockless VFS safe.

**Key insight:** `unix-none` skips all `fcntl()` lock calls. This is safe because
single-instance enforcement guarantees only one container instance writes to the database.
Do NOT use WAL mode — its shared memory files are incompatible with SMB.

**Should you switch to PostgreSQL?** If the application uses SQLite for primary
application data (user records, orders, sessions — not an embedded cache or FTS index),
the recommended fix is to enable `resources.postgres.enabled: true` in the manifest
rather than applying the VFS workaround. This eliminates the SMB locking constraint
entirely, provides a managed database that survives container instance replacement, and
uses keyless auth (`DB_HOST`/`DB_NAME`/`DB_USER` injected, no password — the app fetches an
Entra token via `DefaultAzureCredential`). The VFS workaround is appropriate for file-adjacent
data where a separate database server is overkill.

---

## Failure Mode 13: web-app-awa Volume mount_path Missing `/mounts/` Prefix

**Applies to:** `web-app-awa` only.

**Symptom:** `amplifier-online up` fails or the volume is not mounted at the expected path:
```
Error: mount path must start with /mounts/
Volume mount failed: invalid mount_path "/data"
```

**Diagnostic:**
```bash
grep -A2 "volume:" amplifier-online.yaml    # Check mount_path value
grep "stack:" amplifier-online.yaml          # Confirm web-app-awa stack
```

**Root cause:** Azure Web App (Linux) requires that custom storage mounts use paths under
`/mounts/`. Unlike `web-app-aca` (which accepts any absolute path), `web-app-awa` rejects
mount paths that don't start with `/mounts/`.

**Fix:**
1. Update `mount_path` in the manifest to use the `/mounts/` prefix:
   ```yaml
   services:
     api:
       image: amplifieronlinecr.azurecr.io/my-project-api:latest
       port: 8000
       volume:
         mount_path: /mounts/data    # ✅ correct for web-app-awa
         size_gib: 16
   ```
2. Update your application code to read/write from the new path (e.g., `/mounts/data/app.db`
   instead of `/data/app.db`).
3. Re-run `amplifier-online up`.

---

## Failure Mode 14: JWT Middleware Not Configured on API Service

**Symptom:** API service returns 401 Unauthorized for all requests, even with a valid Bearer token,
or returns 500 Internal Server Error with JWT-related errors in logs:
```
HTTP 401 - Unauthorized (on every API call with a Bearer token)
HTTP 500 - jwt_middleware: JWKS endpoint not configured
KeyError: 'AZURE_CLIENT_ID' or 'AZURE_TENANT_ID'
```

Alternatively, the API accepts all requests without authentication (no middleware at all).

**Diagnostic:**
```bash
amplifier-online logs --container api    # Look for JWT validation errors or missing env vars
# Check if jwt_middleware.py is present in the API container's code
# Check if the middleware is registered in the FastAPI app
```

**Root cause:** API/backend services do not use EasyAuth for token validation. They must
include the JWT middleware (`jwt_middleware.py`) to validate Bearer tokens from MSAL.js frontends.
Common causes:

1. **Middleware not installed:** The `jwt_middleware.py` template was not added to the API service.
2. **Middleware not registered:** The middleware file exists but is not registered in the FastAPI app.
3. **Missing environment variables:** `AZURE_CLIENT_ID` or `AZURE_TENANT_ID` not available (auth
   not enabled for the service in the manifest).
4. **Missing dependency:** The `PyJWT` and `cryptography` packages are not in the container's
   `requirements.txt`.

**Fix:**

1. Copy the JWT middleware template into your API service:
   ```bash
   cp amplifier-online/templates/jwt_middleware.py ./your-api-service/middleware/
   ```

2. Register the middleware in your FastAPI app:
   ```python
   from middleware.jwt_middleware import JWTAuthMiddleware
   app.add_middleware(JWTAuthMiddleware)
   ```

3. Add required dependencies to `requirements.txt`:
   ```
   PyJWT>=2.8.0
   cryptography>=41.0.0
   ```

4. A backend API service is always given a `-api` registration, so `AZURE_CLIENT_ID` (the
   `-api` appId) and `AZURE_TENANT_ID` are injected — confirm the middleware reads them.

5. Rebuild, push, and redeploy:
   ```bash
   docker build -t amplifieronlinecr.azurecr.io/<project>-api:latest ./api/
   docker push amplifieronlinecr.azurecr.io/<project>-api:latest
   amplifier-online up
   ```

**Key insight:** EasyAuth is never deployed on API/backend services. Token validation is the
API service's responsibility via JWT middleware. On the backend, `AZURE_CLIENT_ID` is the
project's `-api` registration (`ao-{project}-api`). The middleware validates signatures against
Entra's JWKS endpoint, checks audience (`api://{AZURE_CLIENT_ID}`), issuer, and expiry, and
extracts user identity from JWT claims.

---
## Diagnostic Commands Quick Reference

```bash
amplifier-online status               # Check container app state and revisions
amplifier-online logs                 # Last 30 min, all containers
amplifier-online logs --since 60      # Last 60 min
amplifier-online logs --container api # Single container logs
amplifier-online up --dry-run         # Preview what would change
```

**External diagnostics:**
```bash
az acr repository list --name amplifieronlinecr                          # List repos in ACR
az acr repository show-tags --name amplifieronlinecr --repository <name>  # List image tags
cat ~/.amplifier-online/config.yaml                                       # Show global config
```

---

## Failure Mode 9: Nested Entra Group Membership

**Symptom:** User can log in successfully but gets access denied (403) when trying to access the app:
```
HTTP 403 - Forbidden
User is authenticated but not authorized
```

**Diagnostic:**
```bash
amplifier-online logs --container web    # Look for "user not in authorized group" errors on web frontend
amplifier-online logs --container api    # Look for 403 errors in JWT middleware on API backend
# Check if the user is in a nested group (group-within-a-group)
```

**Root cause:** Neither EasyAuth (on web frontends) nor Entra JWT tokens support **nested group
membership**. If a user is in GroupB, and GroupB is a member of GroupA, and the app checks for
GroupA membership, the user will NOT be recognized as authorized. Only direct membership works.

This affects:
- **Web frontends:** EasyAuth's group claim doesn't include nested groups.
- **API backends:** The JWT `groups` claim doesn't include nested groups either.

**Fix:**
1. Verify group membership structure:
   - Azure Portal → Entra ID → Groups → [your admin_group or user_group]
   - Check "Members" tab
   - If the user is not directly listed, they're in a nested group

2. **Option A (Recommended):** Add the user directly to the authorized group
   - Azure Portal → Entra ID → Groups → [group] → Add member

3. **Option B:** Update the global config to use a different group that contains direct members
   ```bash
   amplifier-online config
   # Update admin_group / user_group to a group with only direct members
   ```

4. Re-run `amplifier-online up` to update configuration

**Note:** This is an Azure platform limitation, not an Amplifier Online bug. Nested groups do
not work with EasyAuth, Static Web Apps authentication, or JWT group claims.

---

## Failure Mode 10: Custom Health Path Returns 401 (EasyAuth Blocks It on Web Services)

**Applies to:** Web/frontend services only. API/backend services do not have EasyAuth.

**Symptom:** Deployment completes but the web Container App shows unhealthy, or Azure health probes fail:
```
Health probe failed: GET /healthz returned 401 Unauthorized
Container app revision failing: health check timeout
amplifier-online status shows: Revision: Failed
```

**Note:** The platform automatically excludes `/health` from EasyAuth enforcement. This failure
mode only applies if your **web service** uses a **custom health path** (e.g., `/healthz`,
`/ready`) that is not auto-excluded. API services are unaffected because they do not have
EasyAuth.

**Diagnostic:**
```bash
amplifier-online logs --container web    # Look for repeated health probe requests on web service
amplifier-online status                  # Check revision status
curl https://<app-url>/healthz           # Test from outside (will 401 if not excluded)
```

**Root cause:** EasyAuth is enabled on the web service (always enforced for frontends) and your
custom health path is not in the excluded paths list. Azure's health probe doesn't send auth
tokens, so it gets a 401 and marks the container as unhealthy. The standard `/health` path is
always excluded automatically, but custom paths are not.

**Fix:** Add your custom health path to the web service's `auth_exclude` list:
```yaml
services:
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 80
    auth_exclude: ["/healthz", "/ready"]    # Add custom health paths here
```

**Key insight:** `/health` is auto-excluded by the platform — you never need to list it. But if
your web service uses a non-standard health path, you must explicitly exclude it. This does not
apply to API services, which do not have EasyAuth.

**After fixing:**
1. Re-run `amplifier-online up`
2. Verify with `amplifier-online status` — revision should show "Running"

---

## Failure Mode 16: BYO Registration Validation Failed

**Applies to:** All stacks when `auth.client_app_id` or `auth.api_app_id` is set in `amplifier-online.yaml`.

**Symptom:** `amplifier-online up` fails immediately with, for a BYO `-api`:
```
App registration 'your-api-app-id' is missing required configuration:
  - Missing identifier URI. Expected 'api://your-api-app-id' in identifierUris.
  - Missing 'access_as_user' OAuth2 permission scope.
```

**Diagnostic:**
```bash
grep -A2 "auth:" amplifier-online.yaml    # Confirm auth.client_app_id / auth.api_app_id are set
```

**Root cause:** BYO is **per role** and validation is role-aware and read-only. A BYO `-api`
(`api_app_id`) that is user-facing must expose `api://{api_app_id}` + `access_as_user` for JWT
audience validation and MSAL.js token acquisition; an internal `-api` exposes neither. A BYO
`-client` (`client_app_id`) is a login client and is **not** required to expose `access_as_user`.
A warning (non-blocking) is emitted if `requestedAccessTokenVersion` is not `2`.

**Fix (user-facing `-api` only):**
1. In Azure Portal > App registrations > your `-api` app > **Expose an API**:
   - Set Application ID URI to `api://{your-api-app-id}`
   - Add a scope with value `access_as_user` (type: Users and admins)
2. Optionally, set `requestedAccessTokenVersion` to `2` in the app manifest
3. Re-run `amplifier-online up`

**Note:** The provisioner never modifies a BYO registration. It also skips deletion of BYO
registrations on `amplifier-online destroy`. For a BYO **client** app, two things must be set by
hand and are **not** auto-configured (both are printed post-deployment): the
`…/.auth/login/aad/callback` redirect URI **and** 'ID tokens' / implicit-grant issuance (required
for the Static Web App / EasyAuth login flow — its hybrid OIDC flow needs an `id_token` from
`/authorize`). Note that **reusing an app registration from a prior deploy makes it a BYO
registration** on this read-only path. Symptom of a missing one: SWA login works once or 401s
after a fresh deploy.

---

## Failure Mode 17: Stale GitHub Variables After `amplifier-online up` (MSAL.js Wrong Client ID)

**Applies to:** All stacks with CI/CD configured via `amplifier-online cicd create`.

**Symptom:** After running `amplifier-online up` (which may recreate app registrations), the
deployed frontend uses a stale or deleted client ID for MSAL.js authentication:
```
AADSTS700016: Application with identifier '<old-client-id>' was not found in the directory
```

The SWA or Container App loads, but authentication fails because the JavaScript bundle has a
client ID baked in that no longer exists in Entra ID.

**Diagnostic:**
```bash
# Check what GitHub repo variables the CI/CD workflow is using
gh variable list --repo <owner>/<repo>

# Compare with the actual login client registration
az ad app list --display-name ao-<project>-client --query "[].appId" -o tsv
```

If the frontend's `AZURE_CLIENT_ID` GitHub variable (the login `-client` appId) doesn't match
the registration's `appId`, the variables are stale. (This is the project's MSAL.js login client,
not the CI/CD deploy identity's `AZURE_CLIENT_ID` GitHub-OIDC app.)

**Root cause:** `amplifier-online up` creates/updates Entra app registrations and sets SWA/Container
App settings correctly, but it does **not** update GitHub repository variables. The CI/CD workflow
(generated by `amplifier-online cicd create`) reads `vars.AZURE_CLIENT_ID` at build time and bakes
it into the Vite bundle via `VITE_AZURE_CLIENT_ID`. When `up` creates a new app registration (e.g.,
after a `destroy` and redeploy), the GitHub variable still points to the old, deleted registration.

**Fix:**
```bash
amplifier-online cicd update-vars    # Syncs GitHub variables with current Azure state
```

This re-resolves `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` from the live app registration and
updates the GitHub repository variables. Then trigger a redeploy to rebuild the frontend with
the correct values:

```bash
gh workflow run "<workflow-name>" --repo <owner>/<repo> --ref main
```

**Key insight:** SWA/Container App **runtime** settings (set by `up`) and GitHub **build-time**
variables (set by `cicd create` / `cicd update-vars`) are independent. Vite inlines `VITE_`-prefixed
env vars at build time, so the GitHub variable is what matters for the deployed JavaScript bundle,
not the SWA app setting.

---

## Failure Mode 15: SWA Authentication Not Enforced

**Applies to:** `web-app-awa`, `static-web-app` stacks.

**Symptom:** SWA app allows unauthenticated access or MSA (personal Microsoft) accounts can
sign in when only organizational accounts should be permitted.

**Diagnostic:**
```bash
# Check if staticwebapp.config.json exists and has an auth section
cat staticwebapp.config.json | grep -A 10 '"auth"'
# Check SWA app settings for required env vars
az staticwebapp appsettings list --name <swa-name>
```

**Root cause:** Missing or incomplete `auth` section in `staticwebapp.config.json`, or missing
`AZURE_TENANT_ID` in SWA app settings. Without the AAD identity provider configured with
`openIdIssuer` pinned to the tenant, SWA falls back to allowing all Microsoft accounts
(including personal MSA accounts) or no authentication at all.

**Fix:**
1. Verify `staticwebapp.config.json` has the AAD identity provider with `openIdIssuer`
   pinned to the tenant (e.g., `https://login.microsoftonline.com/<tenant-id>/v2.0`)
2. Verify SWA app settings include both `AZURE_CLIENT_ID` and `AZURE_TENANT_ID`
3. Re-run `amplifier-online up` to regenerate the configuration if needed

---

## Failure Mode 18: Consumer Deployed Before Producer (`auth.consumes`)

**Applies to:** Any project with `auth.consumes: [...]` referencing another project by name.

**Symptom:** `amplifier-online up` fails to wire cross-project access, or the consumer's calls
to the producer API are rejected (401/invalid audience):
```
Error: producer project 'other-project' not found / not deployed
Consumer token rejected: application not pre-authorized for api://<producer-api>/access_as_user
```

**Diagnostic:**
```bash
grep -A2 "consumes:" amplifier-online.yaml    # See which producer(s) this consumer references
```

**Root cause:** The producer (which must set `auth.expose: true`) must be **deployed first**.
The platform wires the consumer's `-client` requiredResourceAccess to the producer's
`access_as_user` and adds it to the producer's `preAuthorizedApplications` — which requires the
producer's `-api` to already exist.

**Fix:**
1. Deploy the producer first (`auth.expose: true`), then the consumer.
2. If the platform does not own the producer, it warns — the producer owner must add the
   consumer to its `-api` preAuthorizedApplications manually. (For a BYO producer, pass the
   producer via `auth.consumes: [{api_app_id, base_url}]`.)

---

## Failure Mode 19: `AADSTS7002381` at an Azure login step (retired model — regenerate workflows)

**Applies to:** Repos whose `.github/workflows/` still contain the **old** Azure-OIDC deploy jobs
(an `azure/login` step plus `az acr login` / `az containerapp update`).

**Symptom:** A deploy job fails at an Azure login step:
```
AADSTS7002381: Federated identity credentials issued by
'https://token.actions.githubusercontent.com/' ... must contain the enterprise claim ...
```

**Root cause:** The retired container CI/CD model logged in to **Azure AD** via a per-repo Entra
federated credential, which the corporate tenant only honors for repos in a Microsoft-linked GitHub
enterprise org. The **current** push-to-deploy model does not log in to Azure AD at all — the deploy
job mints a GitHub OIDC token for the **provisioner's** audience and POSTs to the provisioner, which
validates the token itself (issuer / audience / `repository_id` / `ref`). There is **no
`enterprise`-claim requirement and no enterprise-org constraint** anymore.

**Fix:** Regenerate the workflows so they use the current model:
```bash
amplifier-online cicd create
```
If a deploy still fails with a **401 at the provisioner** (not Azure AD), that's a different problem —
see the OIDC / `AO_PROVISIONER_AUDIENCE` rows in `cicd-guide.md`.

---

## Failure Mode 20: `ServiceTreeInvalid` on App Registration Creation

**Symptom:** `amplifier-online up` fails during app-registration creation with `ServiceTreeInvalid`.

**Root cause:** The tenant requires every app registration to carry a valid Service Tree ID
(`serviceManagementReference`). Creation is rejected outright without it.

**Fix:** Set `AO_SERVICE_TREE_ID` to a valid Service Tree ID before provisioning (it flows into
`serviceManagementReference` at creation), then re-run `amplifier-online up`. Get the ID from
your service's Service Tree entry, or from the platform operator.

---

## Failure Mode 21: `AuthConfigInvalidRequest` During Deploy (Token Store)

**Symptom:** Bicep/EasyAuth deployment fails with `AuthConfigInvalidRequest`.

**Root cause:** The Container Apps `2024-03-01` auth API requires a blob storage SAS URL
(`SasUrlSettingName`) whenever a token store is configured. The token store needs a storage
account with `allowSharedKeyAccess` enabled, which tenant policy disables — so the platform omits
the token-store block entirely (it is removed, not set to `enabled: false`).

**Fix:** This is handled by the platform; if you see it on a customized stack, remove the
`tokenStore` block from the `authConfigs` resource. **Note:** with no token store, `GET /.auth/me`
returns **404 — this is the expected, healthy state**, not a bug. EasyAuth still injects the
`X-MS-CLIENT-PRINCIPAL*` identity headers, and APIs read identity from the validated JWT (see
`authorization-guide.md`). Do not "fix" a 404 from `/.auth/me`.

---

## Failure Mode 22: `ObjectConflict` on App Registration Creation

**Symptom:** App-registration creation fails with `ObjectConflict`.

**Root cause:** Either a concurrent provisioner run is creating the same registration, or a
previously deleted registration with the same display name lingers as a soft-deleted tombstone
(Entra retains them for 30 days).

**Fix:** Usually transient — the provisioner polls for the winning registration and restores from
deleted items automatically. **Retry the command.** If it persists, check for a tombstone:
```bash
az rest --method GET --uri "https://graph.microsoft.com/v1.0/directory/deletedItems/microsoft.graph.application?\$filter=displayName eq 'ao-<project>-api'"
```
Restore it, or permanently delete it, then retry.

---

## Failure Mode 23: Bicep Permission / "Not Found" Error Right After App Creation

**Symptom:** The app registration is created, but the immediately following Bicep deployment fails
with a permission or "not found" error that references the service principal.

**Root cause:** Entra service-principal replication lag. The SP exists in Graph but has not yet
propagated to ARM.

**Fix:** Transient — the provisioner polls (up to 15 times, 3s apart). If it surfaces to you,
**wait 30–60 seconds and retry** `amplifier-online up` (idempotent).

---

## Failure Mode 24: `amplifier-online up` "Response ended prematurely"

**Symptom:** `amplifier-online up` drops mid-deployment with `Response ended prematurely`.

**Root cause:** The provisioner Container App restarted during a revision swap while streaming the
deployment, cutting the SSE connection.

**Fix:** **Retry the command** — all operations are idempotent, so a re-run resumes/repeats safely.

---

## Failure Mode 25: `TokenIssuedBeforeRevocationTimestamp` (CAE Revocation)

**Symptom:** API calls fail with `TokenIssuedBeforeRevocationTimestamp` after a permission or
group/role change.

**Root cause:** Azure Continuous Access Evaluation (CAE) revoked the in-flight token after the
directory change; the cached token predates the revocation timestamp.

**Fix:** Re-acquire a fresh token (clear the cache — see the token-cache guidance in
`authorization-guide.md`). For CLI scripts, validate freshness early so the failure surfaces up
front:
```bash
az account get-access-token --resource "api://<client-id>"
```

---

## Failure Mode 26: Unexpected Consent Prompt on First Login

**Symptom:** New users hit a "Permissions requested" consent dialog on first login (the developer's
own account doesn't, because it consented earlier).

**Root cause:** The app registration doesn't declare `User.Read` in `requiredResourceAccess`, so
Entra prompts each new user for consent on the default scopes.

**Fix:** Add `User.Read` (Microsoft Graph, delegated) to the registration's `requiredResourceAccess`
so it's pre-declared. **Note:** in the corp tenant you are not a tenant admin and cannot grant admin
consent — for anything beyond `User.Read`, use the established Graph-permission request process.

---

## Failure Mode 27: Personal (MSA) Accounts Can Sign In to a Corp-Only App

**Symptom:** Personal Microsoft accounts authenticate to an app that should be corp-tenant only.

**Root cause:** The tenant ID is empty/missing, so the MSAL or EasyAuth authority falls back to
`https://login.microsoftonline.com/common` (the multi-tenant + MSA endpoint).

**Fix — pin the tenant per stack:**
- **SPA / MSAL.js:** ensure `VITE_MSAL_TENANT_ID` is set **at build time** (it's baked into the
  bundle — see the build-time diagnostic below).
- **SWA:** pin `openIdIssuer` to `https://login.microsoftonline.com/<tenant-id>/v2.0` in
  `staticwebapp.config.json` (not "common").
- **ACA:** verify `AZURE_TENANT_ID` is injected (automatic via Bicep).

---

## Failure Mode 28: CLI/Script Gets 403 After a Role or Group Change (Stale CLI Token Cache)

**Symptom:** A user's `az`/script call to a deployed API returns 403 (or shows old roles/groups)
right after their role or group membership changed.

**Root cause:** Claims are evaluated at token issuance; the Azure CLI caches tokens, so the cached
token carries stale claims until it expires.

**Fix:** Clear the CLI token cache and re-authenticate:
```bash
az account clear && az login
rm ~/.azure/msal_token_cache.*
```
(The full cross-surface cache guidance — browser/MSAL too — lives in `authorization-guide.md`.)

---

## Failure Mode 29: `redirect_uri_mismatch` / `AADSTS50011`

**Symptom:** Login fails with `redirect_uri_mismatch` or `AADSTS50011: The redirect URI ... does
not match the redirect URIs configured for the application`.

**Root cause:** A project that signs users in needs **two different** redirect URI types on the
`-client` registration, and they live under different platform sections:
- **Web** (EasyAuth callback): `https://{fqdn}/.auth/login/aad/callback`
- **SPA** (MSAL.js): `https://{fqdn}/` — must be registered under the **SPA** platform (not Web),
  and in **both** the trailing-slash (`/`) and bare-origin forms.

A SPA redirect URI registered under the **Web** platform instead of **SPA** produces
`AADSTS9002326` ("cross-origin token redemption is permitted only for the 'Single-Page
Application' client-type").

**Fix:** Re-run `amplifier-online up` to reconfigure redirect URIs for platform-managed
registrations. For a BYO `-client`, add both URI types yourself (the deploy prints them); see
Failure Mode 5. See also the AADSTS quick table below.

---

## Failure Mode 30: Authorization Silently Fails (Mail-Enabled Group / 200-Group Overage)

**Symptom:** A user is assigned to a role (or in the right group) per the Azure Portal, but the
app treats them as unauthorized — no `roles` claim, or a missing `groups` claim.

**Root cause (brief):** Two silent traps — assigning a **mail-enabled** group to an app role
(Entra returns 201 and shows it in the portal but never emits the claim), or a user in **200+
security groups** (the `groups` claim is replaced by `_claim_names`/`_claim_sources`).

**Fix:** Prefer app **roles** over group claims (roles are never subject to overage), and use only
**pure security groups** (`mailEnabled=false`). **`authorization-guide.md` owns the full
explanation, detection commands, and the roles-vs-groups model — go there.**

---

## Failure Mode 31: Static Web App Auth Config Has No Effect (Free Tier)

**Symptom:** A `static-web-app` (or `web-app-awa` frontend) ships a `staticwebapp.config.json` with
AAD auth / protected-route rules, but they have no effect — anonymous users reach routes that should
require login.

**Root cause:** The Static Web App is on the **Free** tier. Built-in AAD authentication and custom
auth route rules require the **Standard** plan; on Free, the auth config is silently ignored.

**Fix:** Upgrade the Static Web App to the **Standard** plan, then redeploy / re-run `amplifier-online up`.

---

## Failure Mode 32: internal-service-aca Unreachable From Another Container

**Symptom:** A caller in the environment gets connection-refused or a timeout when calling an
`internal-service-aca` service.

**Root cause / checklist:** Internal services have `external: false` (no public ingress), so verify:
1. The caller runs in the **same Container Apps Environment** as the callee.
2. The caller addresses the callee by its **internal FQDN** (`<app>.internal.<env-default-domain>`),
   not a public hostname.
3. The request **port matches** the container's `targetPort`.

(Once reachable, a 401/403 is an auth problem, not connectivity — see the service-to-service auth
section in `stacks-reference.md` for the JWT + `azp`-whitelist layer.)

---

## Failure Mode 33: vm Unreachable From an ACA App (NSG / Networking)

**Applies to:** `vm` stack.

**Symptom:** An ACA app (or other VNet resource) gets connection-refused or a timeout connecting to
the VM's private IP/port.

**Root cause / checklist:** The VM has **no public IP** and a **default-deny NSG** — only the
inbound `ports` you declared are open, and only from the declared `source`. Verify:
1. The target `port` is listed in `vm.ports` in the manifest (all other inbound is denied).
2. The rule's `source` covers the caller. ACA app egress comes from the CAE app subnet — use
   `source: cae-infra` (`10.100.0.0/23`). `vnet` opens the whole VNet; a CIDR must include the caller.
3. The caller uses the VM's **private IP** (printed on `up`, or `az vm list-ip-addresses`). A dynamic
   IP can change if the VM is deallocated — set `vm.static_private_ip` for stability.
4. The software is actually listening and bound to `0.0.0.0` (not `127.0.0.1`):
   ```bash
   az vm run-command invoke -g ao-<project>-rg -n <project>-vm \
     --command-id RunShellScript --scripts "ss -tlnp"
   ```

After changing `vm.ports`, re-run `amplifier-online up`.

---

## Failure Mode 34: vm Can't Resolve an Internal (`external: false`) ACA App Name

**Applies to:** `vm` stack (v1 limitation).

**Symptom:** Software on the VM fails to resolve an internal ACA app FQDN
(`<app>.internal.<domain>`), while external app FQDNs resolve fine.

**Root cause:** External-ingress CAEs have no private DNS zone to link, so the VM resolves external
app FQDNs publicly but **cannot resolve `*.internal.<domain>`** names.

**Fix:** Reach the internal app **by IP**, or make it **external** (`external: true`). (The reverse
direction — an ACA app reaching the VM — works over the VM's private IP; see Failure Mode 33.)

---

## Failure Mode 35: vm — `resources.env` Missing/Stale, or Postgres Rejected

**Applies to:** `vm` stack.

**Symptom:** Software on the VM can't find `/etc/amplifier-online/resources.env` (or it's missing an
endpoint like `COSMOS_ENDPOINT`/`REDIS_HOST`/`DB_HOST`).

**Root cause:**
1. **`resources.env` timing.** Enabled keyless resources (`cosmos`, `redis`, `storage`,
   `cognitive-services`, `postgres` — all keyless) are written to
   `/etc/amplifier-online/resources.env` by a **Run Command** — it lands **shortly after boot**, not
   at cloud-init parse time. Software that reads it inline during cloud-init can race ahead of it.
2. **First-run / stale file.** The file is (re)written on every `up` whose resource set changed. If
   you enabled a resource but haven't re-run `up`, or you're on an old VM provisioned before this
   feature, the file won't reflect the change until the next `up`.

**Fix:**
- For `postgres` on a VM, the file provides `DB_HOST`/`DB_NAME`/`DB_USER` (keyless, no password) —
  the VM fetches an Entra token (scope `https://ossrdbms-aad.database.windows.net/.default`) via
  `DefaultAzureCredential`/IMDS and uses it as the password.
- **Source `/etc/amplifier-online/resources.env` at service start** (a systemd unit or `runcmd`
  step), not inline at cloud-init parse time. Authenticate to the resource with
  `DefaultAzureCredential`/IMDS — the file provides endpoints, not keys.
- If the file is missing/stale after enabling a resource, **re-run `amplifier-online up`** (the Run
  Command refreshes it). Verify with
  `az vm run-command invoke -g ao-<project>-rg -n <project>-vm --command-id RunShellScript --scripts "cat /etc/amplifier-online/resources.env"`.

---

## AADSTS Error Code → Cause Quick Table

When the only signal is an `AADSTS` code in the browser console or CLI output:

| Code | Cause | Pointer |
|------|-------|---------|
| `AADSTS50011` | Redirect URI not registered (or registered under the wrong platform) | Failure Mode 29 |
| `AADSTS9002326` | SPA redirect URI registered under **Web** platform; MSAL needs **SPA** type | Failure Mode 29 |
| `AADSTS900144` | Empty/missing `client_id` — a build-time var was not baked into the bundle | Build-Time Config Inlining (below) |
| `AADSTS700016` | Application not found for the client id — stale/wrong client id in config or GitHub vars | Failure Mode 17 |
| `AADSTS7002381` | GitHub OIDC token missing `enterprise` claim (non-enterprise repo) | Failure Mode 19 |
| `AADSTS50105` | User not assigned to a role; or nested/mail-enabled group | Failure Mode 9, Failure Mode 30 |
| `AADSTS53000` | Conditional Access — device not compliant/managed | Sign in from a compliant device |

---

## Build-Time Config Inlining Diagnostic

**When to use:** A frontend uses the wrong client/tenant ID and changing a Container App env var
has **no effect**, or you see `AADSTS900144` (empty client id) / `AADSTS700016` (app not found).

**Why:** Vite / Next / CRA inline `VITE_*` / `NEXT_PUBLIC_*` env values at **`docker build`
time**, baking them into the served JS bundle. Changing the running container's env var afterward
does nothing — the value is already compiled in.

**Diagnose — confirm what's actually baked into the bundle:**
```bash
# Exec into a running replica and grep the served assets for the expected GUID
az containerapp exec --name <app> --resource-group <rg> \
  --command "sh -c \"grep -roh '[0-9a-f-]\\{36\\}' /usr/share/nginx/html | sort -u\""
```
Compare the GUID(s) found against the `-client` login registration's app id.

**Common cause:** the frontend was built with the **deploy service principal's** `AZURE_CLIENT_ID`
(the GitHub-OIDC deploy identity) as its client id, instead of the project's **`-client`** login
registration. Set the build var to the `-client` app id and rebuild. (Related: stale GitHub
variables — Failure Mode 17.)

---

