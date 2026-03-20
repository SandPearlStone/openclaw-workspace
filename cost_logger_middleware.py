#!/usr/bin/env python3
"""
Cost Logger Middleware for Trading System

Wraps API calls to automatically log token usage.
Import this and use the wrapper functions instead of direct API calls.
"""

import functools
from typing import Any, Callable, Dict, Optional
from cost_monitor import TokenUsageMonitor

monitor = TokenUsageMonitor()


def log_api_call(model: str, component: str = "unknown"):
    """
    Decorator to log API call costs.
    
    Usage:
        @log_api_call("anthropic/claude-haiku-4-5", component="phase4_build")
        def my_api_function(...):
            response = client.messages.create(...)
            return response
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            response = func(*args, **kwargs)
            
            # Extract usage if available
            if hasattr(response, 'usage'):
                monitor.log_usage(
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    component=component,
                    notes=func.__name__
                )
            
            return response
        return wrapper
    return decorator


def log_subagent_run(task_name: str, model: str, input_tokens: int, output_tokens: int):
    """
    Log a subagent run cost.
    
    Usage:
        log_subagent_run(
            task_name="Phase 4 ML Build",
            model="anthropic/claude-haiku-4-5",
            input_tokens=88000,
            output_tokens=33200
        )
    """
    monitor.log_usage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        component=f"subagent:{task_name}",
        notes=task_name
    )
    return True


def get_daily_cost() -> str:
    """Get today's total cost."""
    daily = monitor.get_daily_summary()
    return daily["totals"]["cost"]


def get_cost_by_model() -> Dict[str, str]:
    """Get cost breakdown by model today."""
    daily = monitor.get_daily_summary()
    return {model: stats["cost"] for model, stats in daily["by_model"].items()}


def estimate_remaining_budget(daily_limit: float = 50.0) -> Dict[str, Any]:
    """Estimate remaining daily budget."""
    daily = monitor.get_daily_summary()
    current_cost = float(daily["totals"]["cost"].replace("$", ""))
    remaining = daily_limit - current_cost
    
    return {
        "daily_limit": f"${daily_limit:.2f}",
        "current_cost": daily["totals"]["cost"],
        "remaining": f"${remaining:.2f}",
        "percentage_used": f"{(current_cost/daily_limit*100):.1f}%",
        "warning": remaining < 10.0  # Alert if < $10 remaining
    }


if __name__ == "__main__":
    # Test
    print("Testing cost logger middleware...")
    
    # Log a test call
    log_subagent_run(
        task_name="test_run",
        model="anthropic/claude-haiku-4-5",
        input_tokens=1000,
        output_tokens=500
    )
    
    # Print budget
    budget = estimate_remaining_budget()
    print(f"\n💰 Daily Budget Status:")
    for k, v in budget.items():
        print(f"  {k}: {v}")
    
    # Show cost by model
    costs = get_cost_by_model()
    print(f"\n📊 Cost by Model:")
    for model, cost in costs.items():
        print(f"  {model}: {cost}")
