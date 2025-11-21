"""
Setup Telegram Webhook
Registers webhook URL with Telegram Bot API
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DOMAIN = os.getenv('REPLIT_DOMAINS', '').split(',')[0].strip()

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not found")
    sys.exit(1)

if not DOMAIN:
    print("❌ REPLIT_DOMAINS not found")
    sys.exit(1)

webhook_url = f"https://{DOMAIN}/webhook"
api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

print("=" * 60)
print("Telegram Webhook Setup")
print("=" * 60)
print(f"Domain: {DOMAIN}")
print(f"Webhook URL: {webhook_url}")
print()

# Delete existing webhook first
print("🗑️  Deleting existing webhook...")
response = requests.post(f"{api_url}/deleteWebhook", timeout=10)
if response.status_code == 200:
    print("✅ Old webhook deleted")
else:
    print(f"⚠️  Delete failed: {response.status_code}")

# Set new webhook
print(f"📡 Setting new webhook: {webhook_url}")
response = requests.post(
    f"{api_url}/setWebhook",
    json={'url': webhook_url},
    timeout=10
)

if response.status_code == 200:
    result = response.json()
    if result.get('ok'):
        print("✅ Webhook registered successfully!")
        print(f"   URL: {webhook_url}")
    else:
        print(f"❌ Registration failed: {result}")
        sys.exit(1)
else:
    print(f"❌ HTTP error: {response.status_code}")
    sys.exit(1)

# Get webhook info to verify
print("\n📊 Verifying webhook status...")
response = requests.get(f"{api_url}/getWebhookInfo", timeout=10)
if response.status_code == 200:
    info = response.json().get('result', {})
    print(f"   URL: {info.get('url', 'N/A')}")
    print(f"   Pending updates: {info.get('pending_update_count', 0)}")
    print(f"   Last error: {info.get('last_error_message', 'None')}")
    print()
    print("✅ Webhook setup complete!")
else:
    print(f"⚠️  Verification failed: {response.status_code}")

print("=" * 60)
