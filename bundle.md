---
bundle:
  name: amplifier-online
  version: 2.0.0
  description: DEPRECATED bridge to Amplifier Online v2 — sets up the CLI and its deploy skill, offers to upgrade v1 projects, then to remove itself

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: amplifier-online:behaviors/amplifier-online
---

# Amplifier Online Assistant

@foundation:context/shared/common-system-base.md
