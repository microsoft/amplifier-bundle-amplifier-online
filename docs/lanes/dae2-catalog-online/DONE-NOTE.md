# DONE-NOTE — lane `dae2-catalog-online`

Delegate-catalog SOURCES sweep (kp79 standard) applied to this repo's one delegate-catalog
agent, `deployment-guide`.

**Landing stage: DRAFT PR.** This lane may not merge. Fail-before / pass-after is demonstrated
below; the change ships as a draft PR and the merge is the manager's next stage.

Work item: `model_performance-ven6` (per-repo child of `model_performance-dae2`, linked
`relates-to`). The parent covers six repos with one lane each; it was claimed, a per-repo child
filed, and the parent **released unresolved** so the five sibling repos' lanes are not blocked —
the `model_performance-k75p` recovery pattern, applied pre-emptively rather than after a refusal.

## What changed

One file, one YAML value: `agents/deployment-guide.md`, frontmatter `meta.description`.
Nothing else in the repo was touched.

## Numbers (measured against CURRENT `origin/main` @ `39823ad`, not a cached baseline)

| agent | stock desc | lean desc | delta | pct |
|---|---:|---:|---:|---:|
| `deployment-guide` | 4,004 chars | 598 chars | −3,406 | −85.1% |
| **repo total (1 agent)** | **4,004** | **598** | **−3,406** | **−85.1%** |

The parent item's carried estimate was ~4,007 chars. Verified figure is **4,004** — the baseline
had drifted by 3 chars, which is why it was re-measured rather than quoted.

`<example>` blocks 6 → 0. `<commentary>` blocks 6 → 0.

## Bodies byte-identical

Everything after the closing frontmatter `---`:

```
stock body md5 = 46db7bf0db8a34e8ad13426c4fe334ce  (9,848 chars)
lean  body md5 = 46db7bf0db8a34e8ad13426c4fe334ce  (9,848 chars)
identical      = True
```

Non-description frontmatter is unchanged too: `meta.name` = `deployment-guide`,
`meta.model_role` = `[reasoning, general]`, both sides.

## Fidelity

`evidence/fidelity-table.md` walks all 18 facts in the stock description.
**No routing fact was lost; zero restorations were required; restoration byte delta 0.**

The one real risk in this file was that the single negative-routing fact — a guided,
approval-gated end-to-end deployment belongs to the `deploy-project` recipe, not a direct
delegate call — existed **only inside `<example>` block 6**, which the standard requires
deleting. It is promoted into an explicit `DO NOT USE WHEN` clause rather than deleted with the
block. `validate-agents`' own LLM phase, run against the stock checkout before this branch was
written, independently flagged that same block as the lossy one.

## validate-agents (recipe v1.8.0, foundation @v2.1.2 `a27d5824`)

| | stock (`origin/main` @ `39823ad`) | branch (`lane/dae2-catalog-online` @ `0911d6c`) |
|---|---|---|
| verdict | **FAIL** (`critical`) | **PASS WITH WARNINGS** |
| agents discovered | 1 across 1 location | 1 across 1 location |
| structural | `{"errors": 3, "passed": 0, "total": 1, "warnings": 1}` | `{"errors": 0, "passed": 1, "total": 1, "warnings": 1}` |
| desc chars / tokens | 4,004 / 1,001 | 598 / 149 |

**Transition FAIL → PASS WITH WARNINGS** — not "PASS held". Stock carried three structural
ERRORs (`DESCRIPTION_EXCESSIVE`, `COMMENTARY_TAG_PRESENT`, `EXAMPLE_BLOCK_PRESENT`); the branch
carries none. Raw runs: `evidence/validate-agents-STOCK-main.txt`,
`evidence/validate-agents-BRANCH.txt`.

**Discovered agent count for this repo: 1** (`agents/deployment-guide.md`;
`candidates_scanned` 1, `non_agent_count` 0).

## The one surviving warning — accepted, not remediated

`NO_TOOLS_SECTION` on `deployment-guide` (implicit tool inheritance) is present in stock,
present on the branch, **identical on both sides**. It is the sole driver of the `needs_work`
classification; the report's description-quality phase returned "Issues (description quality):
None" and "No description change recommended."

It is out of contract for this lane, which touches the frontmatter `description` value only and
holds bodies byte-identical. Both LLM phases of the branch run reached the same conclusion
unprompted ("do NOT land this on the current branch … file it as a follow-up"). Recorded here as
a real, open finding for the repo owner — **NOT-POSSIBLE-in-this-lane**, with reason.

## CI and tests

- Repo CI exists: `.github/workflows/tests.yml`, `pytest tests/ -v` on Python 3.12, triggered on
  `pull_request`. It will run on the draft PR.
- Local run on the branch: `python3 -m pytest tests/ -q` → **2 passed**.

## Census safety

`grep -l /tmp/ ~/.local/share/uv/tools/amplifier/lib/python3.13/site-packages/*.pth` returns
nothing — checked after all measurement. No `amplifier` binary was run on the host with a scratch
`AMPLIFIER_HOME`; every measurement here is a static read of file bytes plus two in-session
recipe runs.

## Spend

$0 authorised, $0 of API measurement performed. Work was text edits, byte counts, a local pytest
run, and two `validate-agents` recipe runs (explicitly within authority).
