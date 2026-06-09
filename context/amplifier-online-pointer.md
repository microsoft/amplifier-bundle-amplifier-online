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

These rules apply even if the user gives step-by-step instructions.

## Core Concepts

- **Stack** -- A deployment blueprint (e.g., `web-app-aca`) defining which Azure resources get provisioned.
- **Project** -- Your application deployed via a stack; lives in your repo as `amplifier-online.yaml`.
- **Manifest** -- The `amplifier-online.yaml` file describing containers, stack, and resources.
