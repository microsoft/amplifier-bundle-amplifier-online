# User-Resource Access Guide for Amplifier Online

How a **backend or long-running service** acts on a logged-in user's Microsoft 365 resources
(OneDrive, SharePoint, Teams, Outlook, Graph) — *after* the user has left, or from a service
with no browser. This is a different problem from a SPA calling Graph on the user's device
(that is `msal-authentication-guide.md` and the `static-web-app` Graph section in
`stacks-reference.md`).

## The one hard rule: a backend cannot hold a user's delegated token

This tenant enforces Conditional Access **token protection** (token binding). A user's sign-in
and **refresh** tokens are cryptographically bound to the device they were issued on. A
backend/native sign-in is refused outright with **`AADSTS530084`**, and a captured refresh token
cannot be redeemed off the originating device.

**Never propose or build any of these** — they are impossible in this tenant, not merely
discouraged:

- ❌ A server-side **token broker / token vault** that stores users' delegated (refresh) tokens
  and redeems them on a schedule.
- ❌ **On-Behalf-Of (OBO)** — a confidential-client flow that also needs a client secret (blocked).
- ❌ The **EasyAuth token store** (`/.auth/me` returning access tokens) — disabled by tenant policy.
- ❌ **Device code** flow for a headless service — blocked by Conditional Access.

If a user asks to "store the user's token in the backend and refresh it" or "have the service
act as the user in the background," **explain that token protection makes that impossible** and
steer to the patterns below. Do not generate code that stores or refreshes a user's Graph token
server-side — it will fail at runtime. (The short-lived **access** token is *not* device-bound —
see pattern D — but it cannot be renewed server-side.)

## The four patterns that DO work

Pick by two questions: **does the job outlive the user's session?** and **must the action be
attributed to the user?**

| Pattern | Use it for | Attribution | Duration |
|---|---|---|---|
| **App identity + user-as-context** | Unattended / long-running reads and app-attributed writes (nightly SharePoint sync, scheduled transcript reads, indexing a drive). | App, not the user | Unbounded |
| **User-minted capability** | A user-attributed write to *one known resource*, later (drop a report into the user's OneDrive). | User | The capability's window (hours–days) |
| **Forwarded access token** | Genuine "on behalf of" work that finishes while the user is still around. | User (exact perms) | ~60–90 min, not renewable server-side |
| **Human-in-the-loop** | Delegated-only ops that must be the user (send a Teams/chat message *as* them). | User | Gated on a human per step |

### App identity + user-as-context (the workhorse)

The service authenticates **as itself** — its own app registration — via the
**federated-credential pattern** (the provisioner's model): the managed identity gets a token for
`api://AzureADTokenExchange`, presents it as a client assertion to authenticate as an app
registration that holds the Graph permission, and receives an **app-only** Graph token. No secret.
Because there is no user sign-in, token protection does not apply, so it runs unbounded.

It uses Graph **application** permissions, which are **tenant-wide by default** and MUST be scoped:

- `Sites.Selected` — per-SharePoint-site grants (the app has no access until granted a role on a site).
- `Files.SelectedOperations.Selected` — per-item file operations.
- Exchange `ApplicationAccessPolicy` — restrict the app to named mailboxes.
- Teams **RSC** (resource-specific consent) — per-team/-chat.

The user's identity (`oid`, from the forwarded validated JWT) is carried only as **authorization
context** and for audit — the Graph call is app-only, so Graph / DLP / sharing see the app, not the
user. Confirm app-attribution is acceptable before using this for writes.

### User-minted capability (user-attributed writes, no custody)

While the user is present (in the browser, on their device), they mint a pre-authorized artifact
the backend later redeems with **no token at all**:

- `createUploadSession` → an `uploadUrl` the backend `PUT`s to with no `Authorization` header.
- A sharing link, or an item-permission grant to the app's service principal.

Scoped to one resource, expires after a window, nothing stored server-side. Only works for
operations that *have* such an artifact — it authorizes one door, not the building.

### Forwarded access token (sub-hour, user present)

The frontend acquires the delegated Graph **access** token in the browser (MSAL, on the user's
device) and forwards it to the backend, which uses it off-device until it expires (~60–90 min).
Genuine "on behalf of," the user's exact permissions. **Not renewable server-side** — for anything
unattended or resumable, use app identity or a capability instead.

### Human-in-the-loop

For delegated-only operations that must be the user (e.g. posting a Teams message *as* them),
pause the job and have the user re-authorize on their device.

## Consent is a human admin step — the CLI cannot grant it

Any Graph permission beyond basic sign-in (`openid` / `profile` / `email`) — delegated resource
scopes AND all application permissions — requires a **one-time tenant-admin consent** on the app
registration. User self-consent is disabled in this tenant, and **neither `amplifier-online up`
nor the provisioner can grant it** (the provisioner holds `Application.ReadWrite.OwnedBy`, which
has no consent rights). When a design needs new Graph permissions, tell the user it requires a
tenant admin to consent them once — do not imply the CLI will do it.

## Carrying user identity across a service hop

Frontend → backend identity is carried by **forwarding the user's validated `api://…-api` JWT**
(the token the frontend already holds). The backend validates it against Entra's JWKS with its JWT
middleware (see `authorization-guide.md`) and trusts `oid` / claims from it — no secret needed,
Entra signed it. This *identity* JWT has the wrong audience to call Graph; it is distinct from any
*Graph* access token forwarded for pattern D.

## Decision guide

- Runs after the user leaves, app attribution acceptable → **App identity**.
- Write one known file/item as the user, later → **User-minted capability**.
- Finishes within ~1 hour, must be the user, exact permissions → **Forwarded access token**.
- Must act *as* the user (send a message) → **Human-in-the-loop**.
- Wants a background token broker for Microsoft resources → **impossible; explain token protection**.

## See Also

- `msal-authentication-guide.md` — the browser/SPA side: how a user signs in and a frontend
  acquires delegated tokens.
- `stacks-reference.md` — "Calling Microsoft Graph or other external APIs" (SWA/frontend), and
  internal service-to-service auth (`azp` whitelist + MI tokens).
- `authorization-guide.md` — reading identity/claims, roles-vs-groups authorization.
- Platform source of truth: `amplifier-online/docs/design/long-running-delegated-access.md`, and
  the masterclass Module 10 "Server-Side Work on Behalf of a User" (tenant constraint #13, token
  protection).
