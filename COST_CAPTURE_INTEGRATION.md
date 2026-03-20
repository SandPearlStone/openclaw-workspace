# Cost Capture Integration Guide

## Problem

OpenClaw API costs are **server-side** and not directly queryable from local sessions. The 67.8M Haiku tokens from today are only visible on Anthropic's console.

## Solution Architecture

### 3 Levels of Cost Tracking

#### Level 1: Manual Logging (Working Now ✅)
For trading system API calls, manually log costs:

```python
from cost_logger_middleware import log_subagent_run

log_subagent_run(
    task_name="Phase 4 ML Build",
    model="anthropic/claude-haiku-4-5",
    input_tokens=88000,
    output_tokens=33200
)
```

#### Level 2: Anthropic Console Export (Semi-Automatic)
Periodically export usage from Anthropic console and parse:

```bash
# 1. Visit: https://console.anthropic.com/account/billing/usage
# 2. Export as CSV (if available)
# 3. Save as anthropic_usage.csv
# 4. Run:
python3 auto_cost_monitor.py
```

#### Level 3: Webhook Integration (Future)
When Anthropic releases a cost webhook API:

```python
# Webhook endpoint that Anthropic calls with usage data
@app.post("/webhook/anthropic-usage")
async def capture_anthropic_usage(event: dict):
    monitor.log_usage(
        model=event["model"],
        input_tokens=event["input_tokens"],
        output_tokens=event["output_tokens"],
        component="webhook"
    )
```

---

## Current Implementation (Level 1)

### In Your Trading Scripts

Add cost logging to `find_trades.py`, `confluence.py`, etc.:

```python
from cost_logger_middleware import log_subagent_run

def find_trades(symbols):
    # ... your code ...
    
    for symbol in symbols:
        # Log the cost after getting results
        log_subagent_run(
            task_name=f"scan_{symbol}",
            model="anthropic/claude-haiku-4-5",
            input_tokens=500,  # Estimate or extract from response.usage
            output_tokens=200
        )
```

### In Your Subagent Spawns

```python
from sessions_spawn import sessions_spawn
from cost_logger_middleware import log_subagent_run

# Spawn subagent
result = sessions_spawn(
    task="Build Phase 4...",
    runtime="subagent",
    label="phase4-build"
)

# After completion, log the cost
# Extract from subagent completion event
log_subagent_run(
    task_name="phase4_build",
    model="anthropic/claude-haiku-4-5",
    input_tokens=result.get("input_tokens", 0),
    output_tokens=result.get("output_tokens", 0)
)
```

---

## Integration Checklist

- [ ] Add `log_subagent_run()` calls after each major AI operation
- [ ] Export Anthropic console data monthly as backup
- [ ] Set daily cost limit alert in Prometheus ($50/day)
- [ ] Review Grafana dashboard weekly
- [ ] Monitor 7-day rolling average for trends

---

## Tools Available

| Tool | Purpose | Use |
|------|---------|-----|
| **cost_monitor.py** | Core logging engine | Auto-called by middleware |
| **cost_logger_middleware.py** | Decorator/wrapper | Import for easy integration |
| **prometheus_exporter.py** | Real-time metrics | Reads from cost_monitor.db |
| **grafana_dashboard.json** | Visualization | Import into Grafana |
| **auto_cost_monitor.py** | Batch processing | Run hourly via cron |

---

## Limitations (Why We Can't Catch 100%)

1. **Subagent usage is opaque** — OpenClaw spawns subagents server-side; local code can't see their token usage
2. **No local API access** — OpenClaw doesn't expose a "get_session_tokens" API
3. **Anthropic doesn't provide webhook API** (yet) — Can't automatically push usage to us

**Workaround:** Manually log subagent costs after they complete, or export from Anthropic console monthly.

---

## Next Steps

1. **Short-term** — Add `log_subagent_run()` calls to trading system
2. **Medium-term** — Set up monthly Anthropic console export + auto-parsing
3. **Long-term** — Advocate for Anthropic webhook API or OpenClaw session usage API

---

## Example: Complete Flow

```python
# trading_scanner.py
from cost_logger_middleware import log_subagent_run, get_daily_cost, estimate_remaining_budget

def scan_market():
    budget = estimate_remaining_budget(daily_limit=50.0)
    
    if budget["warning"]:
        print("⚠️  Warning: Less than $10 remaining today")
        return  # Stop scanning
    
    # Scan symbols
    for symbol in ["BTCUSDT", "ETHUSDT"]:
        # ... scanning logic ...
        
        # Log cost (estimate or from response.usage)
        log_subagent_run(
            task_name=f"scan_{symbol}",
            model="anthropic/claude-haiku-4-5",
            input_tokens=1500,
            output_tokens=800
        )
    
    # Report
    print(f"Daily cost so far: {get_daily_cost()}")
```

---

## Monitoring in Grafana

Visit http://localhost:3000 and check:
- **Daily Cost** chart — See today's spending
- **Cost by Model** — Haiku vs Sonnet breakdown
- **Daily Tokens** — Token volume trend
- **Today's Total Cost** stat — Big red number if limit exceeded

Set alerts in Grafana if daily cost > $50.
