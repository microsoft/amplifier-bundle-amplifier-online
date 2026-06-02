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

## Failure Mode 5: EasyAuth / Entra ID Misconfiguration

**Symptom:** App deploys and runs but returns 401 Unauthorized or redirect loops:
```
HTTP 401 - Unauthorized
Redirect loop: app → AAD → app → AAD...
Error creating app registration: insufficient permissions
```

**Diagnostic:**
```bash
amplifier-online logs --container api    # Look for auth-related errors
amplifier-online status                  # Check if container apps are running
```

**Root cause:** One of several causes:
- The user account running `amplifier-online up` doesn't have permission to create Entra app registrations
- The redirect URI wasn't updated after deployment (can happen on first deploy)
- The app registration was manually deleted outside of Amplifier Online

**Fix:**
1. Verify you have permission to create app registrations in the tenant
2. Re-run `amplifier-online up` to re-create/update the Entra registration — it's idempotent
3. If redirect loops persist, check that the Container App's FQDN matches the redirect URI in the Entra app registration
4. If the app registration is missing: `amplifier-online up` will recreate it

**Note:** `up` automatically handles app registration creation and redirect URI configuration.
If permissions issues persist, escalate to the platform operator.

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

**Root cause:** EasyAuth is enabled on the web service with `protected: login`, which enforces
authentication on **all** paths — including `/api/...` paths that the frontend proxies to the
API service. When the browser's `fetch()` hits EasyAuth on a proxied path, EasyAuth returns a
302 redirect to the login page. `fetch()` cannot follow cross-origin auth redirects, so the
call fails.

**Fix:**

Add `exclude` to the web service's `protected` config to bypass EasyAuth on the proxied paths:

```yaml
services:
  web:
    image: amplifieronlinecr.azurecr.io/my-project-web:latest
    port: 80
    protected:
      mode: login
      exclude: ["/api"]      # ← EasyAuth skips /api/* paths; proxy forwards them directly
  api:
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000
    protected: validate      # ← The API service still enforces auth via token validation
```

Then redeploy:
```bash
amplifier-online up
```

**Key insight:** The API service has its own `protected: validate` enforcement, so the
excluded paths are still authenticated — just by the API service (via token) rather than by
EasyAuth on the web service (via redirect). The `exclude` field only removes the web service's
EasyAuth gate on those path prefixes.

---

## Failure Mode 12: SQLite Errors on Azure Files Volume

**Applies to:** `web-app-aca` and `web-app-awa` (both use Azure Files SMB-backed volumes).

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
amplifier-online logs --container api    # Look for "user not in authorized group" errors
# Check if the user is in a nested group (group-within-a-group)
```

**Root cause:** Azure Container Apps EasyAuth does not support **nested group membership**.
If a user is in GroupB, and GroupB is a member of GroupA, and the manifest lists GroupA as
the allowed group, EasyAuth will NOT recognize the user as authorized. Only direct membership works.

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

4. Re-run `amplifier-online up` to update EasyAuth configuration

**Note:** This is an Azure platform limitation, not an Amplifier Online bug. Nested groups do
not work with Container Apps EasyAuth or Static Web Apps authentication.

---

## Failure Mode 10: Custom Health Path Returns 401 (EasyAuth Blocks It)

**Symptom:** Deployment completes but Container App shows unhealthy, or Azure health probes fail:
```
Health probe failed: GET /healthz returned 401 Unauthorized
Container app revision failing: health check timeout
amplifier-online status shows: Revision: Failed
```

**Note:** The platform automatically excludes `/health` from EasyAuth enforcement. This failure
mode only applies if your app uses a **custom health path** (e.g., `/healthz`, `/ready`) that
is not auto-excluded.

**Diagnostic:**
```bash
amplifier-online logs --container api    # Look for repeated health probe requests
amplifier-online status                  # Check revision status
curl https://<app-url>/healthz           # Test from outside (will 401 if not excluded)
```

**Root cause:** EasyAuth is enabled on the Container App and your custom health path is not in
the excluded paths list. Azure's health probe doesn't send auth tokens, so it gets a 401 and
marks the container as unhealthy. The standard `/health` path is always excluded automatically,
but custom paths are not.

**Fix:** Add your custom health path to the service's `exclude` list:
```yaml
services:
  api:
    image: amplifieronlinecr.azurecr.io/my-project-api:latest
    port: 8000
    protected:
      mode: validate
      exclude: ["/healthz", "/ready"]    # Add custom health paths here
```

**Key insight:** `/health` is auto-excluded by the platform — you never need to list it. But if
your app uses a non-standard health path, you must explicitly exclude it.

**After fixing:**
1. Rebuild and push the updated container image
2. Re-run `amplifier-online up`
3. Verify with `amplifier-online status` — revision should show "Running"

---

