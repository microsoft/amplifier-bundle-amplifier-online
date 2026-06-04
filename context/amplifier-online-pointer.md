# Amplifier Online

**Amplifier Online** is the Azure Container Apps deployment system for shared team infrastructure.
It is distinct from **Amplifier** (this AI assistant platform). Never conflate the two.

## Hard Rules

1. **ALL deployment work MUST be delegated to `deployment-guide`.** Do not attempt
   to run `amplifier-online` CLI commands, write manifests, build Docker images,
   or troubleshoot deployments yourself. Delegate immediately.

2. **Manifests MUST be created with `amplifier-online init`.** Never hand-write
   `amplifier-online.yaml` via `write_file` or `create_file`. The CLI generates
   stack-correct templates with sensible defaults. Edits go through `edit_file`.

These rules apply even if the user gives step-by-step instructions.

## Core Concepts

- **Stack** — A deployment blueprint (e.g., `web-app-aca`) defining which Azure resources get provisioned.
- **Project** — Your application deployed via a stack; lives in your repo as `amplifier-online.yaml`.
- **Manifest** — The `amplifier-online.yaml` file describing containers, stack, and resources.

For guided deployment workflows, architecture details, and CLI reference, activate the `/amplifier-online` mode.
