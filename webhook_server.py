"""
Telegram Webhook Server for /ask_ai Commands
Receives updates from Telegram Bot API via webhook instead of polling
VERSION: 1.0 - Webhook implementation
"""

import os
import sys
import json
import logging
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_command_service import TelegramCommandBot, RateLimiter, CHAT_ID
from services.ai_analyst.runner import AIAnalystService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Global instances
rate_limiter = None
ai_analyst = None
bot_token = None

def init_services():
    """Initialize AI Analyst and rate limiter"""
    global rate_limiter, ai_analyst, bot_token
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    # Initialize rate limiter
    rate_limiter = RateLimiter(max_requests=10)
    logger.info("Rate limiter initialized (10 requests/hour)")
    
    # Initialize AI Analyst
    try:
        ai_analyst = AIAnalystService()
        if not ai_analyst.enabled:
            raise ValueError("AI Analyst is disabled in config")
        logger.info("✅ AI Analyst service loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AI Analyst: {e}")
        raise


def send_message(text: str, reply_to: int = None) -> bool:
    """Send message to Telegram"""
    import requests
    
    try:
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        payload = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }
        if reply_to:
            payload['reply_to_message_id'] = reply_to
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Message sent successfully")
            return True
        else:
            logger.error(f"❌ Failed to send message: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        return False


def handle_ask_ai_command(message: dict):
    """Process /ask_ai command from webhook update"""
    try:
        # Handle both private messages and channel posts
        if 'from' in message:
            user_id = str(message['from']['id'])
            username = message['from'].get('username', 'Unknown')
        else:
            user_id = str(message.get('sender_chat', {}).get('id', '0'))
            username = message.get('sender_chat', {}).get('title', 'Channel')
        
        message_id = message['message_id']
        text = message.get('text', '')
        
        # Extract question (remove /ask_ai prefix)
        question = text.replace('/ask_ai', '').strip()
        
        if not question:
            send_message(
                "⚠️ <b>Usage:</b> /ask_ai [your question]\n"
                "Example: /ask_ai Why is BTCUSDT win rate low?",
                reply_to=message_id
            )
            return
        
        # Rate limiting
        allowed, remaining = rate_limiter.check_and_record(user_id)
        
        if not allowed:
            send_message(
                "⏱ <b>Rate limit exceeded!</b>\n"
                "You can make 10 queries per hour. Please wait.",
                reply_to=message_id
            )
            logger.warning(f"[RATE LIMIT] User {username} ({user_id}) exceeded limit")
            return
        
        logger.info(f"[QUERY] User {username}: '{question}' ({remaining} remaining)")
        
        # Send "processing" message
        send_message(
            f"🤔 <b>Analyzing...</b>\n"
            f"Question: {question[:100]}{'...' if len(question) > 100 else ''}\n"
            f"⏱ This may take 10-30 seconds...",
            reply_to=message_id
        )
        
        # Process query with AI
        try:
            result = ai_analyst.process_interactive_query(question)
            
            if result and 'answer' in result:
                # Format response
                response = (
                    f"🤖 <b>AI Analysis</b>\n\n"
                    f"{result['answer']}\n\n"
                    f"<i>💰 Cost: ${result.get('cost_usd', 0):.5f} | "
                    f"📊 Tokens: {result.get('tokens_used', 0)}</i>"
                )
                
                send_message(response, reply_to=message_id)
                logger.info(f"✅ Query processed successfully (${result.get('cost_usd', 0):.5f})")
            else:
                send_message(
                    "❌ <b>Analysis failed</b>\n"
                    "The AI service encountered an error. Please try again.",
                    reply_to=message_id
                )
                logger.error(f"❌ AI returned invalid result: {result}")
                
        except Exception as e:
            send_message(
                f"❌ <b>Error:</b> {str(e)[:200]}\n"
                "Please try again or contact support.",
                reply_to=message_id
            )
            logger.error(f"❌ AI query failed: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"❌ Error handling /ask_ai command: {e}", exc_info=True)


@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = request.get_json()
        
        # DEBUG: Log full update
        logger.info(f"[DEBUG] Received update: {json.dumps(update, indent=2)}")
        
        if not update:
            logger.warning("⚠️ Received empty webhook update")
            return jsonify({'ok': True})
        
        # Extract message (support both private messages and channel posts)
        message = update.get('message') or update.get('channel_post')
        if not message:
            logger.warning(f"⚠️ No 'message' or 'channel_post' in update, keys: {list(update.keys())}")
            return jsonify({'ok': True})
        
        # Check if it's a command in our chat
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '')
        
        logger.info(f"[DEBUG] chat_id='{chat_id}', CHAT_ID='{CHAT_ID}', text='{text}'")
        
        if chat_id != CHAT_ID:
            logger.warning(f"⚠️ Ignoring message from different chat: {chat_id} (expected: {CHAT_ID})")
            return jsonify({'ok': True})
        
        # Handle /ask_ai command
        if text.startswith('/ask_ai'):
            logger.info(f"📨 Webhook received /ask_ai command")
            
            # Process in background thread to respond quickly
            threading.Thread(
                target=handle_ask_ai_command,
                args=(message,),
                daemon=True
            ).start()
        else:
            logger.info(f"⚠️ Text does not start with /ask_ai: '{text}'")
        
        return jsonify({'ok': True})
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'ai_analyst': ai_analyst.enabled if ai_analyst else False,
        'webhook': 'active'
    })


@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Telegram Webhook Server',
        'status': 'running',
        'endpoints': ['/webhook', '/health']
    })


def main():
    """Start webhook server"""
    logger.info("=" * 60)
    logger.info("Telegram Webhook Server Starting...")
    logger.info("=" * 60)
    
    # Initialize services
    init_services()
    
    # Get domain for webhook URL
    domain = os.getenv('REPLIT_DOMAINS', '').split(',')[0].strip()
    webhook_url = f"https://{domain}/webhook"
    
    logger.info(f"🌐 Webhook URL: {webhook_url}")
    logger.info(f"💬 Chat ID: {CHAT_ID}")
    logger.info(f"⚡ Rate Limit: 10 queries/hour")
    logger.info("=" * 60)
    
    # Start Flask server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()
