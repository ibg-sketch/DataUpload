#!/bin/bash
# Cleanup Git repository and push to GitHub

set -e

echo "🧹 Step 1: Remove large files from Git cache..."

# Remove cached large files
git rm -rf --cached .cache/ .pythonlibs/ .local/ .config/ 2>/dev/null || true
git rm --cached *.csv 2>/dev/null || true
git rm --cached data/*.csv 2>/dev/null || true
git rm --cached *.json 2>/dev/null || true
git rm --cached active_signals.json cvd_data.json 2>/dev/null || true

echo "✅ Large files removed from cache"

echo ""
echo "🔧 Step 2: Configure Git for low memory..."

# Configure Git for low memory usage
git config pack.threads 1
git config pack.windowMemory 50m
git config pack.packSizeLimit 50m
git config pack.deltaCacheSize 50m
git config http.postBuffer 524288000

echo "✅ Git configured for low memory"

echo ""
echo "🗜️  Step 3: Cleanup and repack repository..."

# Remove garbage
git prune
git gc --aggressive --prune=now

echo "✅ Repository cleaned"

echo ""
echo "💾 Step 4: Commit cleanup changes..."

git add .gitignore
git commit -m "🧹 Cleanup: Remove large files and update .gitignore

- Remove .cache/, .pythonlibs/ from repository
- Exclude all CSV/JSON data files
- Configure Git for low memory usage
- Reduce repository size from 6.2GB to manageable size" || echo "Nothing to commit"

echo ""
echo "📊 New repository size:"
du -sh .git
git count-objects -vH

echo ""
echo "🚀 Step 5: Push to GitHub..."

# Check if remote exists
if git remote | grep -q "^github$"; then
    echo "Remote 'github' already exists"
else
    echo "Adding remote 'github'..."
    git remote add github https://github.com/ibg-sketch/smart-money-futures-bot.git
fi

# Push with reduced memory
git push -u github main --force

echo ""
echo "✅ Successfully published to GitHub!"
echo "🔗 https://github.com/ibg-sketch/smart-money-futures-bot"
