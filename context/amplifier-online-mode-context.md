# Amplifier Online — mode context

Amplifier Online is now **v2**. Everything about using it lives in the
**`amplifier-online-deploy` skill**, which ships with the `amplifier-online`
CLI and always matches its version. This mode gets the CLI and skill current,
then hands over to the skill.

## 1. Get the CLI and the skill current (once per session)

These are routine; run them (no need to ask first) and tell the user what
changed:

```bash
amplifier-online update
amplifier-online --help | grep -q install-skill || uv tool install --force "git+https://github.com/microsoft/amplifier-online#subdirectory=cli"
amplifier-online install-skill
```

- `update` upgrades an install made from `main`; an old v1 CLI installed that
  way comes out as v2. A CLI that was pinned to a branch (e.g. `@v1`) stays
  where it is, and a v1 CLI has no `install-skill` command: then the second
  line reinstalls it from `main`. Always install from `main` with no
  `@<branch>`; never `@v1` or `@v2`. If `amplifier-online` isn't installed at
  all, the second line installs it (needs [uv](https://docs.astral.sh/uv/)).
- `install-bundle` is the old v1 command; don't use it.
- The first v2 command moves a v1 config to v2 and says so; that's expected.
- `install-skill` copies the skill into `~/.amplifier/skills` (and other
  agents' skill folders).

Then load it and follow it for everything that follows:

```
load_skill(skill_name="amplifier-online-deploy")
```

If `load_skill` doesn't find it (a skill installed mid-session may not be
listed yet), read `~/.amplifier/skills/amplifier-online-deploy/SKILL.md`
directly, and its `references/` files as it points to them.

## This bundle is deprecated: tell the user once

This bundle only bridges users from AO v1 to v2. Once the skill is installed
it adds nothing: the skill handles Amplifier Online from then on, including
upgrading other v1 projects. So, **once per session**, after the CLI and skill
are set up (or straight away if `~/.amplifier/skills/amplifier-online-deploy`
already existed when the mode started), and without interrupting the task at
hand, tell the user:

> The Amplifier Online bundle was a temporary bridge to AO v2 and is now
> deprecated: your CLI and its skill are set up, and the skill handles
> Amplifier Online (including upgrading other v1 projects) from here. Want me
> to remove the bundle?

Only on a yes:

1. `amplifier bundle current`: if the active bundle is `amplifier-online`,
   ask which bundle to switch to (`amplifier bundle use <name>`) first.
2. Remove it under each name it can be registered with (one that isn't
   registered just reports "not found"):
   ```bash
   amplifier bundle remove amplifier-online-behavior
   amplifier bundle remove amplifier-online
   amplifier bundle remove amplifier-bundle-amplifier-online --app
   ```
   The names come from this bundle's own `bundle.name` fields; `--app`
   matches any app registration whose URI contains the repo name.
3. Tell the user it takes effect in their next session.

Don't repeat the offer in the same session.

## 2. Is this a v1 project?

A repo is still on **AO v1** if its `amplifier-online.yaml` has a `stack:`
key, or it has `.github/workflows/<project>-*-build-deploy.yaml` (or an Azure
Static Web Apps) workflow that deploys to Amplifier Online.

If so, tell the user plainly, before doing anything else:

> This project is still on Amplifier Online v1. v1 keeps running it for now,
> but v2 replaces it: same app names, URLs and sign-in, deploys through Azure
> Pipelines, and usually small Dockerfile changes. Want me to upgrade it?
> I'll show you what changes before anything is touched.

On a yes, follow the skill's `references/adoption.md` (upgrade on a branch,
`manifest migrate`, Dockerfiles, `up --adopt --dry-run`, then adopt and
deploy), asking before `up --adopt` as the skill says. On a no, help with
what they asked; a v1 project can't be changed with the v2 CLI until it is
upgraded (the provisioner answers `PROJECT_MANAGED_BY_V1`).

## 3. Otherwise

Follow the skill: analyze the repo, write the manifest, `up`, `deploy`,
verify. For the user's background, the human guide is
https://github.com/microsoft/amplifier-online/blob/main/docs/upgrading-from-v1.md
(for upgrades) and https://github.com/microsoft/amplifier-online (in general).
