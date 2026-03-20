#!/usr/bin/env python3
"""
OpenClaw Token Usage Monitor

Tracks actual token usage and costs across all sessions.
Logs to JSON for analysis and alerting.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Pricing rates (2026-03)
PRICING = {
    "anthropic/claude-haiku-4-5": {"input": 0.80, "output": 2.40},
    "anthropic/claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4-1": {"input": 15.00, "output": 75.00},
    "openai/gpt-5.4": {"input": 2.50, "output": 10.00},
    "openai/gpt-4.1": {"input": 0.03, "output": 0.06},
}

DB_PATH = Path("usage.db")
JSON_LOG = Path("usage_log.json")
ALERTS_LOG = Path("usage_alerts.json")


class TokenUsageMonitor:
    """Monitor and log token usage across all OpenClaw sessions."""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.json_log = JSON_LOG
        self.alerts_log = ALERTS_LOG
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for usage tracking."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_key TEXT,
                session_id TEXT,
                model TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                input_cost REAL DEFAULT 0,
                output_cost REAL DEFAULT 0,
                total_cost REAL DEFAULT 0,
                component TEXT,
                notes TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                date TEXT PRIMARY KEY,
                total_cost REAL,
                haiku_cost REAL,
                sonnet_cost REAL,
                gpt_cost REAL,
                total_tokens INTEGER,
                session_count INTEGER,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_usage(self, model: str, input_tokens: int, output_tokens: int,
                  session_key: Optional[str] = None, component: str = "unknown",
                  notes: str = "") -> Dict:
        """Log a single API usage event."""
        
        rates = PRICING.get(model, {"input": 0, "output": 0})
        input_cost = input_tokens * rates["input"] / 1_000_000
        output_cost = output_tokens * rates["output"] / 1_000_000
        total_cost = input_cost + output_cost
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        timestamp = datetime.utcnow().isoformat()
        
        c.execute('''
            INSERT INTO usage 
            (timestamp, session_key, model, input_tokens, output_tokens, 
             input_cost, output_cost, total_cost, component, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, session_key, model, input_tokens, output_tokens,
              input_cost, output_cost, total_cost, component, notes))
        
        conn.commit()
        conn.close()
        
        return {
            "timestamp": timestamp,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": f"${input_cost:.6f}",
            "output_cost": f"${output_cost:.6f}",
            "total_cost": f"${total_cost:.6f}",
            "component": component
        }
    
    def get_daily_summary(self, date: Optional[str] = None) -> Dict:
        """Get cost summary for a specific day."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get all usage for the day
        c.execute('''
            SELECT model, SUM(input_tokens), SUM(output_tokens), SUM(total_cost), COUNT(*)
            FROM usage
            WHERE DATE(timestamp) = ?
            GROUP BY model
        ''', (date,))
        
        results = c.fetchall()
        conn.close()
        
        summary = {
            "date": date,
            "by_model": {},
            "totals": {
                "cost": 0.0,
                "tokens": 0,
                "calls": 0
            }
        }
        
        for model, input_t, output_t, cost, count in results:
            if input_t is None:
                continue
            
            summary["by_model"][model] = {
                "input_tokens": input_t,
                "output_tokens": output_t,
                "total_tokens": input_t + output_t,
                "cost": f"${cost:.2f}",
                "calls": count
            }
            
            summary["totals"]["cost"] += cost
            summary["totals"]["tokens"] += input_t + output_t
            summary["totals"]["calls"] += count
        
        summary["totals"]["cost"] = f"${summary['totals']['cost']:.2f}"
        
        return summary
    
    def get_usage_trend(self, days: int = 7) -> List[Dict]:
        """Get daily usage trend for the last N days."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        c.execute('''
            SELECT DATE(timestamp) as date, SUM(total_cost), SUM(input_tokens + output_tokens), COUNT(*)
            FROM usage
            WHERE DATE(timestamp) >= ?
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        ''', (start_date,))
        
        results = c.fetchall()
        conn.close()
        
        return [
            {
                "date": row[0],
                "cost": f"${row[1]:.2f}",
                "tokens": row[2],
                "calls": row[3]
            }
            for row in results
        ]
    
    def check_alerts(self, daily_limit: float = 50.0) -> List[Dict]:
        """Check for alerts (e.g., daily spend exceeding limit)."""
        alerts = []
        daily = self.get_daily_summary()
        
        current_cost = float(daily["totals"]["cost"].replace("$", ""))
        if current_cost > daily_limit:
            alerts.append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "DAILY_LIMIT_EXCEEDED",
                "severity": "HIGH",
                "message": f"Daily cost ${current_cost:.2f} exceeds limit ${daily_limit:.2f}",
                "current_cost": current_cost,
                "limit": daily_limit
            })
        
        return alerts
    
    def export_json(self):
        """Export all usage data to JSON."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT * FROM usage ORDER BY timestamp DESC')
        rows = c.fetchall()
        
        columns = [desc[0] for desc in c.description]
        data = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        
        with open(self.json_log, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        return len(data)
    
    def print_summary(self, days: int = 7):
        """Print a formatted summary."""
        print("\n" + "=" * 80)
        print("📊 TOKEN USAGE MONITOR — 7-Day Summary")
        print("=" * 80)
        
        trend = self.get_usage_trend(days)
        
        total_cost = 0.0
        total_tokens = 0
        
        for day in trend:
            cost = float(day["cost"].replace("$", ""))
            print(f"\n{day['date']}: {day['cost']:<12} ({day['tokens']:>7,} tokens, {day['calls']:>3} calls)")
            total_cost += cost
            total_tokens += day["tokens"]
        
        print("\n" + "=" * 80)
        print(f"Total (7 days): ${total_cost:.2f} ({total_tokens:,} tokens)")
        print(f"Daily average: ${total_cost/days:.2f}")
        
        # Today's breakdown
        today = self.get_daily_summary()
        print(f"\n📈 TODAY'S BREAKDOWN:")
        for model, stats in today["by_model"].items():
            print(f"  {model:<35} {stats['cost']:<12} ({stats['total_tokens']:>7,} tokens)")
        
        print("=" * 80)


if __name__ == "__main__":
    monitor = TokenUsageMonitor()
    
    # Example: Log a test call
    monitor.log_usage(
        "anthropic/claude-haiku-4-5",
        input_tokens=1000,
        output_tokens=500,
        component="test",
        notes="Example log entry"
    )
    
    # Show summary
    monitor.print_summary()
    
    # Export JSON
    count = monitor.export_json()
    print(f"\n✅ Exported {count} usage records to {monitor.json_log}")
