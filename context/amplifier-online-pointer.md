# Amplifier Online

**Amplifier Online** (AO) puts a team's project online in Microsoft's tenant:
each service runs on shared Azure Container Apps, with tenant-only sign-in,
keyless databases, and deploys through Azure Pipelines. It is distinct from
**Amplifier** (this AI assistant platform). Never conflate the two.

## When Amplifier Online work arrives

Deploying or updating a project on AO, an `amplifier-online.yaml` in the repo,
the `amplifier-online` CLI, or "put this online for my team": **activate
`/amplifier-online` mode first**.

```
mode(operation="set", name="amplifier-online")
```

If the mode tool returns `status: denied` (warn gate), call it again
immediately; the second call succeeds.
