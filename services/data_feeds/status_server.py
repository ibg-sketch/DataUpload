"""
Lightweight HTTP server for health status monitoring.
"""
import asyncio
import json
from aiohttp import web
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .health import HealthMonitor


class StatusServer:
    """Lightweight HTTP server for /status endpoint"""
    
    def __init__(self, health_monitor: 'HealthMonitor', port: int = 8080):
        self.health = health_monitor
        self.port = port
        self.app = None
        self.runner = None
        self.site = None
    
    async def start(self):
        """Start the HTTP server"""
        self.app = web.Application()
        self.app.router.add_get('/status', self.handle_status)
        self.app.router.add_get('/health', self.handle_status)  # Alias
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()
        
        print(f"[HTTP] Status server running on http://0.0.0.0:{self.port}/status")
    
    async def stop(self):
        """Stop the HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
    
    async def handle_status(self, request):
        """Handle GET /status requests"""
        try:
            status_data = self.health.get_status()
            
            # Determine overall health status
            overall_healthy = status_data.get('overall_healthy', False)
            http_status = 200 if overall_healthy else 503
            
            return web.Response(
                text=json.dumps(status_data, indent=2),
                content_type='application/json',
                status=http_status
            )
        except Exception as e:
            return web.Response(
                text=json.dumps({'error': str(e)}),
                content_type='application/json',
                status=500
            )
