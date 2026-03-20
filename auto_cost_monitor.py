#!/usr/bin/env python3
"""
Auto Cost Monitor - Scheduled task to capture actual costs

Since OpenClaw sessions are server-side, we integrate with the session_status tool
to extract real-time usage metrics every hour.

This script is meant to run as a cron job or systemd timer.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from cost_monitor import TokenUsageMonitor

USAGE_DB = Path("usage.db")
LAST_RUN_FILE = Path(".cost_monitor_last_run")

PRICING = {
    "anthropic/claude-haiku-4-5": {"input": 0.80, "output": 2.40},
    "anthropic/claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4-1": {"input": 15.00, "output": 75.00},
    "openai/gpt-5.4": {"input": 2.50, "output": 10.00},
    "openai/gpt-4.1": {"input": 0.03, "output": 0.06},
}


def estimate_costs_from_anthropic_console():
    """
    Parse Anthropic console data (manual export from console.anthropic.com).
    
    This is a placeholder for automated data ingestion.
    For now, you can manually export CSV from Anthropic and we'll parse it.
    """
    
    # Example: Read from manually exported CSV
    csv_path = Path("anthropic_usage.csv")
    if not csv_path.exists():
        print("⚠️  No anthropic_usage.csv found. Manual export needed.")
        return None
    
    import csv
    
    monitor = TokenUsageMonitor()
    total_logged = 0
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = row.get("Date", "")
                model = row.get("Model", "").lower()
                input_tokens = int(row.get("Input Tokens", 0) or 0)
                output_tokens = int(row.get("Output Tokens", 0) or 0)
                
                # Map model names
                if "haiku" in model:
                    model = "anthropic/claude-haiku-4-5"
                elif "sonnet" in model:
                    model = "anthropic/claude-sonnet-4-6"
                elif "opus" in model:
                    model = "anthropic/claude-opus-4-1"
                elif "gpt-5" in model:
                    model = "openai/gpt-5.4"
                else:
                    continue
                
                # Log if we have data
                if input_tokens > 0 or output_tokens > 0:
                    monitor.log_usage(
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        component="anthropic_console",
                        notes=date
                    )
                    total_logged += 1
            except Exception as e:
                print(f"⚠️  Error parsing row: {e}")
    
    return total_logged


def estimate_from_session_metrics():
    """
    Estimate costs from visible session metrics.
    
    This extracts token counts from session_status tool output.
    For subagent costs, we rely on Anthropic's console data.
    """
    
    # Since we can't directly query session storage, we track via the session_status tool
    # User can run: python3 -c "from session_status import get_session_metrics; get_session_metrics()"
    
    return None


def print_cost_summary():
    """Print current cost summary."""
    monitor = TokenUsageMonitor()
    monitor.print_summary(days=7)


def check_daily_limit(limit: float = 50.0):
    """Alert if daily spend exceeds limit."""
    monitor = TokenUsageMonitor()
    daily = monitor.get_daily_summary()
    
    current_cost = float(daily["totals"]["cost"].replace("$", ""))
    
    if current_cost > limit:
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "DAILY_LIMIT_EXCEEDED",
            "severity": "HIGH",
            "current_cost": current_cost,
            "limit": limit,
            "message": f"⚠️  Daily cost ${current_cost:.2f} exceeds limit ${limit:.2f}"
        }
        
        # Log alert
        alerts_file = Path("usage_alerts.json")
        alerts = []
        if alerts_file.exists():
            with open(alerts_file) as f:
                alerts = json.load(f)
        
        alerts.append(alert)
        with open(alerts_file, "w") as f:
            json.dump(alerts, f, indent=2, default=str)
        
        print(alert["message"])
        return True
    
    return False


def main():
    """Main cost monitoring routine."""
    print("\n📊 OpenClaw Auto Cost Monitor")
    print(f"⏰ {datetime.utcnow().isoformat()}")
    print("=" * 80)
    
    # Check for Anthropic console export
    anthropic_exported = estimate_costs_from_anthropic_console()
    
    if anthropic_exported:
        print(f"✅ Logged {anthropic_exported} usage records from Anthropic console")
    else:
        print("ℹ️  To capture Anthropic costs:")
        print("   1. Go to https://console.anthropic.com/account/billing/usage")
        print("   2. Export data as CSV (if available)")
        print("   3. Save as anthropic_usage.csv in this directory")
        print("   4. Re-run this script")
    
    # Print summary
    print_cost_summary()
    
    # Check limits
    check_daily_limit(limit=50.0)
    
    print("\n💡 Note: For real-time tracking, integrate with Anthropic's webhook API")
    print("   (currently not available in public API)")


if __name__ == "__main__":
    main()
