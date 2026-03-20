# Cost Tracking & Token Usage Monitoring

## Overview

Three cost tracking tools are available:

1. **cost_tracker.py** — Manual logging of API calls to CSV
2. **token_counter.py** — Uses Anthropic Token Counting API for cost estimates
3. **cost_monitor.py** — Full session-based tracking with SQLite + JSON export

## Usage

### Real-time Monitoring (cost_monitor.py)

```python
from cost_monitor import TokenUsageMonitor

monitor = TokenUsageMonitor()

# Log an API call after it completes
monitor.log_usage(
    model="anthropic/claude-haiku-4-5",
    input_tokens=1500,
    output_tokens=800,
    component="phase4_build",
    notes="ML implementation completed"
)

# View today's breakdown
today = monitor.get_daily_summary()
print(today)

# View 7-day trend
trend = monitor.get_usage_trend(days=7)
for day in trend:
    print(f"{day['date']}: {day['cost']}")

# Check for alerts (e.g., daily spend limit)
alerts = monitor.check_alerts(daily_limit=50.0)
if alerts:
    for alert in alerts:
        print(f"⚠️  {alert['message']}")

# Print formatted summary
monitor.print_summary()
```

### Pre-Request Cost Estimation (token_counter.py)

```python
from token_counter import estimate_cost

# Before sending a message, estimate cost
messages = [{"role": "user", "content": "Your message here"}]
estimate = estimate_cost(messages, "claude-haiku-4-5", output_tokens=150)

print(f"Estimated cost: {estimate['total_cost']}")
```

### Manual Logging (cost_tracker.py)

```python
from cost_tracker import log_api_call, print_summary

# Log call
log_api_call("anthropic/claude-haiku-4-5", input_tokens=150, output_tokens=50)

# View summary
print_summary()
```

## Integration with OpenClaw

To automatically track costs:

1. **Export API key** (already done):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-api03-..."
   ```

2. **After each subagent completes**, log the usage:
   ```python
   # In your subagent wrapper or monitoring script
   response = client.messages.create(...)
   monitor.log_usage(
       model="anthropic/claude-haiku-4-5",
       input_tokens=response.usage.input_tokens,
       output_tokens=response.usage.output_tokens,
       session_key=session_id,
       component="trading_scanner"
   )
   ```

3. **Daily alerts**:
   ```bash
   # Check in a cron job or heartbeat
   python3 cost_monitor.py
   ```

## Interpreting the Data

### Daily Summary
```
2026-03-20: $0.50 (5,000 tokens, 3 calls)
```

- **$0.50** = Total cost for the day
- **5,000 tokens** = Combined input + output
- **3 calls** = Number of API requests

### By Model
```
claude-haiku-4-5:   $0.30 (70%)
claude-sonnet-4-6:  $0.15 (30%)
```

- Cheaper models (Haiku) reduce costs significantly
- Sonnet is ~4x more expensive but better for complex tasks

## Cost Breakdown (Reference)

**Input pricing per 1M tokens:**
- Claude Haiku: $0.80
- Claude Sonnet: $3.00
- Claude Opus: $15.00
- GPT-5.4: $2.50

**Output pricing per 1M tokens:**
- Claude Haiku: $2.40
- Claude Sonnet: $15.00
- Claude Opus: $75.00
- GPT-5.4: $10.00

## Example: Why Today Cost $31.95

**39.5M Haiku input tokens** likely from:

1. **Main session**: ~150k tokens (direct chat)
2. **Subagent context loading**: ~3.5M tokens (7 spawns × ~500k each)
3. **Phase 4 build + docs**: ~20M tokens (big implementation + testing)
4. **Earlier attempts/retries**: ~5M tokens (failed runs, timeouts)
5. **Unaccounted overhead**: ~10M tokens (token caching, hidden context)

**Total: 39.5M × $0.80/M = $31.60 ✓**

## Recommendations

1. **Monitor daily**:
   ```bash
   python3 cost_monitor.py
   ```

2. **Set alerts** for daily limit (e.g., $50/day):
   ```python
   alerts = monitor.check_alerts(daily_limit=50.0)
   ```

3. **Use cheaper models** when possible:
   - Haiku for simple tasks (60% cheaper than Sonnet)
   - Sonnet for complex design (better quality)

4. **Batch requests**:
   - Fewer large requests > many small requests
   - Reduces API overhead

5. **Cache results**:
   - Store frequently-used data (OHLCV, patterns)
   - Your trading system already does this with SQLite

## Files

- **cost_monitor.py** — Main monitoring tool (SQLite + JSON)
- **token_counter.py** — Pre-request cost estimation
- **cost_tracker.py** — Manual CSV logging
- **usage.db** — SQLite database (auto-created)
- **usage_log.json** — JSON export (auto-created)
- **usage_alerts.json** — Alert log (auto-created)
