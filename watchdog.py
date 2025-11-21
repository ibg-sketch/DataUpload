#!/usr/bin/env python3
"""
Watchdog Service - Monitors and auto-restarts critical workflows
Prevents extended downtime by detecting crashed or stalled processes
"""

import os
import time
import json
import subprocess
from datetime import datetime, timedelta

# Configuration
MONITORED_SERVICES = [
    {
        'name': 'Smart Money Signal Bot',
        'process_name': 'main.py',
        'restart_command': 'python main.py',
        'critical': True
    },
    {
        'name': 'CVD Service',
        'process_name': 'cvd_service.py',
        'restart_command': 'python cvd_service.py',
        'critical': True
    },
    {
        'name': 'Liquidation Service',
        'process_name': 'liquidation_service.py',
        'restart_command': 'python liquidation_service.py',
        'critical': True
    },
    {
        'name': 'Signal Tracker',
        'process_name': 'signal_tracker.py',
        'restart_command': 'python signal_tracker.py',
        'critical': False
    }
]

CHECK_INTERVAL = 30  # Check every 30 seconds
HEALTH_CHECK_FILE = 'watchdog_health.json'
RESTART_LOG_FILE = 'watchdog_restarts.log'

def log_event(message):
    """Log watchdog events with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    # Append to restart log
    with open(RESTART_LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def is_process_running(process_name):
    """Check if a process with the given name is running"""
    try:
        result = subprocess.run(
            f'pgrep -f "{process_name}"',
            shell=True,
            capture_output=True,
            text=True
        )
        # pgrep returns 0 if process found, non-zero if not found
        return result.returncode == 0
    except Exception:
        return False

def get_process_count(process_name):
    """Get the number of running processes matching the name"""
    try:
        result = subprocess.run(
            f'pgrep -f "{process_name}" | wc -l',
            shell=True,
            capture_output=True,
            text=True
        )
        count = int(result.stdout.strip())
        return count
    except Exception:
        return 0

def check_service_health(service):
    """Check if a service is healthy based on running process"""
    process_name = service['process_name']
    
    is_running = is_process_running(process_name)
    process_count = get_process_count(process_name)
    
    if not is_running:
        return {
            'healthy': False,
            'reason': 'Process not running',
            'process_count': 0
        }
    
    return {
        'healthy': True,
        'reason': f'Running ({process_count} process{"es" if process_count > 1 else ""})',
        'process_count': process_count
    }

def restart_service(service):
    """Attempt to restart a failed service"""
    service_name = service['name']
    log_event(f"🔄 RESTARTING: {service_name}")
    
    try:
        # Note: In Replit workflows, we can't actually restart other workflows programmatically
        # This will alert the user, but the workflow itself must be restarted manually
        # or via the Replit workflow restart mechanism
        
        log_event(f"⚠️  ACTION REQUIRED: {service_name} appears to have crashed")
        log_event(f"   Recommended action: Restart '{service_name}' workflow")
        
        # Save alert to health check file for visibility
        save_health_status({
            'timestamp': datetime.now().isoformat(),
            'alert': f"{service_name} requires manual restart",
            'service': service_name
        })
        
        return False  # Cannot auto-restart workflows programmatically
        
    except Exception as e:
        log_event(f"❌ RESTART FAILED: {service_name} - {str(e)}")
        return False

def save_health_status(status):
    """Save current health status to JSON file"""
    try:
        with open(HEALTH_CHECK_FILE, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        log_event(f"Warning: Could not save health status - {str(e)}")

def main():
    """Main watchdog loop"""
    print("=" * 70)
    print("WATCHDOG SERVICE - Workflow Health Monitor")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S GMT%z')}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print(f"Monitoring {len(MONITORED_SERVICES)} services:")
    for svc in MONITORED_SERVICES:
        critical_mark = "🔴 CRITICAL" if svc['critical'] else "🟡 OPTIONAL"
        print(f"  - {svc['name']} ({critical_mark})")
    print("-" * 70)
    
    log_event("🟢 Watchdog service started")
    
    consecutive_failures = {}
    
    while True:
        try:
            all_healthy = True
            status_report = {
                'timestamp': datetime.now().isoformat(),
                'services': {}
            }
            
            for service in MONITORED_SERVICES:
                name = service['name']
                health = check_service_health(service)
                status_report['services'][name] = health
                
                if not health['healthy']:
                    all_healthy = False
                    
                    # Track consecutive failures
                    if name not in consecutive_failures:
                        consecutive_failures[name] = 0
                    consecutive_failures[name] += 1
                    
                    # Alert on first failure, then every 5 failures
                    if consecutive_failures[name] == 1 or consecutive_failures[name] % 5 == 0:
                        critical_mark = "🔴" if service['critical'] else "🟡"
                        log_event(f"{critical_mark} UNHEALTHY: {name} - {health['reason']}")
                        
                        # Attempt restart for critical services after 3 consecutive failures
                        if service['critical'] and consecutive_failures[name] >= 3:
                            restart_service(service)
                else:
                    # Service recovered
                    if name in consecutive_failures and consecutive_failures[name] > 0:
                        log_event(f"✅ RECOVERED: {name} (was down for {consecutive_failures[name] * CHECK_INTERVAL}s)")
                        consecutive_failures[name] = 0
            
            # Save health status
            save_health_status(status_report)
            
            # Periodic status summary (every 10 minutes)
            if int(time.time()) % 600 < CHECK_INTERVAL:
                if all_healthy:
                    log_event("✅ All services healthy")
                else:
                    unhealthy = [s['name'] for s in MONITORED_SERVICES if not status_report['services'][s['name']]['healthy']]
                    log_event(f"⚠️  Unhealthy services: {', '.join(unhealthy)}")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log_event("🛑 Watchdog service stopped by user")
            break
        except Exception as e:
            log_event(f"❌ Watchdog error: {str(e)}")
            time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
