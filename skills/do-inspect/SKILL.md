---
description: "Inspect DigitalOcean infrastructure — app metrics (CPU/memory), logs, deployments, database config, and connection pools. Use when troubleshooting performance, checking deployment status, or investigating incidents."
argument-hint: "[staging|prod] [cpu|memory|logs|deployments|db|status]"
allowed-tools: ["Bash", "Read", "Agent"]
---

# DigitalOcean Infrastructure Inspector

## Prerequisites

All commands require `doctl` via nix: `nix-shell -p doctl --run "..."`.
Auth config lives at `~/.config/doctl/config.yaml`. If not authenticated:
```
! nix-shell -p doctl --run "doctl auth init"
```
Token scopes needed: **Apps (read)**, **Monitoring (read)**, **Database (read)**.

## Phase 1: Discover Resources

Always discover resource IDs first — never hardcode them.

```bash
# Apps
nix-shell -p doctl --run "doctl apps list"

# Databases
nix-shell -p doctl --run "doctl databases list"

# Connection pools (pass DB cluster ID)
nix-shell -p doctl --run "doctl databases pool list {DB_ID}"
```

Match the user's target (`$ARGUMENTS`) against names:
- `staging` / `stag` -> name containing `stag`
- `prod` / `production` -> name containing `prod`
- If no target specified, inspect all

## Phase 2: Inspect

Use `doctl --help` and subcommand help to discover available commands. Key capabilities below.

### App Metrics (API only — not available via doctl)

These are the **only** app metrics available via API. Database metrics and HTTP response times are only visible in the DO dashboard.

```bash
TOKEN=$(grep 'access-token' ~/.config/doctl/config.yaml | head -1 | awk '{print $2}')
```

| Metric | Endpoint |
|--------|----------|
| CPU % | `GET /v2/monitoring/metrics/apps/cpu_percentage?app_id={ID}&start={TS}&end={TS}` |
| Memory % | `GET /v2/monitoring/metrics/apps/memory_percentage?app_id={ID}&start={TS}&end={TS}` |
| Restart count | `GET /v2/monitoring/metrics/apps/restart_count?app_id={ID}&start={TS}&end={TS}` |

All return Prometheus-style per-instance time series:
```json
{
  "data": {
    "result": [{
      "metric": { "app_component_instance": "opencouncil-0" },
      "values": [[unix_ts, "value_string"], ...]
    }]
  }
}
```

Default time range: last 2 hours. For incidents, extend to 24h.
Metric series reset when instances restart — new instance = new series with gaps.

### App Logs, Deployments, Config, Alerts

Use `doctl apps --help` for the full command reference. Key commands:
- `doctl apps logs {APP_ID} --type run` (also: `build`, `deploy`, `run_restarted`)
- `doctl apps logs {APP_ID} --type build --deployment {DEPLOY_ID}`
- `doctl apps list-deployments {APP_ID}`
- `doctl apps get {APP_ID}` (full app spec as JSON with `-o json`)
- `doctl apps list-alerts {APP_ID}`

Limitation: cannot get runtime logs from superseded (old) deployments.

### Database Inspection

Use `doctl databases --help` for the full command reference. Key commands:
- `doctl databases get {DB_ID}` — cluster info, engine, version, region, status
- `doctl databases pool list {DB_ID}` — connection pools with sizes and modes
- `doctl databases db list {DB_ID}` — databases within the cluster
- `doctl databases connection {DB_ID}` — connection details
- `doctl databases backups {DB_ID}` — backup history
- `doctl databases configuration get {DB_ID}` — runtime config (max_connections, etc.)
- `doctl databases events list {DB_ID}` — cluster events

Note: database **performance metrics** (query latency, active connections, cache hit ratio, IOPS) are **NOT available via API or doctl** — they are only visible in the DO dashboard Insights tab.

## Interpretation Guide

### CPU patterns
- **Sustained >90%** = stuck process or infinite loop, not normal load
- **Spike then recovery** = request burst, cache warming, or deployment
- **One instance high, others normal** = instance-specific issue (ISR assignment, stuck request, cache stampede hitting one instance)

### Memory patterns
- **Flat + high CPU** = tight loop without allocations (not a leak)
- **Steadily climbing** = memory leak
- **Flat at baseline** = normal

### Correlating with deployments
1. Get deployment timestamps from `doctl apps list-deployments`
2. Query CPU/memory metrics spanning the deployment window
3. Look for: pre-deploy baseline -> deploy gap (restart) -> post-deploy behavior

## Formatting Helper

Use this to render time series data readably:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "${BASE_URL}/monitoring/metrics/apps/{METRIC}?app_id=${APP_ID}&start=${START}&end=${END}" | \
  python3 -c "
import json, sys, datetime
data = json.load(sys.stdin)
for series in data['data']['result']:
    instance = series['metric'].get('app_component_instance', 'unknown')
    values = series['values']
    print(f'\n=== {instance} ({len(values)} data points) ===')
    for ts, val in values:
        dt = datetime.datetime.utcfromtimestamp(ts)
        v = float(val)
        if v > 10:
            print(f'  {dt.strftime(\"%Y-%m-%d %H:%M\")} UTC  {v:.1f}%')
"
```
