"""
Health monitoring and status reporting for AI Analyst service
"""

import time
import logging
from typing import Dict, Any, Optional
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Track AI Analyst service health and statistics"""
    
    def __init__(self):
        self.last_call_time = None
        self.total_calls = 0
        self.total_errors = 0
        
        self.error_window = deque(maxlen=1000)
        
        self.call_history = deque(maxlen=1000)
        
        logger.info("HealthMonitor initialized")
    
    def record_call(self, success: bool, error: Optional[str] = None):
        """
        Record an API call
        
        Args:
            success: Whether the call succeeded
            error: Error message if failed
        """
        now = time.time()
        self.last_call_time = now
        self.total_calls += 1
        
        self.call_history.append((now, success))
        
        if not success:
            self.total_errors += 1
            self.error_window.append((now, error or 'Unknown error'))
            logger.warning(f"Recorded error: {error}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current health status
        
        Returns:
            {
                'status': 'OK' | 'DEGRADED' | 'DOWN',
                'last_call_age_sec': int,
                'calls_hour': int,
                'errors_24h': int,
                'total_calls': int,
                'total_errors': int,
                'uptime_hours': float
            }
        """
        now = time.time()
        
        if self.last_call_time is None:
            last_call_age = -1
        else:
            last_call_age = int(now - self.last_call_time)
        
        hour_ago = now - 3600
        calls_hour = sum(1 for t, _ in self.call_history if t > hour_ago)
        
        day_ago = now - 86400
        errors_24h = sum(1 for t, _ in self.error_window if t > day_ago)
        
        if self.total_calls == 0:
            status = 'DOWN'
        elif errors_24h > 50:
            status = 'DEGRADED'
        elif last_call_age > 7200:
            status = 'DEGRADED'
        else:
            status = 'OK'
        
        return {
            'status': status,
            'last_call_age_sec': last_call_age,
            'calls_hour': calls_hour,
            'errors_24h': errors_24h,
            'total_calls': self.total_calls,
            'total_errors': self.total_errors
        }
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors for debugging"""
        recent = [(datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'), err) 
                  for t, err in list(self.error_window)[-limit:]]
        return recent
