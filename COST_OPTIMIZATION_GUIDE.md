# Cost Optimization Guide

## Quick Summary

**3 ways to reduce subagent costs by 80-97%:**

1. **Selective attachments** — Attach only needed files (vs loading entire workspace)
2. **Focused task specs** — Narrow, specific instructions (vs vague, open-ended)
3. **Smart retries** — Avoid timeouts through better specifications

---

## The Problem

### Current Approach (Expensive)
```python
sessions_spawn(
    task="Implement Phase 4...",
    runtime="subagent"
)
# OpenClaw automatically loads:
# - Entire workspace directory (200+ files)
# - All memory files
# - Session history
# - Trading/ code directory
# - RESULT: 500k+ tokens = $0.40/spawn ❌
```

### Cost Today
- Phase 4 built 3 times (timeouts, retries)
- 3 × 500k tokens = 1.5M tokens
- 3 × $0.40 = **$1.20 wasted on context alone**

---

## The Solution

### Use Cost-Optimized Spawner
```python
from cost_optimized_spawner import CostOptimizedSpawner

spawner = CostOptimizedSpawner(base_dir=Path("trading"))

result = spawner.spawn_focused_task(
    name="Phase 4 ML Integration",
    files=["confluence.py", "ml_scorer.py", "patterns.py"],
    instructions="""
Build ml_scorer.py:
1. load_model() - Load phase4_model.pkl
2. score_with_ml(features) - Returns confidence [0,1]
3. extract_features_from_setup() - Extract 14 features
""",
    deliverables=[
        "ml_scorer.py (tested)",
        "confluence.py with score_setup_with_ml()",
        "find_trades.py --with-ml flag"
    ],
    constraints=[
        "Use provided RandomForest model",
        "Maintain backward compatibility",
        "No breaking changes"
    ]
)

spawner.print_summary()
```

### Cost Breakdown
```
Context estimate: 12,991 tokens ≈ $0.0106
Optimization vs Full Workspace:
  Unoptimized: $0.40
  Optimized:   $0.01
  Savings:     $0.39 (97.4%)
```

---

## How It Works

### 1. Selective Attachments
Instead of loading everything:
```python
# ❌ BEFORE: Auto-loads entire workspace
sessions_spawn(task="...", runtime="subagent")
```

Do this:
```python
# ✅ AFTER: Attach only what's needed
attachments = [
    {"name": "confluence.py", "content": "..."},
    {"name": "ml_scorer.py", "content": "..."},
    {"name": "patterns.py", "content": "..."}
]
sessions_spawn(
    task="...",
    runtime="subagent",
    attachments=attachments
)
# 12k tokens instead of 500k ✓
```

### 2. Focused Task Specification
Instead of vague instructions:
```python
# ❌ BEFORE: Vague (subagent needs context to understand)
task="Implement Phase 4 ML Integration for live trading scanner"
# Subagent loads everything to figure out context
```

Do this:
```python
# ✅ AFTER: Specific deliverables
task="""
Build ml_scorer.py with:
1. load_model() - Load phase4_model.pkl at startup
2. score_with_ml(features) - Return confidence [0,1]
3. extract_features_from_setup(setup) - Extract 14 features from dict

Files provided: confluence.py, ml_scorer.py, patterns.py
Output: ml_scorer.py (tested, git-ready)

Constraints:
- Use provided RandomForest model
- Don't modify confluence.py
- Don't run expensive operations
"""
# Subagent has clear spec, needs no context hunting
```

### 3. Smart Retries
```python
# Built-in retry logic with cost tracking
result = spawner.spawn_focused_task(
    name="Phase 4 Build",
    files=[...],
    instructions="...",
    timeout_seconds=3600,
    max_retries=2  # Only retry if timeout
)
```

---

## Real Examples

### Example 1: Phase 4 ML Build
**Cost without optimization:** $0.40 × 3 attempts = $1.20  
**Cost with optimization:** $0.01 × 3 attempts = $0.03  
**Savings: $1.17** (97%)

### Example 2: Monthly Backtest Spawns
- 10 backtest runs/month (each spawns a subagent)
- **Without:** 10 × $0.40 = $4.00/month
- **With:** 10 × $0.01 = $0.10/month
- **Savings: $3.90/month**

