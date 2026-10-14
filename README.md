# Amplifier Online Bundle (deprecated)

> **Deprecated: a temporary bridge from Amplifier Online v1 to v2.** Once it
> has set up the CLI and the `amplifier-online-deploy` skill, the skill does
> everything (including upgrading v1 projects) and the bundle offers to remove
> itself. By hand: `amplifier bundle remove amplifier-online-behavior`,
> `amplifier bundle remove amplifier-online`, and (if you added it with `--app`)
> `amplifier bundle remove amplifier-bundle-amplifier-online --app`.
> New users: install the CLI and run `amplifier-online install-skill` instead.

Makes Amplifier ready for **Amplifier Online v2**, the platform that puts a
team's project online in Microsoft's tenant (tenant-only sign-in, keyless
databases, deploys through Azure Pipelines).

The bundle is a thin on-ramp. When Amplifier Online work comes up, its
`/amplifier-online` mode has the assistant:

1. update the `amplifier-online` CLI (an old v1 CLI upgrades to v2) and run
   `amplifier-online install-skill`;
2. load the **`amplifier-online-deploy`** skill, which ships with the CLI and
   always matches its version, and follow it;
3. if the repo is still an **AO v1 project**, offer to upgrade it (same app
   names, URLs and sign-in), showing what changes before anything is touched.

## Installation

```bash
amplifier bundle add "git+https://github.com/microsoft/amplifier-bundle-amplifier-online@main#subdirectory=behaviors/amplifier-online.yaml" --app
```

You need [uv](https://docs.astral.sh/uv/) and the Azure CLI (`az login`); the
mode installs or updates the Amplifier Online CLI itself.

## Usage

Ask about deploying or upgrading a project, or enter the mode directly:

```
/amplifier-online
```

- "Put this project on Amplifier Online"
- "Upgrade this project from Amplifier Online v1 to v2"
- "Why is my deploy failing?"

## Without Amplifier

The skill works in other agents too (Claude Code, Codex, OpenCode):
`amplifier-online install-skill`. Upgrading by hand:
[docs/upgrading-from-v1.md](https://github.com/microsoft/amplifier-online/blob/main/docs/upgrading-from-v1.md).

## v1

Version 1.x of this bundle taught AO v1 (stacks, GitHub Actions deploys); it
is preserved at the `v1` tag.
