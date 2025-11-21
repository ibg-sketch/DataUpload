"""
Telegram Command Service
Handles /ask_ai commands for interactive AI queries
VERSION: 1.0 - Initial implementation with rate limiting
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Telegram credentials
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'

# Rate limiting config
RATE_LIMIT_FILE = 'data/ask_ai_rate_limits.json'
MAX_REQUESTS_PER_HOUR = 10


class RateLimiter:
    """Per-user rate limiter with JSON persistence"""
    
    def __init__(self, max_requests: int = 10):
        self.max_requests = max_requests
        self.limits = self._load_limits()
    
    def _load_limits(self) -> Dict[str, list]:
        """Load rate limit data from file"""
        try:
            if os.path.exists(RATE_LIMIT_FILE):
                with open(RATE_LIMIT_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load rate limits: {e}")
        return {}
    
    def _save_limits(self):
        """Save rate limit data to file"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(RATE_LIMIT_FILE, 'w') as f:
                json.dump(self.limits, f)
        except Exception as e:
            logger.error(f"Failed to save rate limits: {e}")
    
    def check_and_record(self, user_id: str) -> tuple[bool, int]:
        """
        Check if user can make request and record it
        
        Returns:
            (allowed, remaining_requests)
        """
        now = time.time()
        hour_ago = now - 3600
        
        # Get user's request history
        if user_id not in self.limits:
            self.limits[user_id] = []
        
        # Clean old requests
        self.limits[user_id] = [
            timestamp for timestamp in self.limits[user_id]
            if timestamp > hour_ago
        ]
        
        # Check limit
        request_count = len(self.limits[user_id])
        if request_count >= self.max_requests:
            remaining = 0
            allowed = False
        else:
            # Record new request
            self.limits[user_id].append(now)
            self._save_limits()
            remaining = self.max_requests - request_count - 1
            allowed = True
        
        return allowed, remaining


