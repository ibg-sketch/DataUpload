#!/bin/bash
# Push code to GitHub repository

set -e

echo "📦 Preparing to push code to GitHub..."

# Read repo info
REPO_URL=$(python3 -c "import json; print(json.load(open('.github_repo_info.json'))['clone_url'])")
REPO_HTML=$(python3 -c "import json; print(json.load(open('.github_repo_info.json'))['html_url'])")

echo "🔗 Repository URL: $REPO_HTML"

# Add GitHub as remote
echo "🔧 Adding GitHub remote..."
git remote remove github 2>/dev/null || true
git remote add github "$REPO_URL"

# Check current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📍 Current branch: $BRANCH"

# Stage all changes (respecting .gitignore)
echo "📝 Staging changes..."
git add -A

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No new changes to commit"
else
    echo "💾 Committing changes..."
    git commit -m "🚀 Initial commit: Smart Money Futures Signal Bot

- Enhanced Formula v2 with ML-based profit prediction
- Smart Signal Cancellation system
- BingX Auto-Trader integration
- 9 parallel services (CVD, Liquidations, AI Analyst, etc.)
- Order Flow Indicators (Psychological Levels, BA Aggression)
- Comprehensive backtesting results (62.3% WR for BUY signals)
- Professional README with setup instructions"
fi

# Push to GitHub
echo "🚀 Pushing to GitHub..."
git push -u github "$BRANCH" --force

echo ""
echo "✅ Successfully published to GitHub!"
echo "🔗 View at: $REPO_HTML"
echo ""
