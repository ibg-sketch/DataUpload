"""
Combined AI Analyst + Telegram Command Bot Runner
Runs both services in parallel threads
VERSION: 1.0 - Initial combined service
"""

import os
import sys
import threading
import logging
from typing import Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.ai_analyst.runner import AIAnalystService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_ai_analyst_scheduler():
    """Run AI Analyst daily summary scheduler"""
    try:
        logger.info("Starting AI Analyst scheduler thread...")
        service = AIAnalystService()
        
        if not service.enabled:
            logger.warning("AI Analyst is disabled")
            return
        
        service.run_scheduler()
    except Exception as e:
        logger.error(f"AI Analyst scheduler error: {e}", exc_info=True)


def run_telegram_command_bot():
    """Run Telegram Command Bot polling"""
    try:
        logger.info("Starting Telegram Command Bot thread...")
        
        # Import here to avoid circular dependencies
        from telegram_command_service import TelegramCommandBot
        
        bot = TelegramCommandBot()
        bot.run()
    except Exception as e:
        logger.error(f"Telegram Command Bot error: {e}", exc_info=True)


def main():
    """Main entry point - runs both services in parallel"""
    logger.info("=" * 70)
    logger.info("AI Analyst Combined Service Starting...")
    logger.info("Services: Daily Summaries + Telegram /ask_ai Commands")
    logger.info("=" * 70)
    
    # Create threads for both services
    ai_analyst_thread = threading.Thread(
        target=run_ai_analyst_scheduler,
        name="AIAnalystScheduler",
        daemon=True
    )
    
    telegram_bot_thread = threading.Thread(
        target=run_telegram_command_bot,
        name="TelegramCommandBot",
        daemon=True
    )
    
    # Start both threads
    ai_analyst_thread.start()
    telegram_bot_thread.start()
    
    logger.info("Both services started successfully")
    logger.info("- AI Analyst: Scheduled daily summaries at 18:59 UTC")
    logger.info("- Telegram Bot: Polling for /ask_ai commands")
    
    # Keep main thread alive
    try:
        ai_analyst_thread.join()
        telegram_bot_thread.join()
    except KeyboardInterrupt:
        logger.info("Services stopped by user")


if __name__ == '__main__':
    main()
