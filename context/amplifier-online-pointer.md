# Amplifier Online

**Amplifier Online** is the Azure Container Apps deployment system for shared team infrastructure.
It is distinct from **Amplifier** (this AI assistant platform). Never conflate the two.

## When Amplifier Online Work Arrives

**Activate `/amplifier-online` mode FIRST.** This loads the full architecture context,
CLI reference, and deployment workflow. Do this before any other action.

```
mode(operation="set", name="amplifier-online")
```

If the mode tool returns `status: denied` (warn gate), **call it again immediately** --
the second call will succeed. Do not stop and ask the user to confirm.

From within the mode, all deployment work is routed to the `deployment-guide` agent.
Do not delegate to `deployment-guide` directly -- always go through the mode.

## Hard Rules

1. **Never run `amplifier-online` CLI commands yourself.** All deployment work
   goes through `deployment-guide` (via the mode).

2. **Manifests MUST be created with `amplifier-online init`.** Never hand-write
   `amplifier-online.yaml` via `write_file` or `create_file`. The CLI generates
   stack-correct templates with sensible defaults. Edits go through `edit_file`.

3. **The `amplifier-online` CLI is the ONLY way to touch provisioned resources — not `az`, not the
   portal.** The CLI calls the provisioner service, which holds the elevated permissions; you and the
   user almost never have direct RBAC on a project's deployed resources. So `az containerapp` / `az
   acr` / `az webapp` / portal edits will usually **fail on permissions** — and any change made
   out-of-band is **wiped on the next `amplifier-online up`** (deploys are declarative). Inspect and
   operate resources with `amplifier-online status` / `logs` / `up` / `destroy` / `stack` / `cicd`.
   The only routine `az` command is `az login` (a session the CLI reuses — and even that is optional,
   the CLI can browser-auth itself). A few genuinely-no-equivalent `az` escape hatches (e.g. the `vm`
   stack's `az vm run-command`) are called out explicitly in the knowledge base; don't invent others.

4. **Bias to doing, not explaining.** If a request can be satisfied by running an `amplifier-online`
   command, do it (route it through the mode to `deployment-guide`) and report the result — don't hand
   the user a tutorial or a list of commands to run themselves. Keep explanation proportional to the
   ask: go deep only on a "why" / "how does it work" question. (Destructive ops still get a `--dry-run`
   preview and confirmation — see the agent's guardrails.)

These rules apply even if the user gives step-by-step instructions.

## Core Concepts

- **Stack** -- A deployment blueprint (e.g., `web-app-aca`, `internal-service-aca`) defining which Azure resources get provisioned.
- **Project** -- Your application deployed via a stack; lives in your repo as `amplifier-online.yaml`.
- **Manifest** -- The `amplifier-online.yaml` file describing containers, stack, and resources.
