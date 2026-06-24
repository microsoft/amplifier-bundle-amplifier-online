# Amplifier Online Bundle

Developer assistant for **Amplifier Online** -- deploy projects onto shared Azure Container Apps infrastructure using guided AI workflows.

This bundle turns Amplifier into an expert deployment guide. It does not deploy anything itself; it makes your AI assistant knowledgeable about how to use the `amplifier-online` CLI to deploy your projects onto shared Azure infrastructure.

## Installation

```bash
amplifier bundle add "git+https://github.com/microsoft/amplifier-bundle-amplifier-online@main#subdirectory=behaviors/amplifier-online.yaml" --app
```

## Prerequisites

- [Amplifier CLI](https://github.com/microsoft/amplifier) installed
- [Amplifier Online CLI](https://github.com/microsoft-amplifier/amplifier-online) installed (`uv tool install git+https://github.com/microsoft-amplifier/amplifier-online@main`)
- Azure credentials configured (interactive browser or `az login`)

## Usage

Once the bundle is installed, activate the deployment assistant by entering the mode:

```
/amplifier-online
```

This loads the full deployment knowledge base into your session. From there you can ask things like:

- "Help me deploy this project"
- "What stack should I use for a React + FastAPI app?"
- "Show me the manifest schema"
- "Why is my container failing health checks?"

### Guided Deployment Recipe

For a full end-to-end deployment with approval gates at each stage:

```
run the deploy-project recipe
```

This walks through 9 stages: project analysis, stack selection, environment setup, manifest creation, readiness checks, container build/push, deployment, verification, and optional CI/CD setup.

### Direct Agent Delegation

For specific questions, the `deployment-guide` agent is available via the mode. It carries detailed knowledge about:

- CLI command reference
- Stack comparison (web-app-aca, internal-service-aca, web-app-awa, static-web-app)
- Manifest schema and examples
- Troubleshooting playbook (18 named failure modes)
- CI/CD setup with GitHub Actions
- MSAL.js frontend authentication

## What's Included

```
bundle.md                       # Root bundle entry point
behaviors/
  amplifier-online.yaml         # Behavior: activates agent, mode, and context
agents/
  deployment-guide.md           # Expert deployment agent (context sink)
modes/
  amplifier-online.md           # /amplifier-online mode definition
recipes/
  deploy-project.yaml           # 9-stage guided deployment recipe
context/
  amplifier-online-pointer.md   # Always-loaded orientation context
  amplifier-online-mode-context.md  # Mode-scoped architecture + CLI reference
  agent/                        # Heavy knowledge base (loaded by agent only)
    cli-reference.md
    stacks-reference.md
    manifest-schema.md
    project-analysis.md
    troubleshooting-playbook.md
    cicd-guide.md
    msal-authentication-guide.md
    authorization-guide.md
```

## Supported Stacks

| Stack | Use Case |
|-------|----------|
| `web-app-aca` | Multi-container apps on Azure Container Apps (backend + frontend both containerized) |
| `internal-service-aca` | Internal-only Azure Container App -- no public ingress, JWT/managed-identity auth, optional Postgres/Cosmos/Redis/Storage |
| `web-app-awa` | Container backend + Static Web App frontend (GitHub-integrated CI/CD, PR previews) |
| `static-web-app` | Pure static sites with no backend |

---

## Contributing

Due to the rapid AI-driven development of this project, we are not accepting external contributions at this time. If you're interested in contributing or have feedback, please reach out to the maintainers directly.

---

## Legal

### Code of Conduct
This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

### Trademarks
This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).

### Privacy
See [Microsoft Data Privacy Notice](http://go.microsoft.com/fwlink/?LinkId=518021).