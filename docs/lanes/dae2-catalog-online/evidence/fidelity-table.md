# Fidelity table — `deployment-guide`, stock vs lean

Stock = `origin/main` @ `39823ad`, `agents/deployment-guide.md`, frontmatter `meta.description`
(4,004 chars). Lean = `lane/dae2-catalog-online` @ `0911d6c` (598 chars).

The question this table answers is the only one that matters: **is there any USE WHEN /
DO NOT USE WHEN fact, trigger condition, or constraint present in stock and absent in lean?**

| # | Fact in stock | Where in stock | Status in lean |
|---|---|---|---|
| 1 | Domain is Amplifier Online, the **Azure Container Apps** deployment system | opening ¶; Authoritative-on | **KEPT** — `(Azure Container Apps/Web Apps/Static Web Apps deployment)`, all three Azure surfaces named |
| 2 | Carries stacks / manifests / CLI / troubleshooting / readiness / CI-CD knowledge | opening ¶ | **KEPT as the trigger enumeration** — the same six areas appear as concrete WHEN conditions (#4–#11) instead of as a capability blurb |
| 3 | "What is Amplifier Online?" + architecture (Platform / Provisioner Service / CLI) | USE WHEN b1; ex. 1 | **KEPT** — `what it is; Platform/Provisioner Service/CLI architecture` |
| 4 | Which deployment stack to choose | USE WHEN b2; MUST b2; ex. 2 | **KEPT** — `stack choice`, plus all four stack names verbatim |
| 5 | Stack names `web-app-aca`, `internal-service-aca`, `web-app-awa`, `static-web-app` | Authoritative-on | **KEPT verbatim** |
| 6 | Repo readiness check — Dockerfiles, ACR image format | USE WHEN b3; MUST b2; ex. 3 | **KEPT** — `repo readiness/project analysis (Dockerfiles, ACR refs)` |
| 7 | Creating / editing / validating `amplifier-online.yaml` project manifest | USE WHEN b4; MUST b3 | **KEPT** — `authoring/validating amplifier-online.yaml` |
| 8 | First deployment end-to-end: `config → build → push → init → up` | USE WHEN b5 | **KEPT** — `first deploy (config->build->push->init->up)` |
| 9 | Diagnosing errors from `up`, `status`, `logs` | USE WHEN b6; MUST b4; ex. 4 | **KEPT** — `` `up`/`status`/`logs` failures `` |
| 10 | GitHub Actions CI/CD via `amplifier-online cicd create` | USE WHEN b7; ex. 5 | **KEPT** — `GitHub Actions CI/CD (`cicd create`)` |
| 11 | Destroying a deployment or switching stacks | USE WHEN b8 | **KEPT** — `destroy/stack switch` |
| 12 | External Key Vault-backed secrets — `secrets:` block / `amplifier-online secret` | Authoritative-on | **KEPT** — `Key Vault `secret`s` (both the Key Vault concept and the `secret` command name) |
| 13 | Keyword `ACR` | Authoritative-on | **KEPT** |
| 14 | Keyword `project analysis` | Authoritative-on | **KEPT** — `repo readiness/project analysis` |
| 15 | Commands `amplifier-online up` / `init` / `config` / `cicd` | Authoritative-on | **KEPT** — `up` (#9), `init` and `config` inside the deploy sequence (#8), `cicd create` (#10) |
| 16 | "MUST be used for" block: deploying via Amplifier Online, stack selection/readiness, manifest authoring/validation, deployment troubleshooting | lines 27–31 | **DROPPED AS DUPLICATION** — all four are restatements of #4, #6, #7 and #9, which are kept. No fact lost. |
| 17 | Guided / "walk me through" deployment belongs to the **`deploy-project` recipe**, not a direct delegate call | **example block 6 only** | **PROMOTED** — now an explicit `DO NOT USE WHEN asked for a guided, approval-gated walkthrough: use the deploy-project recipe.` |
| 18 | Example blocks 1–5 | ex. 1–5 | **DELETED** — each restates a trigger already carried by #3, #4, #6, #9, #10. No fact lost. |

## Verdict

**No routing fact was lost. Zero restorations were required; byte delta from restorations: 0.**

Two items are worth naming explicitly because they are the only places where the lean text is
not a verbatim carry-over:

- **#17 is a gain, not a carry-over.** The single negative-routing fact in the whole stock
  description lived *only inside example block 6* — a block the standard requires deleting.
  Deleting the blocks without promoting it would have silently dropped it. It is now first-class
  structured text, which is the strongest form of a DO NOT clause: it names the competing surface
  *and* routes to it.
- **#16 and #18 are duplication, not facts.** Stock stated one decision rule four ways (opening
  paragraph, USE WHEN bullets, Authoritative-on keyword list, MUST-be-used-for block) and then
  illustrated it six more times. That duplication — not the trigger list — is what produced
  4,004 chars. The trigger list itself was already good and was kept essentially intact.

Two stock phrasings are carried semantically rather than verbatim, and neither is a routing fact:

- "container deployment" (Authoritative-on keyword) — carried by "Azure Container Apps … deployment".
- "ACR image format" → "ACR refs" — same readiness check, shorter wording; the discriminating
  keyword `ACR` is preserved.

## Independent corroboration

`validate-agents` v1.8.0 was run against the stock checkout *before* this branch was written
(`run-b2597d76aa5d`). Its LLM description-quality phase independently identified example block 6
as the one fidelity risk in the file — "the ONLY place in the file carrying the negative-routing
fact that a guided, gated end-to-end deployment belongs to the `deploy-project` recipe … Deleting
the blocks without promoting that fact loses it silently" — and independently proposed a 598-char
rewrite. That is an agreement reached from the stock file alone, not a review of this branch.
