"""
Atomic Snapshot Writer for UIF Features

Writes data/uif_snapshot.json atomically using tmp → fsync → os.replace pattern.
"""

import json
import os
import time
from typing import Dict, Any


SNAPSHOT_PATH = "data/uif_snapshot.json"


def write_snapshot(symbols_data: Dict[str, Dict[str, Any]]) -> bool:
    """
    Atomically write UIF features snapshot.
    
    Args:
        symbols_data: Dict[symbol -> {adx14, psar_state, momentum5, vol_accel, updated}]
    
    Returns:
        True if write successful, False otherwise
    """
    try:
        os.makedirs("data", exist_ok=True)
        
        snapshot = {
            "ts": int(time.time()),
            "symbols": symbols_data
        }
        
        tmp_path = SNAPSHOT_PATH + ".tmp"
        
        # Write to temp file
        with open(tmp_path, 'w') as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic replace
        os.replace(tmp_path, SNAPSHOT_PATH)
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to write UIF snapshot: {e}")
        return False


def read_snapshot() -> Dict[str, Any]:
    """
    Read current UIF snapshot.
    
    Returns:
        Snapshot dict or empty dict if file doesn't exist/invalid
    """
    try:
        if not os.path.exists(SNAPSHOT_PATH):
            return {}
        
        with open(SNAPSHOT_PATH, 'r') as f:
            return json.load(f)
    
    except Exception as e:
        print(f"[WARN] Failed to read UIF snapshot: {e}")
        return {}


def get_snapshot_age() -> int:
    """
    Get snapshot age in seconds.
    
    Returns:
        Age in seconds, or 9999 if snapshot doesn't exist
    """
    try:
        snapshot = read_snapshot()
        if not snapshot or 'ts' not in snapshot:
            return 9999
        
        return int(time.time() - snapshot['ts'])
    
    except Exception:
        return 9999
