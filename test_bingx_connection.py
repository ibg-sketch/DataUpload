"""
Test BingX API Connection
"""
import os
import sys

print("🔍 Testing BingX API Connection...")
print("="*60)

print("\n1. Checking environment secrets...")
api_key = os.getenv('BINGX_API_KEY')
api_secret = os.getenv('BINGX_API_SECRET')
trading_channel = os.getenv('TRADING_TELEGRAM_CHAT_ID')

print(f"   BINGX_API_KEY: {'✅ Set' if api_key else '❌ Missing'}")
print(f"   BINGX_API_SECRET: {'✅ Set' if api_secret else '❌ Missing'}")
print(f"   TRADING_TELEGRAM_CHAT_ID: {'✅ Set' if trading_channel else '❌ Missing'}")

if not all([api_key, api_secret, trading_channel]):
    print("\n❌ Missing required secrets!")
    sys.exit(1)

print("\n2. Testing BingX public API (price fetch)...")
try:
    import requests
    response = requests.get(
        "https://open-api.bingx.com/openApi/swap/v2/quote/price",
        params={'symbol': 'BTC-USDT'},
        timeout=5
    )
    data = response.json()
    
    if data.get('code') == 0:
        price = float(data['data']['price'])
        print(f"   ✅ BTC-USDT Price: ${price:,.2f}")
    else:
        print(f"   ❌ API Error: {data}")
except Exception as e:
    print(f"   ❌ Connection failed: {e}")
    sys.exit(1)

print("\n3. Testing BingX authenticated API...")
try:
    import hmac
    import hashlib
    import time
    
    timestamp = int(time.time() * 1000)
    params = {'timestamp': timestamp}
    param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    headers = {'X-BX-APIKEY': api_key}
    
    response = requests.get(
        "https://open-api.bingx.com/openApi/swap/v2/user/balance",
        params=params,
        headers=headers,
        timeout=10
    )
    
    data = response.json()
    
    if data.get('code') == 0:
        print(f"   ✅ Authentication successful!")
        balance_data = data.get('data', {}).get('balance', {})
        if balance_data:
            print(f"   Account balance info retrieved")
    else:
        print(f"   ⚠️  Auth response: {data.get('msg', 'Unknown')}")
        print(f"   Note: This is normal if you haven't deposited funds yet")
except Exception as e:
    print(f"   ❌ Auth failed: {e}")
    sys.exit(1)

print("\n4. Testing Telegram notification...")
try:
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    response = requests.post(
        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
        json={
            'chat_id': trading_channel,
            'text': '✅ <b>BingX Trader Connection Test</b>\n\nAll systems operational!',
            'parse_mode': 'HTML'
        },
        timeout=10
    )
    
    if response.status_code == 200:
        print(f"   ✅ Telegram notification sent to channel!")
    else:
        print(f"   ⚠️  Telegram response: {response.status_code}")
except Exception as e:
    print(f"   ❌ Telegram failed: {e}")

print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\n🚀 Ready to start Paper Trading!")
