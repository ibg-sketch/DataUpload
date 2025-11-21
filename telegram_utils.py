import os, requests, time, json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
T=os.getenv('TELEGRAM_BOT_TOKEN');C=os.getenv('TELEGRAM_CHAT_ID');TC=os.getenv('TRADING_TELEGRAM_CHAT_ID');TT=os.getenv('TRADING_TELEGRAM_BOT_TOKEN')

# Enhanced logging for Telegram failures
TELEGRAM_FAILURE_LOG = 'telegram_failures.log'

def log_telegram_failure(error_type, payload_snippet, response_text, retry_attempt=0):
    """Log detailed Telegram API failure information"""
    try:
        with open(TELEGRAM_FAILURE_LOG, 'a') as f:
            log_entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error_type': error_type,
                'payload_snippet': payload_snippet[:200] if payload_snippet else '',
                'response': response_text[:500] if response_text else '',
                'retry_attempt': retry_attempt
            }
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f'[TELEGRAM LOG ERROR] Failed to write failure log: {e}')

def send_telegram_message(text, parse_mode='HTML', reply_to_message_id=None, max_retries=3):
    """
    Send a message to Telegram with retry logic and enhanced error logging.
    
    Args:
        text: Message text
        parse_mode: Parse mode (HTML or Markdown)
        reply_to_message_id: Optional message ID to reply to
        max_retries: Number of retry attempts (default 3)
    
    Returns:
        message_id if successful, None otherwise
    """
    if not T or not C:
        print('[TELEGRAM WARN] No Telegram credentials configured')
        return None
    
    u=f'https://api.telegram.org/bot{T}/sendMessage'
    payload = {
        'chat_id': C,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    # Add reply_to if specified
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            r=requests.post(u, json=payload, timeout=20)
            
            if r.status_code==200:
                # Success - return message_id
                try:
                    return r.json().get('result', {}).get('message_id')
                except:
                    print('[TELEGRAM WARN] Success but failed to parse message_id')
                    log_telegram_failure('parse_error', str(payload), r.text, attempt)
                    return None
            elif r.status_code==429:
                # Rate limit - extract retry_after from response
                try:
                    retry_after = r.json().get('parameters', {}).get('retry_after', 5)
                except:
                    retry_after = 5
                print(f'[TELEGRAM RATE LIMIT] Retry after {retry_after}s (attempt {attempt+1}/{max_retries})')
                log_telegram_failure('rate_limit', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
            else:
                # Other error
                print(f'[TELEGRAM ERROR] Status {r.status_code}: {r.text[:200]} (attempt {attempt+1}/{max_retries})')
                log_telegram_failure(f'http_{r.status_code}', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
        except requests.exceptions.Timeout:
            print(f'[TELEGRAM TIMEOUT] Request timed out (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('timeout', str(payload), 'Request timeout after 20s', attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f'[TELEGRAM EXCEPTION] {type(e).__name__}: {e} (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('exception', str(payload), str(e), attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    
    # All retries failed
    print(f'[TELEGRAM FAILED] All {max_retries} attempts failed')
    return None

def send_cancellation_message(symbol, original_message_id, reason="Confidence dropped below threshold"):
    """
    Send a cancellation message as a reply to the original signal.
    
    Args:
        symbol: Trading pair symbol
        original_message_id: Message ID to reply to
        reason: Reason for cancellation
    """
    text = f"⚠️ <b>SIGNAL CANCELLED</b>\n\n{symbol}\n\n{reason}\n\nMarket conditions no longer meet minimum criteria."
    return send_telegram_message(text, reply_to_message_id=original_message_id)

def send_cancellation_notification(signal_data, result_data, cancellation_reason, reply_to_message_id=None):
    """
    Send a detailed cancellation notification as a reply to the original signal.
    
    Args:
        signal_data: Original signal data dict (from active_signals.json)
        result_data: Result data from log_cancelled_signal
        cancellation_reason: Human-readable reason for cancellation
        reply_to_message_id: Message ID to reply to
    
    Returns:
        message_id if successful, None otherwise
    """
    symbol = signal_data['symbol']
    verdict = signal_data['verdict']
    confidence = signal_data['confidence']
    entry_price = signal_data['entry_price']
    final_price = result_data.get('final_price', entry_price)
    profit_pct = result_data.get('profit_pct', 0)
    duration_actual = result_data.get('duration_actual', 0)
    duration_planned = signal_data.get('duration_minutes', 0)
    
    # Direction emoji
    direction_emoji = "🟢" if verdict == "BUY" else "🔴"
    
    # Profit formatting
    profit_sign = "+" if profit_pct >= 0 else ""
    profit_emoji = "📈" if profit_pct > 0 else "📉"
    
    # Build message (English to match rest of bot)
    text = f"""❌ <b>SIGNAL CANCELLED</b>

{direction_emoji} <b>{symbol} {verdict}</b> ({confidence:.0f}%)

<b>Reason:</b> {cancellation_reason}

<b>Entry:</b> ${entry_price:,.2f}
<b>Current:</b> ${final_price:,.2f} ({profit_sign}{profit_pct:.2f}%)
<b>Duration:</b> {duration_actual} min of {duration_planned} min

{profit_emoji} <b>PnL:</b> {profit_sign}{profit_pct:.2f}%

⚠️ Position closed"""
    
    return send_telegram_message(text, reply_to_message_id=reply_to_message_id)

def send_ttl_expired_message(symbol, verdict, original_message_id, result, profit_pct, duration_minutes):
    """
    Send a TTL expiration message as a reply to the original signal.
    
    Args:
        symbol: Trading pair symbol
        verdict: Signal direction (BUY/SELL)
        original_message_id: Message ID to reply to
        result: Final result (WIN/LOSS)
        profit_pct: Profit percentage
        duration_minutes: Signal duration in minutes
    
    Returns:
        message_id if successful, None otherwise
    """
    # Determine result based on actual profit (not passed result parameter)
    if profit_pct > 0:
        result_emoji = "✅"
        result_text = "WIN"
    else:
        result_emoji = "❌"
        result_text = "LOSS"
    
    # Format profit
    profit_sign = "+" if profit_pct >= 0 else ""
    
    direction_emoji = "🟢" if verdict == "BUY" else "🔴"
    
    text = f"""⏱️ <b>TTL EXPIRED</b>

{direction_emoji} <b>{symbol} {verdict}</b>

{result_emoji} <b>{result_text}</b>
Profit: <b>{profit_sign}{profit_pct:.2f}%</b>
Duration: {duration_minutes} minutes

Signal time window has ended."""
    
    return send_telegram_message(text, reply_to_message_id=original_message_id)

def send_to_channel(text, channel_id, parse_mode='HTML', reply_to_message_id=None, max_retries=3):
    """
    Send a message to a specific Telegram channel.
    
    Args:
        text: Message text
        channel_id: Specific channel ID to send to
        parse_mode: Parse mode (HTML or Markdown)
        reply_to_message_id: Optional message ID to reply to
        max_retries: Number of retry attempts (default 3)
    
    Returns:
        message_id if successful, None otherwise
    """
    if not T or not channel_id:
        print('[TELEGRAM WARN] No Telegram credentials or channel ID configured')
        return None
    
    u=f'https://api.telegram.org/bot{T}/sendMessage'
    payload = {
        'chat_id': channel_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    
    for attempt in range(max_retries):
        try:
            r=requests.post(u, json=payload, timeout=20)
            
            if r.status_code==200:
                try:
                    return r.json().get('result', {}).get('message_id')
                except:
                    print('[TELEGRAM WARN] Success but failed to parse message_id')
                    log_telegram_failure('parse_error', str(payload), r.text, attempt)
                    return None
            elif r.status_code==429:
                try:
                    retry_after = r.json().get('parameters', {}).get('retry_after', 5)
                except:
                    retry_after = 5
                print(f'[TELEGRAM RATE LIMIT] Retry after {retry_after}s (attempt {attempt+1}/{max_retries})')
                log_telegram_failure('rate_limit', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
            else:
                print(f'[TELEGRAM ERROR] Status {r.status_code}: {r.text[:200]} (attempt {attempt+1}/{max_retries})')
                log_telegram_failure(f'http_{r.status_code}', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        except requests.exceptions.Timeout:
            print(f'[TELEGRAM TIMEOUT] Request timed out (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('timeout', str(payload), 'Request timeout after 20s', attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f'[TELEGRAM EXCEPTION] {type(e).__name__}: {e} (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('exception', str(payload), str(e), attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    
    print(f'[TELEGRAM FAILED] All {max_retries} attempts failed')
    return None

def send_to_trading_channel(text, channel_id, parse_mode='HTML', reply_to_message_id=None, max_retries=3):
    """
    Send a message to Trading Bot Telegram channel using Trading Bot token.
    
    Args:
        text: Message text
        channel_id: Specific channel ID to send to
        parse_mode: Parse mode (HTML or Markdown)
        reply_to_message_id: Optional message ID to reply to
        max_retries: Number of retry attempts (default 3)
    
    Returns:
        message_id if successful, None otherwise
    """
    if not TT or not channel_id:
        print('[TELEGRAM WARN] No Trading Bot credentials or channel ID configured')
        return None
    
    u=f'https://api.telegram.org/bot{TT}/sendMessage'
    payload = {
        'chat_id': channel_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    
    for attempt in range(max_retries):
        try:
            r=requests.post(u, json=payload, timeout=20)
            
            if r.status_code==200:
                try:
                    return r.json().get('result', {}).get('message_id')
                except:
                    print('[TELEGRAM WARN] Success but failed to parse message_id')
                    log_telegram_failure('parse_error', str(payload), r.text, attempt)
                    return None
            elif r.status_code==429:
                try:
                    retry_after = r.json().get('parameters', {}).get('retry_after', 5)
                except:
                    retry_after = 5
                print(f'[TELEGRAM RATE LIMIT] Retry after {retry_after}s (attempt {attempt+1}/{max_retries})')
                log_telegram_failure('rate_limit', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
            else:
                print(f'[TELEGRAM ERROR] Status {r.status_code}: {r.text[:200]} (attempt {attempt+1}/{max_retries})')
                log_telegram_failure(f'http_{r.status_code}', str(payload), r.text, attempt)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        except requests.exceptions.Timeout:
            print(f'[TELEGRAM TIMEOUT] Request timed out (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('timeout', str(payload), 'Request timeout after 20s', attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f'[TELEGRAM EXCEPTION] {type(e).__name__}: {e} (attempt {attempt+1}/{max_retries})')
            log_telegram_failure('exception', str(payload), str(e), attempt)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    
    print(f'[TELEGRAM FAILED] All {max_retries} attempts failed')
    return None
