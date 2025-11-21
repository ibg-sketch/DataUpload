#!/bin/bash
# Create fresh Git repository and push to GitHub

set -e

echo "🔥 Creating FRESH Git repository (no history)..."
echo ""

# Backup old .git
echo "📦 Step 1: Backup old .git folder..."
if [ -d ".git" ]; then
    mv .git .git_backup_$(date +%Y%m%d_%H%M%S)
    echo "✅ Old .git backed up"
fi

# Initialize fresh repository
echo ""
echo "🆕 Step 2: Initialize fresh repository..."
git init
git branch -M main
echo "✅ Fresh Git initialized"

# Add .gitignore first
echo ""
echo "🛡️  Step 3: Add .gitignore..."
git add .gitignore
git commit -m "Add .gitignore"
echo "✅ .gitignore committed"

# Add all files (respecting .gitignore)
echo ""
echo "📝 Step 4: Add all source code..."
git add -A
echo ""
echo "📊 Files to be committed:"
git status --short | head -20
echo "..."
echo ""

# Count files
FILE_COUNT=$(git status --short | wc -l)
echo "Total files: $FILE_COUNT"

# Commit
git commit -m "🚀 Initial commit: Smart Money Futures Signal Bot

Enhanced Formula v2 ML-based cryptocurrency futures auto-trading system
Monitors 11 trading pairs with smart signal cancellation pipeline

Features:
- ML-based profit prediction (Random Forest Regressor)  
- Smart Signal Cancellation (3 criteria)
- BingX Auto-Trader integration
- Order Flow Indicators (Psychological Levels, BA Aggression)
- 9 parallel services (CVD, Liquidations, AI Analyst, etc.)
- Comprehensive backtesting: 62.3% WR for BUY signals

Tech Stack: Python, Binance WebSocket, Coinalyze API, OpenAI API"

echo "✅ Initial commit created"

# Check repository size
echo ""
echo "📊 Step 5: Check new repository size..."
du -sh .git
git count-objects -vH

# Add GitHub remote
echo ""
echo "🔗 Step 6: Add GitHub remote..."
git remote add github https://github.com/ibg-sketch/smart-money-futures-bot.git
echo "✅ Remote added"

# Push to GitHub (force to overwrite)
echo ""
echo "🚀 Step 7: Push to GitHub (fresh start)..."
git push -u github main --force

echo ""
echo "================================================"
echo "✅ SUCCESS! Published to GitHub!"
echo "🔗 https://github.com/ibg-sketch/smart-money-futures-bot"
echo ""
echo "📊 Old repo size: 6.2GB (1879 commits)"
echo "📊 New repo size: ~50MB (1 commit)"
echo "================================================"
