# Amplifier Online — Mode Context

This document is loaded when the `/amplifier-online` mode is active. It supplements
the always-loaded pointer with architecture details, workflow guidance, and CLI reference.

## Three Layers

| Layer | What it is |
|-------|-----------|
| **Amplifier Online Platform** | Shared Azure infrastructure provisioned by operators (Container Apps Environment, ACR, Postgres, Cosmos DB, Key Vault) |
| **Amplifier Provisioner Service** | Backend API that runs as a Container App and handles stack provisioning and deployment |
| **Amplifier Online CLI** | `amplifier-online` command-line tool used by developers to deploy their projects |

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
amplifier-online init            # Scaffold amplifier-online.yaml from a stack template (--name, --stack)
amplifier-online up              # Deploy (add --dry-run to preview)
amplifier-online status          # Show deployed container apps and resources
amplifier-online logs            # Tail container logs (--since, --container)
amplifier-online destroy         # Tear down project resources (add --dry-run to preview)
amplifier-online cicd create     # Generate GitHub Actions workflows
```

## Delegation Reminder

**REQUIRED — not optional.** When the user asks anything about Amplifier Online —
deploying an app, stack selection, repo readiness, manifest creation or editing,
troubleshooting, or CI/CD setup — you MUST delegate to the `deployment-guide`
agent. Do not attempt these tasks yourself.

The `deployment-guide` agent carries the full domain knowledge and handles all
workflow scenarios: orientation, stack selection, first deployment,
troubleshooting, CI/CD setup, repo readiness checks, and project analysis.
