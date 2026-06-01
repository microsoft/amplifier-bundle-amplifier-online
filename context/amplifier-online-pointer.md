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

These rules apply even if the user gives step-by-step instructions. The
`deployment-guide` agent carries the full domain knowledge (CLI reference, stack
docs, manifest schema, troubleshooting playbook) and will execute correctly.

## Three Layers

| Layer | What it is |
|-------|-----------|
| **Amplifier Online Platform** | Shared Azure infrastructure provisioned by operators (Container Apps Environment, ACR, Postgres, Cosmos DB, Key Vault) |
| **Amplifier Provisioner Service** | Backend API that runs as a Container App and handles stack provisioning and deployment |
| **Amplifier Online CLI** | `amplifier-online` command-line tool used by developers to deploy their projects |

## Core Concepts

- **Stack** — A deployment blueprint (e.g., `web-app-aca`). Defines what Azure resources get provisioned.
- **Project** — Your specific application deployed using a stack. Lives in your repo as `amplifier-online.yaml`.
- **Project Manifest** — The `amplifier-online.yaml` file in a project's root, describing containers, stack, and resources.

## Getting Started: Guided Deployment

**New to Amplifier Online?** Start with the guided deployment recipe:

```
"Help me deploy my app to Amplifier Online"
"Walk me through deploying this project"
```

The **deploy-project recipe** provides end-to-end guidance with approval gates at critical decision points:
1. **Project analysis** — Scans your code and recommends the right stack
2. **Stack selection** — Explains options and lets you choose
3. **Environment setup** — Verifies CLI, config, and Azure authentication
4. **Manifest creation** — Generates or validates `amplifier-online.yaml`
5. **Repo preparation** — Checks Dockerfiles, image format, health endpoints
6. **Build & push** — Guides container image builds (if applicable)
7. **Deployment** — Runs `amplifier-online up` with preview first
8. **Verification** — Tests health and troubleshoots if needed
9. **CI/CD setup** — Optional GitHub Actions workflow generation

**For specific questions**, ask directly:
- "Which stack should I use for my app?" → Project analysis + stack recommendation
- "Is my repo ready to deploy?" → Repo readiness checklist
- "How do I fix deployment error X?" → Troubleshooting with playbook
- "Set up CI/CD for automatic deployments" → GitHub Actions workflow generation

## CLI Quick Reference

```
amplifier-online config          # Set global config (~/.amplifier-online/config.yaml)
amplifier-online stack list      # List available deployment stacks
amplifier-online stack manifest  # Show default manifest template for a stack
amplifier-online init            # Scaffold amplifier-online.yaml from a stack template
amplifier-online up          # Deploy (add --dry-run to preview)
amplifier-online status      # Show deployed container apps and resources
amplifier-online logs        # Tail container logs (--since, --container)
amplifier-online destroy     # Tear down project resources (add --dry-run to preview)
amplifier-online cicd create # Generate GitHub Actions workflows
```

## Delegate to deployment-guide

**REQUIRED — not optional.** When the user asks anything about Amplifier Online —
deploying an app, stack selection, repo readiness, manifest creation or editing,
troubleshooting, or CI/CD setup — you MUST delegate to the `deployment-guide`
agent. Do not attempt these tasks yourself.

The `deployment-guide` agent carries the full domain knowledge and handles all
workflow scenarios: orientation, stack selection, first deployment,
troubleshooting, CI/CD setup, repo readiness checks, and project analysis.
