#!/bin/bash
# Final GitHub push - bulletproof version

set -e

echo "🚀 FINAL GitHub Push - Bulletproof Version"
echo "==========================================="
echo ""

# Step 1: Remove only Git directories (NOT .gitignore!)
echo "🗑️  Step 1: Remove Git directories only..."
rm -rf .git .git_backup_* 2>/dev/null || true
echo "✅ Git directories removed"

# Step 2: Verify .gitignore exists
echo ""
echo "🔍 Step 2: Verify .gitignore exists..."
if [ ! -f ".gitignore" ]; then
    echo "❌ ERROR: .gitignore missing! Aborting."
    exit 1
fi
echo "✅ .gitignore verified"

# Step 3: Initialize fresh Git
echo ""
echo "🆕 Step 3: Initialize fresh Git repository..."
git init -b main
echo "✅ Git initialized"

# Step 4: Configure Git for low memory
echo ""
echo "⚙️  Step 4: Configure Git for low memory..."
git config pack.threads 1
git config pack.windowMemory 10m
git config pack.packSizeLimit 20m
git config pack.deltaCacheSize 10m
git config http.postBuffer 524288000
git config core.compression 0
echo "✅ Git configured"

# Step 5: Stage .gitignore first
echo ""
echo "🛡️  Step 5: Stage .gitignore..."
git add .gitignore
git commit -m "Add .gitignore protection"
echo "✅ .gitignore committed"

# Step 6: Stage all code (respecting .gitignore)
echo ""
echo "📝 Step 6: Stage source code..."
git add .

# Show what will be committed
echo ""
echo "📊 Files to commit:"
git status --short | wc -l
echo " files staged"

# Step 7: Create main commit
echo ""
echo "💾 Step 7: Create commit..."
git commit -m "🚀 Smart Money Futures Signal Bot

ML-based cryptocurrency futures auto-trading system

Features:
- Enhanced Formula v2 with Random Forest ML
- Smart Signal Cancellation (3-criteria pipeline)  
- BingX Auto-Trader with robust risk management
- Order Flow Indicators (Psychological Levels + BA Aggression)
- 9 parallel services (CVD, Liquidations, AI Analyst, etc.)
- 62.3% win rate on BUY signals (validated backtest)

Tech Stack: Python, Binance WebSocket, Coinalyze API, OpenAI GPT-4o-mini

Clean deployment - no historical data or large binaries included"

echo "✅ Commit created"

# Step 8: Check repository size
echo ""
echo "📊 Step 8: Repository size..."
REPO_SIZE=$(du -sh .git | awk '{print $1}')
echo "Size: $REPO_SIZE"

# Verify size is reasonable
SIZE_MB=$(du -sm .git | awk '{print $1}')
if [ "$SIZE_MB" -gt 500 ]; then
    echo "⚠️  WARNING: Repository is ${SIZE_MB}MB (expected <100MB)"
    echo "Large files may have been included. Check .gitignore!"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 9: Add GitHub remote
echo ""
echo "🔗 Step 9: Add GitHub remote..."
git remote add github https://github.com/ibg-sketch/smart-money-futures-bot.git
echo "✅ Remote added"

# Step 10: Push to GitHub
echo ""
echo "🚀 Step 10: Pushing to GitHub..."
echo ""

git push -u github main --force

echo ""
echo "================================================"
echo "✅ SUCCESS! Published to GitHub!"
echo "🔗 https://github.com/ibg-sketch/smart-money-futures-bot"
echo ""
echo "📊 Repository size: $REPO_SIZE"
echo "📝 Files committed: $(git ls-files | wc -l)"
echo "================================================"
