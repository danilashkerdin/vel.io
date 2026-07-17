#!/bin/bash
# One-time setup: install git hooks + frontend dependencies

set -e

echo "🔧 Installing git hooks..."
git config core.hooksPath .githooks
echo "   hooksPath set to .githooks/"

if [ -d frontend/node_modules ]; then
    echo "✅ Frontend dependencies already installed"
else
    echo "📦 Installing frontend dependencies (ESLint)..."
    cd frontend && npm install && cd ..
    echo "✅ Frontend dependencies installed"
fi

echo ""
echo "🎉 Done! Hooks are active:"
echo "   - pre-commit: ESLint check on staged JS files"
echo "   - pre-push:   blocks direct pushes to main"
echo ""
echo "   To bypass hooks: git commit --no-verify / git push --no-verify"