# Lane ff1n — deployment-guide's missing `tools:` block (NO_TOOLS_SECTION)

Work item: `model_performance-ff1n`
Branch: `lane/ff1n-online-tools-section`, based on `origin/main` @ `e722db3`
Spend: **$0** — config edit, validator runs, local test runs. No API measurement.
Landing stage: **DRAFT PR.** This lane may not merge; the merge is the manager's next stage.

---

## What changed

One file, one addition: a top-level `tools:` block in `agents/deployment-guide.md`'s
frontmatter, declaring three modules.

```yaml
tools:
  - module: tool-bash
    source: git+https://github.com/microsoft/amplifier-module-tool-bash@main
  - module: tool-filesystem
    source: git+https://github.com/microsoft/amplifier-module-tool-filesystem@main
  - module: tool-search
    source: git+https://github.com/microsoft/amplifier-module-tool-search@main
```

`meta:` is byte-identical to stock, the body is byte-identical to stock, and no other
file in the bundle changed. Verified by parsing both revisions and comparing:

```
description IDENTICAL: True | chars: 598
meta IDENTICAL: True
body IDENTICAL: True
```

Everything else added by this lane lives under `docs/lanes/ff1n-online-tools-section/`,
which `validate-agents` excludes from discovery, so the artifacts cannot flatter the
verdict.

---

## Decision 1 — the block goes in agent frontmatter, not `behaviors/amplifier-online.yaml`

The item explicitly left this open. Frontmatter, for three reasons, in order of weight:

1. **The requirement is agent-scoped.** It is *this agent's body* that hard-codes these
   tools as workflow steps — principle 8's `init` → `read_file` → `edit_file` manifest
   sequence, principle 6's `bash` diagnosis, principle 3 and Scenario F's `glob`/`grep`
   scan. Agent frontmatter is the only place that says "this agent needs these". A
   top-level `tools:` in the behavior grants tools to the whole consuming **session**,
   which is broader than the need and records the dependency where no reader of the
   agent will see it.
2. **It travels through every include form.** `bundle.md`, the behavior partial, and
   `recipes/deploy-project.yaml`'s self-referential dependency all reach the agent file.
   Only one of them reaches `behaviors/amplifier-online.yaml`.
3. **It is the only home the validator recognises.** `validate-agents` v1.8.0 clears
   `NO_TOOLS_SECTION` from frontmatter or from `bundles/*.yaml` — the latter is a
   directory this repo does not have and should not grow for this
   (`recipes/validate-agents.yaml:647-685, 778-803` in the cached foundation copy).
   A behavior-level block would have left the warning standing.

## Decision 2 — module names and sources, verified against the CURRENT foundation layout

All three are **standalone repos whose module lives at the repo root**, so **no
`#subdirectory` fragment applies to any of them.** That was the item's named failure
risk (a wrong `source:` makes the agent fail to resolve, strictly worse than the
implicit state), so it was checked three ways rather than copied:

| module | source | cross-check in current amplifier-foundation |
|---|---|---|
| `tool-bash` | `git+https://github.com/microsoft/amplifier-module-tool-bash@main` | `agents/shell-exec.md`, `bundles/anchors/bundle.md` |
| `tool-filesystem` | `git+https://github.com/microsoft/amplifier-module-tool-filesystem@main` | `agents/file-ops.md`, `agents/explorer.md`, `bundles/anchors/bundle.md` |
| `tool-search` | `git+https://github.com/microsoft/amplifier-module-tool-search@main` | `agents/file-ops.md`, `agents/explorer.md`, `bundles/anchors/bundle.md` |

Each module's cache metadata confirms the URL actually resolves and the ref is live
(`~/.amplifier/cache/amplifier-module-tool-*/.amplifier_cache_meta.json`: `tool-bash`
`73038ab`, `tool-filesystem` `8bd1eab`, `tool-search` `0c7f4a7`, all `ref: main`, all
fetched within two days of this lane).

Nothing else was added. `todo`, `delegate`, `web_*`, `apply_patch` and the rest appear
nowhere in the agent's documented workflow, and under the full bundle the agent still
inherits them anyway (see the correction below).

---

## CORRECTION to the item's premise: an explicit `tools:` block does NOT replace inheritance

The item cautioned that "an explicit `tools:` block REPLACES inheritance, so the agent
then gets ONLY what is listed." **Measured: false, for agent frontmatter.**

Agent-level `tools:` is **merged with** the inherited roster by module id:

- `amplifier_app_cli/lib/merge_utils.py:163-194` — `merge_agent_dicts` routes
  `"hooks"/"tools"/"providers"` to `merge_module_lists`, not to override.
- `amplifier_app_cli/lib/merge_utils.py:80-128` — `merge_module_lists` keeps the parent
  entry, deep-merges on a module-id collision, appends a new module.

Wholesale replacement is a **parent bundle's `spawn.tools:`** policy — a different key,
untouched by this change (`amplifier_app_cli/agent_config.py:41-51`; the same docstring
states the default plainly: "agents inherit all parent tools").

Measured on this repo, not inferred — `verify_agent_tools.py` step 4:

```
regression guard: bundle.md (includes amplifier-foundation)
  inherited modules before: 13  after: 13
  lost: none   duplicated: none
PASS: full-bundle roster unchanged -- the declaration is purely additive
```

Note that `validate-agents`' own synthesised report repeats the same "replaces
inheritance" claim in its prose. That claim is wrong on this code path; the numbers
above are the evidence. It does not change the verdict either way.

---

## Evidence

Two committed harnesses, both **$0** — no LLM call, no provider mounted.

### 1. `verify_agent_tools.py` — the real failure mode, fail-before / pass-after

