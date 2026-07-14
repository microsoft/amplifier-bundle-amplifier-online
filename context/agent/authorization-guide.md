# Authorization Guide for Amplifier Online

This guide covers the **authorization** layer for projects deployed via Amplifier Online:
once a user is authenticated (by EasyAuth on web frontends or MSAL.js for SPAs — see
`msal-authentication-guide.md`), how the application decides *what that user is allowed to
do*. Authorization runs in application middleware using claims already present in the
validated JWT — the tenant blocks the calls that platform-level group enforcement would need.

**The one rule that matters most:** authorize on the **`roles`** claim (app roles), not on
`groups`. Group claims silently break for some users; app roles never do. The rest of this
guide explains why, and how to read identity and claims correctly.

---

## App Roles vs Group Claims

App roles are the **primary** authorization mechanism. Group claims are a fallback that
only works for a subset of users.

| Property | Group claims (`groups`) | App roles (`roles`) |
|---|---|---|
| Subject to the 200-group overage | **Yes** | No |
| Requires a Graph OBO call to resolve (when overage hits) | Yes | Never |
| Requires a client secret (blocked by tenant policy) | Yes (when overage) | No |
| Always present in the token | **No** | Yes |

### Why group claims break: the 200-group overage

With `groupMembershipClaims: "SecurityGroup"`, Entra emits group OIDs in the `groups`
claim. But a user who belongs to **more than 200 security groups receives NO `groups`
claim at all**:

- It is **silent** — no error. The claim is simply absent.
- Instead the token carries `_claim_names` / `_claim_sources` pointing at a Graph endpoint.
- Resolving that endpoint needs an On-Behalf-Of (OBO) call, which needs a client secret —
  and client secrets are blocked tenant-wide. There is no way to resolve it.

So group-based authorization silently fails for heavily-grouped users, and you cannot
detect it at authorization time. **App roles emit a `roles` claim that is never subject to
overage** — this is the core reason to prefer them.

### Configuring app roles

Define app roles on the Entra app registration (Azure portal → **App roles**, or the app
manifest). Conventional setup:

| Role | Value in `roles` claim | Purpose |
|---|---|---|
| Admin | `Admin` | Full access |
| User | `User` | Standard access |

Assign roles to **security groups** under **Enterprise Applications → [your app] → Users
and groups → Add user/group**, then pick the role.

### Group claims as fallback

Group claims are usable only when the user is in **fewer than 200** groups *and* the group
is a pure security group (see below). Use `"SecurityGroup"` for `groupMembershipClaims`, not
`"All"` — `"All"` bloats the token and pulls in distribution/Office groups. Nested group
membership does **not** traverse (`AADSTS50105`); users must be direct members — see
`troubleshooting-playbook.md`.

---

## The #1 Authorization Bug: Mail-Enabled Groups Silently Fail

This is the single most common authorization debugging problem. Assigning a **mail-enabled**
security group to an app role:

1. Returns HTTP 201 (success) from Graph,
2. Shows the assignment correctly in the Azure portal,
3. but **never emits the `roles` claim** for members of that group.

There is no error anywhere — the assignment looks correct, users just never get the role.
Only **pure security groups** work for role assignment:

| Property | Required value |
|---|---|
| `mailEnabled` | `false` |
| `securityEnabled` | `true` |
| `groupTypes` | `[]` (empty — no `"Unified"`) |

Check a group before assigning:

```bash
az rest --method GET \
  --uri "https://graph.microsoft.com/v1.0/groups/{groupId}" \
  --query '{mailEnabled:mailEnabled,groupTypes:groupTypes,securityEnabled:securityEnabled}'
```

If `mailEnabled` is `true` or `groupTypes` contains `"Unified"`, the group will not work —
recreate it as a pure security group.

---

## Reading Identity: OID-First

When you need to *identify* a user (key a record, bind a profile, write an audit entry), use
the **`oid`** — the tenant-wide Entra object ID. It is immutable and survives email/UPN
changes. Everything else is display.

| Source | Carries | Use as identity key? |
|---|---|---|
| `oid` (JWT) / `X-MS-CLIENT-PRINCIPAL-ID` (header) | The user's Entra object ID | **Yes** — stable, immutable |
| `preferred_username` (JWT) | UPN / email | No — mutable, display only |
| `name` (JWT) / `X-MS-CLIENT-PRINCIPAL-NAME` (header) | Display name | No — display only |

Note `X-MS-CLIENT-PRINCIPAL-ID` carries the `oid`, **not** the app-pairwise `sub`, and
`X-MS-CLIENT-PRINCIPAL-NAME` is the display `name`, **not** the email. Never key identity or
authorization off `-NAME` or email.

---

## Reading Claims: Use the JWT, Not the Header

Two ways to read a request's identity and claims — they are not equivalent.

