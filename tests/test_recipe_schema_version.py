"""Lint: every shipped recipe that references an agent must be schema v2.

Why this exists
---------------
A recipe without ``schema_version: 2`` is a *legacy* recipe. Its ``agent:``
references resolve from the CALLING session's agent map, so it only runs from a
bundle that already carries those agents -- shipping one from this repo means it
breaks for anyone who installs the recipe without the bundle. Declaring
``schema_version: 2`` plus a ``dependencies`` closure makes resolution
closed-world (contract ``recipe-dependency-manifest.v1``, Core 3), so the recipe
runs from any session bundle.

The engine never infers a dependency from an agent's namespace prefix (Core 11),
so a recipe referencing this bundle's own agents must still declare a
self-referential dependency. That is what the third check below enforces.

Run with::

    python -m pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Iterator

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = REPO_ROOT / "recipes"

# Files deliberately left as legacy recipes, each with the reason why.
# A recipe using `agent: self` cannot be made v2-safe (the closed-world resolver
# has no "the caller's own agent" to resolve `self` against), so such a file
# belongs here rather than being forced to declare a schema version it cannot
# honour. Paths are relative to the repo root.
LEGACY_EXEMPT: dict[str, str] = {}


def _recipe_files() -> list[Path]:
    if not RECIPES_DIR.is_dir():
        return []
    return sorted(p for p in RECIPES_DIR.rglob("*.yaml") if p.is_file())


def _walk(node: Any) -> Iterator[Any]:
    """Yield every mapping nested anywhere inside a parsed YAML document."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _agent_references(doc: Any) -> list[str]:
    """Every string value of an ``agent:`` key, anywhere in the document."""
    refs: list[str] = []
    for mapping in _walk(doc):
        agent = mapping.get("agent")
        if isinstance(agent, str) and agent.strip():
            refs.append(agent.strip())
    return refs


def _declared_agents(doc: Any) -> set[str]:
    """Every agent name promised by the ``dependencies`` block."""
    declared: set[str] = set()
    dependencies = doc.get("dependencies") if isinstance(doc, dict) else None
    if not isinstance(dependencies, list):
        return declared
    for entry in dependencies:
        if not isinstance(entry, dict):
            continue
        required = entry.get("required_agents")
        if isinstance(required, list):
            declared.update(str(name).strip() for name in required if isinstance(name, str))
    return declared


def test_recipes_directory_is_present() -> None:
    """Guard the guard: a typo'd RECIPES_DIR must not make this suite vacuous."""
    assert RECIPES_DIR.is_dir(), f"expected a recipes/ directory at {RECIPES_DIR}"
    assert _recipe_files(), f"no *.yaml recipes discovered under {RECIPES_DIR}"


@pytest.mark.parametrize("recipe_path", _recipe_files(), ids=lambda p: p.name)
def test_recipe_with_agent_reference_declares_schema_v2(recipe_path: Path) -> None:
    relative = recipe_path.relative_to(REPO_ROOT).as_posix()
    if relative in LEGACY_EXEMPT:
        pytest.skip(f"{relative} is exempt: {LEGACY_EXEMPT[relative]}")

    doc = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{relative} did not parse to a YAML mapping"

    refs = _agent_references(doc)
    if not refs:
        pytest.skip(f"{relative} references no agents; schema v2 is not required")

    # 1. The header itself.
    assert doc.get("schema_version") == 2, (
        f"{relative} references agent(s) {sorted(set(refs))} but does not declare "
        "`schema_version: 2`. Without it the recipe is legacy: its agents resolve "
        "from the caller session, so it fails for anyone whose bundle lacks them. "
        "Add `schema_version: 2` and a `dependencies:` block, or list the file in "
        "LEGACY_EXEMPT with a reason."
    )

    # 2. A schema version without a closure resolves nothing.
    dependencies = doc.get("dependencies")
    assert isinstance(dependencies, list) and dependencies, (
        f"{relative} declares `schema_version: 2` but has no non-empty "
        "`dependencies:` list to resolve its agents from."
    )
    for entry in dependencies:
        assert isinstance(entry, dict), f"{relative}: each dependency must be a mapping"
        assert entry.get("source"), f"{relative}: every dependency needs a `source:`"
        assert entry.get("kind") in {"bundle", "behavior"}, (
            f"{relative}: dependency `kind:` must be 'bundle' or 'behavior' "
            f"(got {entry.get('kind')!r})"
        )

    # 3. Every referenced agent must actually be promised by the closure --
    #    including this bundle's own agents, which the engine never infers.
    declared = _declared_agents(doc)
    undeclared = sorted({ref for ref in refs if ref != "self"} - declared)
    assert not undeclared, (
        f"{relative} references {undeclared} but no dependency lists them in "
        "`required_agents:`. The runner never infers a source from a namespace "
        "prefix, so even this bundle's own agents need a self-referential entry."
    )
