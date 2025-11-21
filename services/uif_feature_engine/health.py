"""
Health Status Endpoint for UIF Feature Engine

Provides /status JSON with engine state and snapshot age.
"""

import json
import time
from typing import Dict, Any
from .snapshot import get_snapshot_age, read_snapshot


def get_health_status() -> Dict[str, Any]:
    """
    Get UIF engine health status.
    
    Returns:
        Dict with engine status, snapshot age, and per-symbol health
    """
    try:
        snapshot = read_snapshot()
        snapshot_age = get_snapshot_age()
        
        # Determine overall engine status
        if not snapshot or snapshot_age > 90:
            engine_status = "DEGRADED"
        else:
            engine_status = "OK"
        
        # Per-symbol status
        symbols_status = {}
        if snapshot and 'symbols' in snapshot:
            current_time = int(time.time())
            for symbol, data in snapshot['symbols'].items():
                updated = data.get('updated', 0)
                age = current_time - updated
                symbols_status[symbol] = "OK" if age <= 90 else "STALE"
        
        return {
            "uif_engine": engine_status,
            "uif_snapshot_age_sec": snapshot_age,
            "symbols": symbols_status
        }
    
    except Exception as e:
        return {
            "uif_engine": "ERROR",
            "uif_snapshot_age_sec": 9999,
            "error": str(e),
            "symbols": {}
        }


def print_status():
    """Print health status to console."""
    status = get_health_status()
    print(json.dumps(status, indent=2))


def get_status_json() -> str:
    """Get health status as JSON string."""
    return json.dumps(get_health_status(), indent=2)