**Read authorization claims (`roles`, `groups`) from the validated JWT** in the
`Authorization: Bearer` header. It gives you structured arrays with a uniform shape across
the ACA and AWA stacks.

**Do not trust the `X-MS-CLIENT-PRINCIPAL` header for authorization.** It is an
**unsigned** base64-encoded JSON blob that EasyAuth injects — not a cryptographically
verifiable JWT. Its `claims` field is a **list of `{typ, val}` objects** (not a dict keyed
by claim name), and the `typ` may be either a full URI
(`http://schemas.microsoft.com/ws/2008/06/identity/claims/role`) or a short name (`roles`),
so any code reading it must handle both:

```json
{
  "claims": [
    {"typ": "http://schemas.microsoft.com/ws/2008/06/identity/claims/role", "val": "Admin"},
    {"typ": "preferred_username", "val": "jdoe@contoso.com"}
  ]
}
```

### Why the header isn't trustworthy server-to-server

The `X-MS-CLIENT-PRINCIPAL` header is trustworthy **only because EasyAuth is the sole
inbound path** on a public web container — EasyAuth sets it after authenticating. But
**container-to-container traffic inside the Container Apps Environment bypasses EasyAuth
entirely** and can set that header to anything. This is exactly why **API services validate
a signed JWT in-app** (signature via JWKS, `aud=api://{client_id}`, issuer, expiry) rather
than relying on the injected header. For internal service-to-service calls, the callee
validates the JWT and checks the `azp` claim against an allowed-callers whitelist — see the
internal-service auth section in `stacks-reference.md`.

---

## Middleware Pattern and Environment Variables

The platform's `jwt_middleware.py` template follows this order:

```
# --- Identity (from the validated JWT, or scalar EasyAuth headers) ---
#   id   = oid   (X-MS-CLIENT-PRINCIPAL-ID) — stable identity key
#   name = name  (X-MS-CLIENT-PRINCIPAL-NAME) — display only, do NOT key off it
# --- Authorization ---
#   1. Check the `roles` claim FIRST (primary, never subject to overage)
#   2. Fall back to the `groups` claim (secondary)
#   3. Match against ADMIN_ROLE/USER_ROLE, then ADMIN_GROUP/USER_GROUP
#   4. No match → 403 FORBIDDEN before the route handler runs
#   5. Match → request.state.user = UserIdentity(name, id=oid, roles, groups)
```

Authorization is configured entirely through environment variables (no code changes to add
an admin):

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_ROLE` | `"Admin"` | `roles` value granting admin access |
| `USER_ROLE` | `"User"` | `roles` value granting standard access |
| `ADMIN_GROUP` | (none) | Group OID granting admin (fallback, only when roles absent) |
| `USER_GROUP` | (none) | Group OID granting standard (fallback, only when roles absent) |
| `ENVIRONMENT` | (none) | Set to `development` to inject a fake identity for local dev (bypasses token validation) |

Because `roles` is checked before `groups`, configuring `ADMIN_ROLE`/`USER_ROLE` plus app
role assignments is the recommended setup; the `*_GROUP` vars exist only for environments
where app roles aren't configured.

---

## Why Not EasyAuth's Built-In Group Enforcement?

EasyAuth supports `allowedPrincipals.groups`, which would enforce group membership at the
platform level before the request reaches your code. **It does not work in this tenant:** it
triggers an OBO call to Graph to resolve membership, and that OBO call requires a client
secret — blocked by tenant policy. Authorization must therefore live in application
middleware, using claims already in the token. No additional Graph calls are possible at
request time.

---

## Claims Are Evaluated at Token Issuance — Clear the Cache After Changes

Role and group assignments are baked into the token **when it is issued**. If you change a
user's roles or groups (or an app's scopes/permissions), their existing cached tokens still
carry the old claims — the user keeps seeing the old behavior until they get a fresh token.

Clear the cache and re-authenticate:

```bash
# CLI users
az account clear && rm -f ~/.azure/msal_token_cache.*
az login
```

```javascript
// Browser users (then sign out and back in)
localStorage.clear();
```

Even after a clean re-login, an assignment change can take a few minutes to appear due to
Entra directory replication. This cache-clear applies to **any** claims change — roles,
groups, *or* scope/permission edits — not just group changes.

---

## See Also

- `msal-authentication-guide.md` — how SPAs authenticate and acquire Bearer tokens
- `stacks-reference.md` — internal service-to-service auth (`azp` whitelist, MI tokens)
- `user-resource-access-guide.md` — how a **backend/long-running service** acts on a user's M365
  resources (why no server-side token broker; app identity / capability / forwarded token / HITL)
- `troubleshooting-playbook.md` — diagnosing specific authorization failures (`AADSTS50105`,
  missing `roles`, group overage)