class TelegramCommandBot:
    """Telegram bot for handling /ask_ai commands"""
    
    def __init__(self):
        if not BOT_TOKEN or not CHAT_ID:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        
        self.rate_limiter = RateLimiter(MAX_REQUESTS_PER_HOUR)
        self.offset = None
        
        # Import AI Analyst service
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from services.ai_analyst.runner import AIAnalystService
        
        try:
            self.ai_analyst = AIAnalystService()
            if not self.ai_analyst.enabled:
                raise ValueError("AI Analyst is disabled in config")
            logger.info("AI Analyst service loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Analyst: {e}")
            raise
    
    def get_updates(self) -> Optional[Dict]:
        """Fetch updates from Telegram"""
        try:
            params = {'timeout': 5}
            if self.offset:
                params['offset'] = self.offset
            
            response = requests.get(
                f'{API_URL}/getUpdates',
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"getUpdates failed: {response.status_code} - {response.text[:200]}")
                return None
        
        except Exception as e:
            logger.error(f"Error fetching updates: {e}")
            return None
    
    def send_message(self, chat_id: str, text: str, reply_to: Optional[int] = None) -> bool:
        """Send message to Telegram"""
        try:
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            if reply_to:
                payload['reply_to_message_id'] = reply_to
            
            response = requests.post(
                f'{API_URL}/sendMessage',
                json=payload,
                timeout=20
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def clear_webhook(self) -> bool:
        """Clear any existing webhook to enable getUpdates polling"""
        try:
            response = requests.post(
                f'{API_URL}/deleteWebhook',
                json={'drop_pending_updates': True},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("[INIT] Webhook cleared successfully")
                return True
            else:
                logger.warning(f"[INIT] Failed to clear webhook: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error clearing webhook: {e}")
            return False
    
    def handle_ask_ai_command(self, message: Dict):
        """Handle /ask_ai command"""
        chat_id = str(message['chat']['id'])
        user_id = str(message['from']['id'])
        username = message['from'].get('username', 'Unknown')
        message_id = message['message_id']
        
        text = message.get('text', '')
        
        # Extract question after /ask_ai
        if not text.startswith('/ask_ai'):
            return
        
        question = text[8:].strip()  # Remove '/ask_ai '
        
        if not question:
            self.send_message(
                chat_id,
                "❓ <b>Usage:</b> /ask_ai <your question>\n\n"
                "<b>Examples:</b>\n"
                "• /ask_ai Why did win rate drop last 3 days?\n"
                "• /ask_ai Which indicators work best for BTC?\n"
                "• /ask_ai How is VWAP sigma performing?",
                reply_to=message_id
            )
            return
        
        # Check rate limit
        allowed, remaining = self.rate_limiter.check_and_record(user_id)
        
        if not allowed:
            self.send_message(
                chat_id,
                "⏱ <b>Rate Limit Exceeded</b>\n\n"
                f"You've reached the limit of {MAX_REQUESTS_PER_HOUR} questions per hour.\n"
                "Please try again in a few minutes.",
                reply_to=message_id
            )
            logger.warning(f"Rate limit exceeded for user {username} ({user_id})")
            return
        
        logger.info(f"Processing /ask_ai from {username}: '{question}' ({remaining} requests remaining)")
        
        # Send "thinking" message
        self.send_message(
            chat_id,
            f"🤔 <i>Analyzing data...</i>\n\n"
            f"<b>Question:</b> {question}\n"
            f"<i>Requests remaining this hour: {remaining}</i>",
            reply_to=message_id
        )
        
        # Query AI Analyst
        try:
            result = self.ai_analyst.query_ai(
                question=question,
                user_id=user_id
            )
            
            if result['success']:
                # Format response
                response_text = f"🤖 <b>AI Analysis</b>\n\n{result['answer']}\n\n"
                response_text += f"<i>📊 Cost: ${result.get('cost_usd', 0):.4f} | Tokens: {result.get('tokens_total', 0)}</i>"
                
                self.send_message(chat_id, response_text, reply_to=message_id)
                logger.info(f"Successfully answered query for {username}")
            else:
                error_msg = result.get('error', 'Unknown error')
                self.send_message(
                    chat_id,
                    f"❌ <b>Error</b>\n\n{error_msg}\n\n"
                    "Please try rephrasing your question or contact support.",
                    reply_to=message_id
                )
                logger.error(f"AI query failed: {error_msg}")
        
        except Exception as e:
            logger.error(f"Exception in query_ai: {e}", exc_info=True)
            self.send_message(
                chat_id,
                "❌ <b>Internal Error</b>\n\n"
                "Failed to process your question. Please try again later.",
                reply_to=message_id
            )
    
    def handle_message(self, message: Dict):
        """Process incoming message"""
        text = message.get('text', '')
        
        if text.startswith('/ask_ai'):
            self.handle_ask_ai_command(message)
        elif text == '/help':
            chat_id = str(message['chat']['id'])
            message_id = message['message_id']
            self.send_message(
                chat_id,
                "🤖 <b>AI Query Bot - Help</b>\n\n"
                "<b>Command:</b> /ask_ai <question>\n\n"
                "<b>Rate Limit:</b> 10 questions per hour\n\n"
                "<b>Examples:</b>\n"
                "• /ask_ai Why did win rate drop?\n"
                "• /ask_ai Best indicators for BTCUSDT?\n"
                "• /ask_ai How effective is VWAP?\n\n"
                "<i>Ask me anything about formula effectiveness and trading performance!</i>",
                reply_to=message_id
            )
    
    def run(self):
        """Main polling loop"""
        logger.info("=" * 60)
        logger.info("Telegram Command Bot Starting...")
        logger.info(f"Rate Limit: {MAX_REQUESTS_PER_HOUR} requests/hour")
        logger.info(f"Bot Token: {BOT_TOKEN[:10]}... (len={len(BOT_TOKEN) if BOT_TOKEN else 0})")
        logger.info(f"Chat ID: {CHAT_ID}")
        logger.info("=" * 60)
        
        # Clear any existing webhook to avoid 409 conflict errors
        self.clear_webhook()
        
        poll_count = 0
        
        while True:
            try:
                poll_count += 1
                if poll_count % 10 == 1:  # Log every 10th poll
                    logger.info(f"[POLLING] Attempt #{poll_count}, offset={self.offset}")
                
                data = self.get_updates()
                
                if data is None:
                    logger.warning("[POLLING] getUpdates returned None")
                    time.sleep(5)
                    continue
                
                if not data.get('ok'):
                    logger.error(f"[POLLING] API error: {data}")
                    time.sleep(5)
                    continue
                
                result = data.get('result', [])
                if result:
                    logger.info(f"[POLLING] Received {len(result)} update(s)")
                
                for update in result:
                    # Update offset
                    self.offset = update['update_id'] + 1
                    
                    # Process message
                    if 'message' in update and 'text' in update['message']:
                        msg = update['message']
                        logger.info(f"[MSG] From chat {msg['chat']['id']}: {msg.get('text', '')[:50]}")
                        
                        # Only process messages from authorized chat
                        if str(msg['chat']['id']) == CHAT_ID:
                            logger.info(f"[MSG] Processing authorized message")
                            self.handle_message(msg)
                        else:
                            logger.warning(f"[MSG] Ignoring unauthorized chat {msg['chat']['id']}")
                
                # Small delay to avoid excessive polling
                time.sleep(1)
            
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)


def main():
    """Entry point"""
    try:
        bot = TelegramCommandBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
