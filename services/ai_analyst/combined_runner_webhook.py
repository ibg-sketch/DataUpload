"""
AI Analyst Combined Service - Webhook Mode
Runs both AI Analyst scheduler (daily summaries) and Telegram webhook server
VERSION: 2.0 - Webhook implementation
"""

import os
import sys
import time
import threading
import logging

# Setup UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    force=True
)
logger = logging.getLogger(__name__)

def run_ai_analyst_scheduler():
    """Run AI Analyst scheduler for daily summaries"""
    try:
        from services.ai_analyst.runner import AIAnalystService
        
        logger.info("Initializing AI Analyst Service...")
        ai_analyst = AIAnalystService()
        
        if not ai_analyst.enabled:
            logger.error("AI Analyst is disabled in config")
            return
        
        logger.info("Starting AI Analyst scheduler...")
        ai_analyst.run_scheduler()
        
    except Exception as e:
        logger.error(f"AI Analyst scheduler failed: {e}", exc_info=True)


def run_webhook_server():
    """Run Flask webhook server"""
    try:
        # Import webhook server main function
        import webhook_server
        
        logger.info("Starting Telegram webhook server...")
        webhook_server.main()
        
    except Exception as e:
        logger.error(f"Webhook server failed: {e}", exc_info=True)


def main():
    """Start both services"""
    logger.info("=" * 70)
    logger.info("AI Analyst Combined Service Starting...")
    logger.info("Services: Daily Summaries + Telegram Webhook (/ask_ai)")
    logger.info("=" * 70)
    
    # Start AI Analyst scheduler in background thread
    logger.info("Starting AI Analyst scheduler thread...")
    scheduler_thread = threading.Thread(target=run_ai_analyst_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Give scheduler time to initialize
    time.sleep(2)
    
    # Start webhook server in main thread (Flask needs main thread)
    logger.info("Starting Telegram Webhook Server in main thread...")
    logger.info("Both services started successfully")
    logger.info("- AI Analyst: Scheduled daily summaries at 18:59 UTC")
    logger.info("- Telegram Bot: Webhook mode for /ask_ai commands")
    logger.info("=" * 70)
    
    run_webhook_server()


if __name__ == '__main__':
    main()
