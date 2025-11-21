"""
Health monitoring for data feeds service.
"""
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum


class FeedStatus(str, Enum):
    """Feed health status"""
    CONNECTED = "connected"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class SymbolHealth:
    """Health tracking for a single symbol"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.status = FeedStatus.OFFLINE
        self.last_update: Optional[datetime] = None
        self.error_count = 0
        self.success_count = 0
        self.last_error: Optional[str] = None
        self.errors_window_start = datetime.now()
    
    def update_success(self):
        """Record successful data collection"""
        self.last_update = datetime.now()
        self.success_count += 1
        
        # Reset error count if we're recovering
        if self.status == FeedStatus.DEGRADED and self.success_count > 3:
            self.error_count = 0
            self.status = FeedStatus.CONNECTED
        elif self.status == FeedStatus.OFFLINE:
            self.status = FeedStatus.CONNECTED
    
    def update_error(self, error_msg: str):
        """Record error"""
        self.error_count += 1
        self.last_error = error_msg
        
        # Degrade status based on error count
        if self.error_count >= 5:
            self.status = FeedStatus.OFFLINE
        elif self.error_count >= 2:
            self.status = FeedStatus.DEGRADED
    
    def reset_hourly_counters(self):
        """Reset error counters every hour"""
        now = datetime.now()
        if (now - self.errors_window_start) > timedelta(hours=1):
            self.error_count = 0
            self.success_count = 0
            self.errors_window_start = now
    
    def get_last_update_age(self) -> Optional[int]:
        """Get seconds since last update"""
        if self.last_update is None:
            return None
        return int((datetime.now() - self.last_update).total_seconds())
    
    def to_dict(self) -> dict:
        """Export to dict"""
        return {
            'status': self.status.value,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'last_update_age_sec': self.get_last_update_age(),
            'error_count': self.error_count,
            'success_count': self.success_count,
            'last_error': self.last_error
        }


class HealthMonitor:
    """Health monitoring for all symbols"""
    
    def __init__(self, symbols: list[str]):
        self.symbols_health: Dict[str, SymbolHealth] = {
            symbol: SymbolHealth(symbol) for symbol in symbols
        }
        self.service_start_time = datetime.now()
        self.cycle_count = 0
        self.total_latency_ms = 0
        
        # Synthetic Basis tracking
        self.basis_status = "MISSING"  # OK, DEGRADED, MISSING
        self.basis_provider: Optional[str] = None
        self.basis_last_update: Optional[datetime] = None
        self.basis_success_count = 0
        self.basis_fail_count = 0
    
    def record_success(self, symbol: str):
        """Record successful data collection for symbol"""
        if symbol in self.symbols_health:
            self.symbols_health[symbol].update_success()
    
    def record_error(self, symbol: str, error_msg: str):
        """Record error for symbol"""
        if symbol in self.symbols_health:
            self.symbols_health[symbol].update_error(error_msg)
    
    def record_cycle(self, latency_ms: int):
        """Record completion of a data collection cycle"""
        self.cycle_count += 1
        self.total_latency_ms += latency_ms
        
        # Reset hourly counters
        for health in self.symbols_health.values():
            health.reset_hourly_counters()
    
    def record_basis_success(self, provider: str):
        """Record successful synthetic basis calculation"""
        self.basis_success_count += 1
        self.basis_provider = provider
        self.basis_last_update = datetime.now()
        
        # Update status
        if self.basis_fail_count > 0 and self.basis_success_count > 3:
            self.basis_fail_count = 0
            self.basis_status = "OK"
        elif self.basis_status == "MISSING":
            self.basis_status = "OK"
    
    def record_basis_failure(self):
        """Record failed synthetic basis calculation"""
        self.basis_fail_count += 1
        
        # Update status based on failure count
        if self.basis_fail_count >= 5:
            self.basis_status = "MISSING"
        elif self.basis_fail_count >= 2:
            self.basis_status = "DEGRADED"
    
    def get_overall_status(self) -> FeedStatus:
        """Get overall service status"""
        offline_count = sum(1 for h in self.symbols_health.values() if h.status == FeedStatus.OFFLINE)
        degraded_count = sum(1 for h in self.symbols_health.values() if h.status == FeedStatus.DEGRADED)
        
        # If more than 50% offline, service is offline
        if offline_count > len(self.symbols_health) / 2:
            return FeedStatus.OFFLINE
        
        # If any degraded or offline, service is degraded
        if degraded_count > 0 or offline_count > 0:
            return FeedStatus.DEGRADED
        
        return FeedStatus.CONNECTED
    
    def get_avg_latency(self) -> int:
        """Get average cycle latency in ms"""
        if self.cycle_count == 0:
            return 0
        return self.total_latency_ms // self.cycle_count
    
    def get_uptime_seconds(self) -> int:
        """Get service uptime in seconds"""
        return int((datetime.now() - self.service_start_time).total_seconds())
    
    def to_dict(self) -> dict:
        """Export full health status"""
        return {
            'overall_status': self.get_overall_status().value,
            'uptime_seconds': self.get_uptime_seconds(),
            'cycle_count': self.cycle_count,
            'avg_latency_ms': self.get_avg_latency(),
            'symbols': {
                symbol: health.to_dict() 
                for symbol, health in self.symbols_health.items()
            }
        }
    
    def get_status(self) -> dict:
        """Get status dict for HTTP API (includes overall_healthy flag)"""
        overall_status = self.get_overall_status()
        overall_healthy = overall_status == FeedStatus.CONNECTED
        
        status_dict = {
            'overall_healthy': overall_healthy,
            'overall_status': overall_status.value,
            'uptime_seconds': self.get_uptime_seconds(),
            'cycle_count': self.cycle_count,
            'avg_latency_ms': self.get_avg_latency(),
            'symbols': {
                symbol: health.to_dict() 
                for symbol, health in self.symbols_health.items()
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Add synthetic basis status if enabled
        if self.basis_status != "MISSING" or self.basis_success_count > 0:
            status_dict['basis'] = {
                'status': self.basis_status,
                'provider': self.basis_provider,
                'last_update': self.basis_last_update.isoformat() if self.basis_last_update else None,
                'success_count': self.basis_success_count,
                'fail_count': self.basis_fail_count
            }
        
        return status_dict
    
    def print_summary(self):
        """Print health summary to console"""
        overall = self.get_overall_status()
        uptime_hours = self.get_uptime_seconds() / 3600
        
        status_emoji = {
            FeedStatus.CONNECTED: "✅",
            FeedStatus.DEGRADED: "⚠️",
            FeedStatus.OFFLINE: "❌"
        }
        
        print(f"\n[HEALTH] {status_emoji[overall]} Overall: {overall.value.upper()}")
        print(f"[HEALTH] Uptime: {uptime_hours:.1f}h | Cycles: {self.cycle_count} | Avg Latency: {self.get_avg_latency()}ms")
        
        # Show degraded/offline symbols
        for symbol, health in self.symbols_health.items():
            if health.status != FeedStatus.CONNECTED:
                age = health.get_last_update_age()
                age_str = f"{age}s ago" if age else "never"
                print(f"[HEALTH] {status_emoji[health.status]} {symbol}: {health.status.value} (last: {age_str}, errors: {health.error_count})")
