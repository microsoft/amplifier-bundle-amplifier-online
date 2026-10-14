---
mode:
  name: amplifier-online
  description: Deploy, update or upgrade a project on Amplifier Online (v2), via the amplifier-online-deploy skill
  tools:
    safe:
      - read_file
      - edit_file
      - write_file
      - bash
      - grep
      - glob
      - todo
      - mode
      - web_fetch
      - LSP
      - python_check
      - load_skill
      - delegate
  default_action: warn
  contributes:
    context:
      - amplifier-online:context/amplifier-online-mode-context.md
---

# Amplifier Online Mode

You are in Amplifier Online mode. First make sure the CLI and its skill are
current, then load the `amplifier-online-deploy` skill and follow it (see the
mode context). If the repo is still an AO v1 project, offer to upgrade it
before anything else.

The skill is the source of truth for commands, the manifest, builds and
troubleshooting; where anything you remember about AO (stacks, `init`,
GitHub Actions deploys) disagrees with it, the skill wins — that was v1.
