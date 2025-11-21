#!/usr/bin/env python3
"""GitHub repository setup script"""

import os
import json
import requests
from datetime import datetime

def get_access_token():
    """Get GitHub access token from Replit Connectors"""
    hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
    x_replit_token = None
    
    if os.getenv('REPL_IDENTITY'):
        x_replit_token = f"repl {os.getenv('REPL_IDENTITY')}"
    elif os.getenv('WEB_REPL_RENEWAL'):
        x_replit_token = f"depl {os.getenv('WEB_REPL_RENEWAL')}"
    
    if not x_replit_token:
        raise Exception('X_REPLIT_TOKEN not found')
    
    response = requests.get(
        f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=github',
        headers={
            'Accept': 'application/json',
            'X_REPLIT_TOKEN': x_replit_token
        }
    )
    
    data = response.json()
    connection_settings = data.get('items', [{}])[0]
    
    access_token = (
        connection_settings.get('settings', {}).get('access_token') or
        connection_settings.get('settings', {}).get('oauth', {}).get('credentials', {}).get('access_token')
    )
    
    if not access_token:
        raise Exception('GitHub not connected properly')
    
    return access_token

def get_user_info(token):
    """Get GitHub user information"""
    response = requests.get(
        'https://api.github.com/user',
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    )
    return response.json()

def create_repository(token, repo_name, description, private=False):
    """Create a new GitHub repository"""
    response = requests.post(
        'https://api.github.com/user/repos',
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        },
        json={
            'name': repo_name,
            'description': description,
            'private': private,
            'auto_init': False
        }
    )
    
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Failed to create repo: {response.status_code} - {response.text}")

if __name__ == '__main__':
    try:
        # Get access token
        print("🔑 Getting GitHub access token...")
        token = get_access_token()
        
        # Get user info
        print("👤 Getting GitHub user info...")
        user = get_user_info(token)
        username = user.get('login')
        print(f"✅ Connected as: {username}")
        
        # Create repository
        repo_name = "smart-money-futures-bot"
        description = "🚀 Advanced cryptocurrency futures trading signal bot with ML-based analysis and automated trading"
        
        print(f"\n📦 Creating repository: {repo_name}...")
        repo = create_repository(token, repo_name, description, private=False)
        
        print(f"\n✅ Repository created successfully!")
        print(f"🔗 URL: {repo['html_url']}")
        print(f"📋 Clone URL: {repo['clone_url']}")
        print(f"🔐 SSH URL: {repo['ssh_url']}")
        
        # Save repo info
        with open('.github_repo_info.json', 'w') as f:
            json.dump({
                'username': username,
                'repo_name': repo_name,
                'html_url': repo['html_url'],
                'clone_url': repo['clone_url'],
                'ssh_url': repo['ssh_url'],
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
