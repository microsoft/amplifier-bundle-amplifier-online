"""The bundle's references resolve, and it hands over to the v2 skill.

v2 of this bundle is an on-ramp: it keeps the amplifier-online CLI and its
`amplifier-online-deploy` skill current and offers to upgrade v1 projects. The
v1 agent, recipe and knowledge base were removed; nothing may still point at
them.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---\n", 2)[1])


def _local(ref: str) -> Path:
    """`amplifier-online:<path>` -> a file in this repo (.md or .yaml added if missing)."""
    rel = ref.split(":", 1)[1]
    for candidate in (rel, f"{rel}.md", f"{rel}.yaml"):
        if (ROOT / candidate).is_file():
            return ROOT / candidate
    raise AssertionError(f"{ref} does not resolve to a file in this repo")


def test_behavior_references_resolve():
    behavior = yaml.safe_load((ROOT / "behaviors" / "amplifier-online.yaml").read_text())
    refs = behavior.get("modes", {}).get("include", []) + behavior.get("context", {}).get("include", [])
    assert refs
    for ref in refs:
        _local(ref)
    assert "agents" not in behavior  # the v1 deployment-guide agent is gone


def test_mode_context_resolves_and_loads_the_skill():
    mode = _frontmatter(ROOT / "modes" / "amplifier-online.md")["mode"]
    assert "load_skill" in mode["tools"]["safe"]
    for ref in mode["contributes"]["context"]:
        text = _local(ref).read_text()
        assert 'load_skill(skill_name="amplifier-online-deploy")' in text
        assert "amplifier-online install-skill" in text


def test_nothing_points_at_removed_v1_files():
    removed = ("deployment-guide", "deploy-project", "context/agent/", "stacks-reference")
    for path in ROOT.rglob("*"):
        if path.suffix not in (".md", ".yaml", ".yml") or ".git" in path.parts or "docs" in path.parts:
            continue
        text = path.read_text()
        for name in removed:
            assert not re.search(re.escape(name), text), f"{path.relative_to(ROOT)} mentions {name}"


def test_it_offers_to_remove_itself_by_its_registered_names():
    """`bundle add` registers this bundle under its own bundle.name; `remove
    --app` matches app URIs by substring. No install URI is guessed."""
    mode = _frontmatter(ROOT / "modes" / "amplifier-online.md")["mode"]
    text = "".join(_local(ref).read_text() for ref in mode["contributes"]["context"])
    behavior = yaml.safe_load((ROOT / "behaviors" / "amplifier-online.yaml").read_text())["bundle"]["name"]
    root = _frontmatter(ROOT / "bundle.md")["bundle"]["name"]
    for name in (behavior, root):
        assert f"amplifier bundle remove {name}\n" in text
    assert "amplifier bundle remove amplifier-bundle-amplifier-online --app" in text
    assert "once per session" in text.lower() and "Only on a yes" in text


def test_setup_reinstalls_a_cli_pinned_to_v1_from_main():
    """`update` keeps a pinned install on its branch; a v1 CLI has no install-skill."""
    mode = _frontmatter(ROOT / "modes" / "amplifier-online.md")["mode"]
    text = "".join(_local(ref).read_text() for ref in mode["contributes"]["context"])
    assert 'grep -q install-skill || uv tool install --force "git+https://github.com/microsoft/amplifier-online#subdirectory=cli"' in text
    assert "never `@v1` or `@v2`" in text
