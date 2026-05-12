# Amplifier Online

**Amplifier Online** is the Azure Container Apps deployment system for shared team infrastructure.
It is distinct from **Amplifier** (this AI assistant platform). Never conflate the two.

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

## CLI Quick Reference

```
amplifier-online config      # Set global config (~/.amplifier-online/config.yaml)
amplifier-online stacks      # List available deployment stacks
amplifier-online init        # Scaffold amplifier-online.yaml from a stack template
amplifier-online up          # Deploy (add --dry-run to preview)
amplifier-online status      # Show deployed container apps and resources
amplifier-online logs        # Tail container logs (--since, --container)
amplifier-online destroy     # Tear down project resources (add --dry-run to preview)
amplifier-online cicd create # Generate GitHub Actions workflows
```

## Delegate to deployment-guide

For ANY depth question about Amplifier Online — stack selection, repo readiness, manifest
authoring, deployment walkthroughs, troubleshooting, or CI/CD setup — delegate to the
`deployment-guide` agent. It carries the full domain knowledge and handles all 6 workflow
scenarios: orientation, stack selection, first deployment, troubleshooting, CI/CD setup,
and repo readiness checks.
