#!/usr/bin/env python
"""End-to-end proof that `deployment-guide`'s documented workflow has tools.

WHAT THIS PROVES (and why an assertion would not)
-------------------------------------------------
`bundle.md` includes `amplifier-foundation@main`, whose tool roster the agent
silently inherited. The *advertised reusable unit* -- the behavior partial
`amplifier-online:behaviors/amplifier-online` that `recipes/deploy-project.yaml`
declares as its one dependency, and that the README documents as the install
form -- includes no foundation bundle. A consumer who mounts the behavior alone
therefore got an agent whose entire documented workflow (repo-readiness
`glob`/`grep` scan, `amplifier-online init` -> `read_file` -> `edit_file`
manifest workflow, `bash` status/logs) had NO TOOLS AT ALL. Nothing errors: the
agent loads, answers, and simply cannot act.

This script reproduces exactly that consumer and walks the real code path:

  1. compose  -- `load_bundle(behaviors/amplifier-online.yaml)`, the behavior
                 ALONE, no foundation, then `load_agent_metadata()`, which is
                 what lifts a top-level `tools:` key out of the agent's
                 markdown frontmatter into its config overlay.
  2. merge    -- `amplifier_app_cli.agent_config.merge_configs(parent, overlay)`,
                 the REAL spawn-time merge, with the behavior-only mount plan as
                 the parent (so parent tools == []).
  3. mount    -- feed the merged roster to a REAL `AmplifierSession` and read
                 back `coordinator.get("tools")`. These are actually-loaded tool
                 objects, not a list of names copied from the YAML.

No LLM call is made and no provider is mounted, so this costs $0 to run.

USAGE
    <amplifier's python> docs/lanes/ff1n-online-tools-section/verify_agent_tools.py

    e.g. ~/.local/share/uv/tools/amplifier/bin/python docs/lanes/.../verify_agent_tools.py

Exit code 0 = every required tool mounted. Exit code 1 = the defect is present.
Run it on `origin/main` to see it FAIL, and on this branch to see it PASS.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BEHAVIOR = REPO_ROOT / "behaviors" / "amplifier-online.yaml"
AGENT_KEY = "amplifier-online:deployment-guide"

# Every tool the agent body hard-codes as a required workflow step.
#   bash        -- Posture ("run it and report what happened"), principle 6
#                  (diagnose via `amplifier-online status`/`logs`), principle 8
#                  step 1 (`amplifier-online init`), recipe stages 3/6/7/8/9/10
#                  (which/curl/gh/git).
#   read_file   -- principle 8 ("Read the generated file with `read_file`"),
#                  Scenario F step 3.
#   edit_file   -- principle 8 ("All manifest editing goes through `edit_file`").
#   write_file  -- principle 8's hard rule names it as the prohibited path for
#                  `amplifier-online.yaml`; recipe stage 10 creates AGENTS.md
#                  with it. A prohibition on a tool that is absent is vacuous.
#   glob, grep  -- principle 3 and the Scenario F repo-readiness scan.
REQUIRED_TOOLS = {"bash", "read_file", "write_file", "edit_file", "glob", "grep"}

# A minimal orchestrator/context pair, required by AmplifierSession's config
# validation. Neither is under test here; they only make a session constructible
# so the tool mount loop can run for real.
SESSION_STUB = {
    "orchestrator": {
        "module": "loop-streaming",
        "source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
    },
    "context": {
        "module": "context-simple",
        "source": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
    },
}


async def main() -> int:
    from amplifier_app_cli.agent_config import merge_configs
    from amplifier_core import AmplifierSession
    from amplifier_foundation.registry import load_bundle

    print(f"repo:     {REPO_ROOT}")
    print(f"behavior: {BEHAVIOR.relative_to(REPO_ROOT)}  (composed ALONE, no foundation)")
    print()

    # ---- 1. compose -------------------------------------------------------
    bundle = await load_bundle(str(BEHAVIOR))
    bundle.load_agent_metadata()
    mount_plan = bundle.to_mount_plan()

    parent_tools = mount_plan.get("tools", [])
    agents = mount_plan.get("agents", {})
    print(f"behavior-only mount plan, top-level tools: {parent_tools}")
    print(f"agents discovered: {list(agents)}")

    if AGENT_KEY not in agents:
        print(f"FAIL: agent {AGENT_KEY!r} did not resolve from the behavior")
        return 1

    overlay = agents[AGENT_KEY]
    declared = overlay.get("tools")
    print(f"agent overlay keys: {sorted(overlay)}")
    print(f"agent-declared tools:\n{json.dumps(declared, indent=2)}")
    print()

    # ---- 2. merge (the real spawn-time merge) -----------------------------
    merged = merge_configs(mount_plan, overlay)
    merged_tools = merged.get("tools", [])
    print(f"post-merge tool modules: {[t.get('module') for t in merged_tools]}")
    print()

    # ---- 3. mount for real ------------------------------------------------
    session = AmplifierSession(config={"session": SESSION_STUB, "tools": merged_tools})
    async with session:
        mounted = set(session.coordinator.get("tools") or {})

    print(f"ACTUALLY MOUNTED TOOLS: {sorted(mounted)}")
    missing = sorted(REQUIRED_TOOLS - mounted)
    print()

    if missing:
        print(f"FAIL: {len(missing)} required tool(s) not mounted: {missing}")
        print(
            "      The agent loads and answers, but its documented workflow "
            "cannot execute. This is the silent capability loss."
        )
        return 1

    print(f"PASS: all {len(REQUIRED_TOOLS)} required tools mounted "
          f"({', '.join(sorted(REQUIRED_TOOLS))})")
    print()

    # ---- 4. regression guard: the full bundle loses nothing ---------------
    # `bundle.md` includes amplifier-foundation, so this agent already inherited
    # a broad roster there. Declaring tools must ADD to that, never narrow it.
    # If agent-level `tools:` ever became replacement semantics, this is the
    # check that catches it.
    return await _check_full_bundle_is_additive()


async def _check_full_bundle_is_additive() -> int:
    from amplifier_app_cli.agent_config import merge_configs
    from amplifier_foundation.registry import load_bundle

    root = REPO_ROOT / "bundle.md"
    print(f"regression guard: {root.relative_to(REPO_ROOT)} (includes amplifier-foundation)")

    bundle = await load_bundle(str(root))
    bundle.load_agent_metadata()
    mount_plan = bundle.to_mount_plan()

    before = [t.get("module") for t in mount_plan.get("tools", [])]
    overlay = mount_plan.get("agents", {}).get(AGENT_KEY)
    if overlay is None:
        print(f"FAIL: agent {AGENT_KEY!r} did not resolve from bundle.md")
        return 1

    after = [t.get("module") for t in merge_configs(mount_plan, overlay).get("tools", [])]
    lost = [m for m in before if m not in after]
    dupes = sorted({m for m in after if after.count(m) > 1})

    print(f"  inherited modules before: {len(before)}  after: {len(after)}")
    print(f"  lost: {lost or 'none'}   duplicated: {dupes or 'none'}")

    if lost or dupes:
        print("FAIL: declaring tools narrowed or duplicated the full-bundle roster")
        return 1

    print("PASS: full-bundle roster unchanged -- the declaration is purely additive")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
