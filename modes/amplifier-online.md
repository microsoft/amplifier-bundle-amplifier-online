---
mode:
  name: amplifier-online
  description: Guided Amplifier Online deployment setup and management
  contributes:
    context:
      - amplifier-online:context/amplifier-online-mode-context.md
---

# Amplifier Online Mode

You are in Amplifier Online deployment mode. The full architecture overview, CLI reference, and guided deployment workflow are now available in your context.

## When to Launch the Recipe

If the user wants an end-to-end guided deployment, launch the deploy-project recipe:

```
recipes(operation="execute", recipe_path="@amplifier-online:recipes/deploy-project.yaml")
```

## When to Delegate Directly

For targeted questions (stack selection, troubleshooting, CI/CD setup, repo readiness), delegate to `deployment-guide` without the recipe:

```
delegate(agent="amplifier-online:deployment-guide", instruction="<user's question>", context_depth="recent")
```

## Reminder

ALL deployment work goes through `deployment-guide`. Do not run `amplifier-online` CLI commands, write manifests, or troubleshoot deployments yourself.