Walks the real code path a consumer walks: compose the behavior **alone** →
`merge_configs` (the actual spawn-time merge) → mount into a **real** `AmplifierSession`
and read back `coordinator.get("tools")`. Those are loaded tool objects, not names
copied out of YAML.

**Before** (`origin/main` @ `e722db3`, and identically at the lane's original base
`39823ad`):

```
behavior-only mount plan, top-level tools: []
agent overlay keys: ['description', 'instruction', 'model_role', 'name']
agent-declared tools: null
post-merge tool modules: []
ACTUALLY MOUNTED TOOLS: []
FAIL: 6 required tool(s) not mounted: ['bash', 'edit_file', 'glob', 'grep', 'read_file', 'write_file']
```

**After** (this branch):

```
agent overlay keys: ['description', 'instruction', 'model_role', 'name', 'tools']
post-merge tool modules: ['tool-bash', 'tool-filesystem', 'tool-search']
ACTUALLY MOUNTED TOOLS: ['bash', 'edit_file', 'glob', 'grep', 'read_file', 'write_file']
PASS: all 6 required tools mounted (bash, edit_file, glob, grep, read_file, write_file)

regression guard: bundle.md (includes amplifier-foundation)
  inherited modules before: 13  after: 13
  lost: none   duplicated: none
PASS: full-bundle roster unchanged -- the declaration is purely additive
```

That is the deliverable "the agent still resolves and its documented workflow still
works", demonstrated rather than asserted: the agent resolves from the behavior, and
every tool the workflow names is present on the coordinator — `glob`/`grep` for the
Scenario F repo-readiness scan, `read_file`/`edit_file`/`write_file` for the
`amplifier-online init` manifest workflow, `bash` for `status`/`logs`.

### 2. `run_validate_agents_deterministic.py` — validate-agents' own bash phases

Reads the four `type: bash` steps verbatim out of `validate-agents.yaml` v1.8.0 and runs
them in order with the engine's `{{var}}` substitution. Not a reimplementation; if the
recipe changes, this follows. It exists so the before/after pair over two git revisions
costs nothing and reproduces exactly.

| | stock (`/tmp` worktree of `origin/main` @ `e722db3`) | this branch |
|---|---|---|
| agents discovered | 1 (`agents/`: 1), candidates 1, non-agents 0 | 1 (`agents/`: 1), candidates 1, non-agents 0 |
| structural summary | `errors: 0, warnings: 1` | `errors: 0, warnings: 0` |
| `quality_level` | `needs_work` | `good` |
| `has_explicit_tools` / `tools_source` | `False` / `implicit` | `True` / `frontmatter` |
| `NO_TOOLS_SECTION` | **PRESENT** | **CLEARED** |

### 3. Full `validate-agents` v1.8.0 run (the quotable verdict)

`recipes(operation="execute", recipe_path="@foundation:recipes/validate-agents.yaml",
context={"repo_path": <this repo>})`, run `run-b6ef57b1156a`:

> **Overall Verdict**: ✅ **PASS**
> **Agents Found**: 1 total across 1 location
> **Quality Breakdown**: 1 good, 0 polish, 0 needs_work, 0 critical
> **Issues**: 0 errors, 0 warnings, 0 suggestions

with `structural_results.agents[0]`: `has_explicit_tools: true`,
`tools_source: "frontmatter"`, `errors: []`, `warnings: []`.

The `quality-classification` step set `requires_llm_analysis: false`, so the run took the
quick-approval path — the two diagnostic LLM phases were skipped.

### 4. Repo test suite — green

```
tests/test_recipe_schema_version.py::test_recipes_directory_is_present PASSED
tests/test_recipe_schema_version.py::test_recipe_with_agent_reference_declares_schema_v2[deploy-project.yaml] PASSED
============================== 2 passed in 0.03s ===============================
```

---

## Reproduce

```bash
PY=~/.local/share/uv/tools/amplifier/bin/python

# fail-before, against stock
git worktree add -f /tmp/ff1n-stock origin/main
$PY docs/lanes/ff1n-online-tools-section/run_validate_agents_deterministic.py /tmp/ff1n-stock   # exit 1

# pass-after, on this branch
$PY docs/lanes/ff1n-online-tools-section/run_validate_agents_deterministic.py .                 # exit 0
$PY docs/lanes/ff1n-online-tools-section/verify_agent_tools.py                                  # exit 0

uvx --with pyyaml --from pytest pytest tests/ -v
```

---

## Two things noticed, deliberately NOT fixed here

Both are out of this item's scope. Recorded so they are not lost, not folded in — the
change under review is a 45-line frontmatter addition with zero body churn, which is
what a reviewer should see.

1. **The behavior partial cannot resolve `@foundation:` mentions on its own.** The agent
   body's last line is `@foundation:context/shared/common-agent-base.md`. `bundle.md`
   includes amplifier-foundation, so it resolves there; the behavior alone includes no
   foundation bundle, so a behavior-only consumer has the same structural gap for
   *context* that this lane just closed for *tools*. Same failure shape, different
   mechanism — it deserves its own item and its own measurement, not a drive-by include
   bolted on here.

2. **The lane's original base was stale.** The item was written against `39823ad`; while
   this lane was in flight, `origin/main` advanced to `e722db3` — lane dae2's PR #43,
   which rewrote the same file's `description` from 4,004 to 598 chars. This branch was
   reset onto `e722db3` before the edit rather than rebased through a frontmatter
   conflict, so the two changes compose cleanly and `meta:` is byte-identical to the
   merged version. Worth knowing that on the *old* base, validate-agents v1.8.0 also
   reported three description ERRORs (`DESCRIPTION_EXCESSIVE`, `COMMENTARY_TAG_PRESENT`,
   `EXAMPLE_BLOCK_PRESENT`) — the item's "structural errors are 0" premise only became
   true once #43 landed.
