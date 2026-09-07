#!/usr/bin/env python
"""Run ONLY the deterministic (`type: bash`) phases of validate-agents.

WHY THIS EXISTS
---------------
`validate-agents` v1.8.0 computes every finding that matters here --
`NO_TOOLS_SECTION`, the discovered agent count, and `quality_level` -- in four
plain `type: bash` Python steps. The four `agent:` steps after them only narrate
what those steps already decided (`quality-classification` sets
`requires_llm_analysis` itself). Running just the bash phases therefore gives the
same numbers with no LLM call, no cost, and no dependence on the calling
session's agent map -- which is what makes a fail-before / pass-after pair over
two git revisions affordable and exactly reproducible.

This is NOT a reimplementation: the step commands are read verbatim out of the
recipe file and executed in order, with the same `{{var}}` substitution the
engine performs on their outputs. If the recipe changes, this follows.

USAGE
    <amplifier's python> run_validate_agents_deterministic.py <repo_path> [recipe_path]

    Default recipe_path is the cached foundation copy this session resolves
    `@foundation:recipes/validate-agents.yaml` to.

Prints the verdict-relevant fields and exits non-zero if `NO_TOOLS_SECTION`
appears for any agent.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_RECIPE = Path.home() / (
    ".amplifier/cache/amplifier-foundation-c909465861f9d6ce/recipes/validate-agents.yaml"
)

# The deterministic prefix, in recipe order. Everything after
# quality-classification is either a default-setter or an LLM narration step.
BASH_STEPS = [
    "environment-check",
    "agent-discovery",
    "structural-validation",
    "quality-classification",
]


def substitute(command: str, context: dict) -> str:
    """Replace {{name}} and {{name.attr}} the way the recipe engine does."""

    def repl(match: re.Match[str]) -> str:
        parts = match.group(1).split(".")
        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return match.group(0)
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return re.sub(r"\{\{(\w+(?:\.\w+)*)\}\}", repl, command)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    repo_path = str(Path(argv[1]).resolve())
    recipe_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_RECIPE

    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    steps = {s["id"]: s for s in recipe["steps"]}
    print(f"recipe:  {recipe_path}")
    print(f"version: {recipe.get('version')}")
    print(f"repo:    {repo_path}")
    print()

    context: dict = {"repo_path": repo_path}
    for step_id in BASH_STEPS:
        step = steps[step_id]
        command = substitute(step["command"], context)
        proc = subprocess.run(
            ["bash", "-c", command], capture_output=True, text=True, timeout=300
        )
        if proc.returncode != 0:
            print(f"step {step_id} exited {proc.returncode}\n{proc.stderr}")
            return 1
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        context[step["output"]] = payload

    discovery = context["discovery_results"]
    structural = context["structural_results"]
    quality = context["quality_classification"]

    print(f"agents discovered: {discovery['total_count']} "
          f"(candidates scanned {discovery['candidates_scanned']}, "
          f"non-agents {discovery['non_agent_count']})")
    print(f"locations: {discovery['location_counts']}")
    print(f"structural summary: {structural['summary']}")
    print(f"quality_level: {quality['quality_level']}   summary: {quality['summary']}")
    print()

    exit_code = 0
    for agent in structural["agents"]:
        codes_e = [e["code"] for e in agent["errors"]]
        codes_w = [w["code"] for w in agent["warnings"]]
        print(f"- {agent['name']} ({agent['relative_path']})")
        print(f"    has_explicit_tools: {agent['has_explicit_tools']}   "
              f"tools_source: {agent['tools_source']}")
        print(f"    ERRORS:   {codes_e or 'none'}")
        print(f"    WARNINGS: {codes_w or 'none'}")
        if "NO_TOOLS_SECTION" in codes_w:
            exit_code = 1

    print()
    print("NO_TOOLS_SECTION: " + ("PRESENT" if exit_code else "CLEARED"))
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
