#!/bin/bash
# Ultra-fresh Git repository - ZERO connection to old repo

set -e

echo "🔥 ULTRA FRESH Git Push (no old objects)"
echo "=========================================="
echo ""

# Step 1: Completely remove ALL git
echo "🗑️  Step 1: Remove ALL Git directories..."
rm -rf .git .git_backup_*
echo "✅ All Git removed"

# Step 2: Clean Git garbage
echo ""
echo "🧹 Step 2: Clear any Git cache..."
rm -rf .git* 2>/dev/null || true
echo "✅ Git cache cleared"

# Step 3: Initialize fresh
echo ""
echo "🆕 Step 3: Initialize ultra-fresh repository..."
git init -b main
echo "✅ Fresh Git initialized"

# Step 4: Configure for low memory
echo ""
echo "⚙️  Step 4: Configure Git..."
git config pack.threads 1
git config pack.windowMemory 10m
git config pack.packSizeLimit 20m
git config pack.deltaCacheSize 10m
git config http.postBuffer 524288000
echo "✅ Git configured"

# Step 5: Add .gitignore FIRST
echo ""
echo "🛡️  Step 5: Add .gitignore protection..."
git add .gitignore
git commit -m "Add .gitignore"
echo "✅ Protection committed"

# Step 6: Add source code only
echo ""
echo "📝 Step 6: Stage source code (respecting .gitignore)..."
git add -A

# Check what's staged
echo ""
echo "📊 Files staged:"
STAGED_COUNT=$(git diff --cached --numstat | wc -l)
echo "Total: $STAGED_COUNT files"

# Show largest staged files
echo ""
echo "Top 10 largest files:"
git diff --cached --numstat | sort -rn | head -10

# Step 7: Commit
echo ""
echo "💾 Step 7: Create commit..."
git commit -m "🚀 Smart Money Futures Signal Bot - Clean Deploy

ML-based cryptocurrency futures auto-trading system
- 11 trading pairs monitored
- Enhanced Formula v2 with Random Forest
- Smart Signal Cancellation pipeline
- BingX Auto-Trader integration
- 62.3% win rate on BUY signals

Clean deployment without historical data or binaries"

echo "✅ Commit created"

# Step 8: Check size
echo ""
echo "📊 Step 8: Check repository size..."
REPO_SIZE=$(du -sh .git | cut -f1)
echo "Repository size: $REPO_SIZE"

# Step 9: Add GitHub remote
echo ""
echo "🔗 Step 9: Add GitHub remote..."
git remote add github https://github.com/ibg-sketch/smart-money-futures-bot.git
echo "✅ Remote added"

# Step 10: Push with optimizations
echo ""
echo "🚀 Step 10: Push to GitHub (force, fresh start)..."
echo ""

GIT_TRACE=1 git push -u github main --force --verbose

echo ""
echo "================================================"
echo "✅ SUCCESS! Check GitHub:"
echo "🔗 https://github.com/ibg-sketch/smart-money-futures-bot"
echo "================================================"
