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
2. Update `amplifier-online.yaml`:
   ```yaml
   containers:
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