### Example 3: Iterative Development
- 5 development iterations (test, iterate, refine)
- **Without:** 5 × $0.40 = $2.00
- **With:** 5 × $0.01 = $0.05
- **Savings: $1.95 per feature**

---

## Implementation Checklist

- [ ] Copy `cost_optimized_spawner.py` to your project
- [ ] Import spawner: `from cost_optimized_spawner import CostOptimizedSpawner`
- [ ] List files needed (be specific!)
- [ ] Write focused instructions (clear deliverables)
- [ ] Call `spawner.spawn_focused_task(...)`
- [ ] Check `spawner.print_summary()` for cost breakdown

---

## When to Use

### ✅ Use Optimized Spawner For:
- Building new features (Phase 4, future phases)
- Batch processing (backtest scoring)
- Iterative development (test → refine → deploy)
- One-off tasks (specific, focused work)
- Budget-conscious operations

### ❌ Don't Need Optimization For:
- Live scanning (no subagent spawn)
- Database queries (local SQLite)
- Manual backtests (pure Python, no API)
- Interactive analysis (direct API calls OK)

---

## Cost Comparison Matrix

| Operation | Normal API | Batch API | Optimized Spawn | Savings |
|-----------|-----------|-----------|-----------------|---------|
| Live scan (1h) | $0.02 | N/A | N/A | — |
| Phase 4 build | $0.40 | $0.20 | $0.01 | **97%** |
| Monthly backtest (10) | $4.00 | $2.00 | $0.10 | **97.5%** |
| Development cycle (5) | $2.00 | $1.00 | $0.05 | **97.5%** |
| Model retraining | $1.50 | $0.75 | $0.15 | **90%** |

---

## Advanced: Custom File Resolver

Build context-specific resolvers:

```python
from cost_optimized_spawner import CostOptimizedSpawner, FileResolver

# Custom resolver that knows about your structure
class TradingFileResolver(FileResolver):
    def get_required_files(self, task_type):
        """Return files needed for task type."""
        specs = {
            "phase4": ["confluence.py", "ml_scorer.py", "patterns.py"],
            "backtest": ["confluence.py", "compare_phases.py"],
            "scanner": ["find_trades.py", "confluence.py", "db.py"],
        }
        return specs.get(task_type, [])

# Use it
resolver = TradingFileResolver(base_dir=Path("trading"))
files = resolver.get_required_files("phase4")
attachments, tokens = resolver.build_attachments(files)
```

---

## Monitoring & Alerts

### Cost Anomalies
```python
summary = spawner.get_cost_summary()
cost = float(summary['total_cost'].replace("$", ""))

if cost > 0.50:  # Alert if total > $0.50
    print("⚠️  High spawn cost detected!")
    print(f"Consider reducing context: {summary}")
```

### Cost Trends
```bash
# Track costs over time
python3 -c "from cost_optimized_spawner import CostOptimizedSpawner; s = CostOptimizedSpawner(); s.print_summary()"
```

---

## FAQ

**Q: Why is token estimate 4 chars = 1 token?**  
A: Rough approximation. Actual is ~3.5 chars per token. Use for estimates only.

**Q: Should I attachment binary files?**  
A: No, only text files (.py, .md, .txt, .json). Exclude .pkl, .db, images.

**Q: What if needed file is huge?**  
A: Consider splitting into smaller modules or summarizing in instructions.

**Q: Can I use this with other models?**  
A: Yes, add rates to PRICING dict:
```python
spawner.PRICING["openai/gpt-4"] = {"input": 0.03, "output": 0.06}
```

---

## Metrics & ROI

**Today's spending on subagents:**
- Unoptimized: $1.20 (3 Phase 4 attempts)
- Optimized: $0.03
- **Savings: $1.17 today**

**Monthly projection (10 spawns):**
- Unoptimized: $4.00
- Optimized: $0.10
- **Savings: $3.90/month**

**Yearly:**
- Unoptimized: $48.00
- Optimized: $1.20
- **Savings: $46.80/year**

---

**Ready to deploy. Start using `CostOptimizedSpawner` today. 🚀**
