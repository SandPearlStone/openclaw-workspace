#!/usr/bin/env python3
"""
OpenClaw Session Cost Collector

Automatically captures token usage from OpenClaw sessions and logs to cost_monitor.db.
Monitors session history and extracts usage metrics.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import glob

# Pricing rates (2026-03)
PRICING = {
    "anthropic/claude-haiku-4-5": {"input": 0.80, "output": 2.40},
    "anthropic/claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4-1": {"input": 15.00, "output": 75.00},
    "openai/gpt-5.4": {"input": 2.50, "output": 10.00},
    "openai/gpt-4.1": {"input": 0.03, "output": 0.06},
}

USAGE_DB = Path("/home/sandro/.openclaw/workspace/usage.db")
SESSIONS_DIR = Path("/home/sandro/.openclaw/sessions")
STATE_FILE = Path("/home/sandro/.openclaw/workspace/cost_collector_state.json")


class SessionCostCollector:
    """Collects costs from OpenClaw session files."""
    
    def __init__(self):
        self.db = USAGE_DB
        self.sessions_dir = SESSIONS_DIR
        self.state_file = STATE_FILE
        self._ensure_db()
        self._load_state()
    
    def _ensure_db(self):
        """Ensure cost_monitor database exists."""
        if not self.db.exists():
            from cost_monitor import TokenUsageMonitor
            monitor = TokenUsageMonitor()
    
    def _load_state(self):
        """Load last processed sessions state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                self.state = json.load(f)
        else:
            self.state = {"last_check": None, "processed_sessions": {}}
    
    def _save_state(self):
        """Save state for resume on restart."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, default=str)
    
    def find_all_sessions(self) -> List[Path]:
        """Find all session files."""
        if not self.sessions_dir.exists():
            return []
        
        # Look for session JSON files
        sessions = []
        for pattern in ["*.json", "**/*.json"]:
            sessions.extend(self.sessions_dir.glob(pattern))
        
        return sorted(set(sessions))
    
    def parse_session_file(self, session_path: Path) -> Optional[Dict]:
        """Parse OpenClaw session JSON file."""
        try:
            with open(session_path) as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"❌ Error parsing {session_path}: {e}")
            return None
    
    def extract_usage_from_session(self, session_data: Dict) -> Optional[Tuple[str, int, int, str]]:
        """
        Extract token usage from session metadata.
        Returns: (model, input_tokens, output_tokens, timestamp)
        """
        
        # Try to find usage in various places
        usage = None
        timestamp = None
        model = None
        
        # Check message-level usage
        if "messages" in session_data:
            for msg in session_data.get("messages", []):
                if "usage" in msg:
                    usage = msg["usage"]
                    timestamp = msg.get("timestamp") or msg.get("created_at")
                    break
        
        # Check metadata
        if not usage and "metadata" in session_data:
            meta = session_data["metadata"]
            if "usage" in meta:
                usage = meta["usage"]
            if "model" in meta:
                model = meta["model"]
            timestamp = meta.get("timestamp") or meta.get("created_at")
        
        # Check top-level
        if not usage and "usage" in session_data:
            usage = session_data["usage"]
        if not model and "model" in session_data:
            model = session_data["model"]
        
        # Extract timestamp
        if not timestamp:
            timestamp = session_data.get("timestamp") or session_data.get("created_at") or datetime.utcnow().isoformat()
        
        if not usage or not model:
            return None
        
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        
        return model, input_tokens, output_tokens, timestamp
    
    def log_session_usage(self, session_id: str, model: str, input_tokens: int,
                          output_tokens: int, timestamp: str, session_type: str = "unknown"):
        """Log usage from a session to the database."""
        
        rates = PRICING.get(model, {"input": 0, "output": 0})
        input_cost = input_tokens * rates["input"] / 1_000_000
        output_cost = output_tokens * rates["output"] / 1_000_000
        total_cost = input_cost + output_cost
        
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
        # Check if already logged
        c.execute('''
            SELECT id FROM usage
            WHERE session_key = ? AND model = ?
        ''', (session_id, model))
        
        if c.fetchone():
            conn.close()
            return False  # Already logged
        
        c.execute('''
            INSERT INTO usage 
            (timestamp, session_key, model, input_tokens, output_tokens, 
             input_cost, output_cost, total_cost, component, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, session_id, model, input_tokens, output_tokens,
              input_cost, output_cost, total_cost, f"session:{session_type}", session_id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def collect_from_sessions(self) -> Dict:
        """Collect all session costs."""
        results = {
            "new_sessions": 0,
            "new_costs": 0,
            "total_cost": 0.0,
            "sessions_processed": []
        }
        
        sessions = self.find_all_sessions()
        print(f"Found {len(sessions)} session files")
        
        for session_path in sessions:
            session_id = session_path.stem
            
            # Skip if already processed
            if session_id in self.state["processed_sessions"]:
                continue
            
            session_data = self.parse_session_file(session_path)
            if not session_data:
                continue
            
            results["new_sessions"] += 1
            
            # Try to extract usage
            usage_data = self.extract_usage_from_session(session_data)
            if usage_data:
                model, input_tokens, output_tokens, timestamp = usage_data
                
                if self.log_session_usage(session_id, model, input_tokens, output_tokens, timestamp):
                    results["new_costs"] += 1
                    
                    # Calculate cost
                    rates = PRICING.get(model, {"input": 0, "output": 0})
                    cost = input_tokens * rates["input"] / 1_000_000 + output_tokens * rates["output"] / 1_000_000
                    results["total_cost"] += cost
                    
                    results["sessions_processed"].append({
                        "id": session_id,
                        "model": model,
                        "tokens": input_tokens + output_tokens,
                        "cost": f"${cost:.4f}"
                    })
            
            # Mark as processed
            self.state["processed_sessions"][session_id] = datetime.utcnow().isoformat()
        
        self.state["last_check"] = datetime.utcnow().isoformat()
        self._save_state()
        
        return results
    
    def print_summary(self, results: Dict):
        """Print collection results."""
        print("\n" + "=" * 80)
        print("💰 SESSION COST COLLECTION SUMMARY")
        print("=" * 80)
        print(f"Sessions found: {results['new_sessions']}")
        print(f"New costs logged: {results['new_costs']}")
        print(f"Total from new sessions: ${results['total_cost']:.2f}")
        
        if results["sessions_processed"]:
            print("\nSessions processed:")
            for s in results["sessions_processed"]:
                print(f"  {s['id']:<40} {s['model']:<30} {s['tokens']:>8} tokens  {s['cost']}")
        
        print("=" * 80)


def main():
    """Main entry point."""
    collector = SessionCostCollector()
    
    print("🔍 Collecting costs from OpenClaw sessions...")
    results = collector.collect_from_sessions()
    
    collector.print_summary(results)
    
    # Total spend so far
    conn = sqlite3.connect(USAGE_DB)
    c = conn.cursor()
    c.execute('SELECT SUM(total_cost) FROM usage')
    total = c.fetchone()[0] or 0
    conn.close()
    
    print(f"\n📊 Cumulative spend (all captured): ${total:.2f}")


if __name__ == "__main__":
    main()
