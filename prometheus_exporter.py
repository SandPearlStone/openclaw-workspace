#!/usr/bin/env python3
"""
Prometheus Exporter for OpenClaw Cost Monitoring

Exposes cost metrics in Prometheus format for scraping by Prometheus/Grafana.
Reads from cost_monitor.py SQLite database.
"""

from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, generate_latest
from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time

DB_PATH = Path("usage.db")
LISTEN_PORT = 9200


class CostMetrics:
    """Prometheus metrics for API cost tracking."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Gauges
        self.daily_cost = Gauge(
            'openclaw_daily_cost_usd',
            'Total API cost for the current day',
            registry=self.registry
        )
        
        self.daily_tokens = Gauge(
            'openclaw_daily_tokens_total',
            'Total tokens used today',
            registry=self.registry
        )
        
        self.daily_calls = Gauge(
            'openclaw_daily_api_calls',
            'Number of API calls today',
            registry=self.registry
        )
        
        # By model
        self.cost_by_model = Gauge(
            'openclaw_cost_by_model_usd',
            'API cost by model',
            labelnames=['model'],
            registry=self.registry
        )
        
        self.tokens_by_model = Gauge(
            'openclaw_tokens_by_model',
            'Total tokens by model',
            labelnames=['model'],
            registry=self.registry
        )
        
        self.calls_by_model = Gauge(
            'openclaw_calls_by_model',
            'API calls by model',
            labelnames=['model'],
            registry=self.registry
        )
        
        # By component
        self.cost_by_component = Gauge(
            'openclaw_cost_by_component_usd',
            'API cost by component',
            labelnames=['component'],
            registry=self.registry
        )
        
        # Running 7-day average
        self.weekly_avg_cost = Gauge(
            'openclaw_weekly_avg_cost_usd',
            '7-day average daily cost',
            registry=self.registry
        )
        
        # Counters
        self.total_spend = Counter(
            'openclaw_total_spend_usd',
            'Cumulative API spend',
            registry=self.registry
        )
    
    def update_from_db(self):
        """Update all metrics from database."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Today's summary
            today = datetime.utcnow().strftime("%Y-%m-%d")
            c.execute('''
                SELECT SUM(total_cost), SUM(input_tokens + output_tokens), COUNT(*)
                FROM usage
                WHERE DATE(timestamp) = ?
            ''', (today,))
            
            result = c.fetchone()
            today_cost = result[0] or 0.0
            today_tokens = result[1] or 0
            today_calls = result[2] or 0
            
            self.daily_cost.set(today_cost)
            self.daily_tokens.set(today_tokens)
            self.daily_calls.set(today_calls)
            
            # By model (today)
            c.execute('''
                SELECT model, SUM(total_cost), SUM(input_tokens + output_tokens), COUNT(*)
                FROM usage
                WHERE DATE(timestamp) = ?
                GROUP BY model
            ''', (today,))
            
            for row in c.fetchall():
                model, cost, tokens, calls = row
                if cost is None:
                    continue
                self.cost_by_model.labels(model=model).set(cost or 0)
                self.tokens_by_model.labels(model=model).set(tokens or 0)
                self.calls_by_model.labels(model=model).set(calls or 0)
            
            # By component (today)
            c.execute('''
                SELECT component, SUM(total_cost)
                FROM usage
                WHERE DATE(timestamp) = ? AND component IS NOT NULL
                GROUP BY component
            ''', (today,))
            
            for row in c.fetchall():
                component, cost = row
                if cost:
                    self.cost_by_component.labels(component=component).set(cost)
            
            # 7-day average
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            c.execute('''
                SELECT AVG(daily_cost)
                FROM (
                    SELECT DATE(timestamp) as date, SUM(total_cost) as daily_cost
                    FROM usage
                    WHERE DATE(timestamp) >= ?
                    GROUP BY DATE(timestamp)
                )
            ''', (week_ago,))
            
            avg = c.fetchone()[0] or 0
            self.weekly_avg_cost.set(avg)
            
            # Total cumulative spend
            c.execute('SELECT SUM(total_cost) FROM usage')
            total = c.fetchone()[0] or 0
            self.total_spend._value.get()  # Get current value
            self.total_spend._value._value = total  # Set directly (Counter limitation)
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error updating metrics: {e}")
    
    def export(self) -> str:
        """Export metrics in Prometheus format."""
        self.update_from_db()
        return generate_latest(self.registry).decode('utf-8')


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus /metrics endpoint."""
    
    metrics = None  # Will be set by server
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.metrics.export().encode('utf-8'))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class PrometheusServer:
    """Prometheus metrics exporter server."""
    
    def __init__(self, port: int = LISTEN_PORT):
        self.port = port
        self.metrics = CostMetrics()
        MetricsHandler.metrics = self.metrics
    
    def run(self):
        """Start the HTTP server."""
        server = HTTPServer(('0.0.0.0', self.port), MetricsHandler)
        print(f"✅ Prometheus exporter listening on 0.0.0.0:{self.port}")
        print(f"   Metrics: http://localhost:{self.port}/metrics")
        print(f"   Health: http://localhost:{self.port}/health")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n✅ Shutting down...")
            server.shutdown()


if __name__ == "__main__":
    server = PrometheusServer(LISTEN_PORT)
    server.run()
