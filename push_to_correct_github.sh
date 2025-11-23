#!/bin/bash
# Push to CORRECT GitHub repository

set -e

echo "🔧 Fixing GitHub remote and pushing code..."
echo ""

# Show current remote
echo "❌ Current (WRONG) remote:"
git remote -v | grep github

# Remove wrong remote
echo ""
echo "🗑️  Removing wrong remote..."
git remote remove github

# Add CORRECT remote
echo ""
echo "✅ Adding CORRECT remote..."
git remote add github https://github.com/ibg-sketch/smart-money-futures-bot.git

# Verify
echo ""
echo "✅ New remote:"
git remote -v | grep github

# Push to CORRECT repository
echo ""
echo "🚀 Pushing to CORRECT GitHub repository..."
echo "   Repository: smart-money-futures-bot"
echo ""

git push -u github main --force

echo ""
echo "================================================"
echo "✅ SUCCESS! Code pushed to CORRECT repository!"
echo "🔗 https://github.com/ibg-sketch/smart-money-futures-bot"
echo "================================================"
