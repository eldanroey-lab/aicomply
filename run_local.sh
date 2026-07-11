#!/bin/bash
# ─────────────────────────────────────────────────────────────
# AiComply — Local Run Script
# Usage: bash run_local.sh
# ─────────────────────────────────────────────────────────────
set -e

echo "🚀 AiComply Local Setup"
echo "========================"

# 1. Python version check
python3 --version | grep -qE "3\.(10|11|12)" || { echo "❌ Python 3.10+ required"; exit 1; }
echo "✅ Python version OK"

# 2. Virtual env
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "✅ Created virtualenv"
fi
source venv/bin/activate

# 3. Install deps
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# 4. .env setup
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  Created .env from example — edit DATABASE_URL and SECRET_KEY before continuing"
  echo "   Press Enter when ready..."
  read
fi

# 5. Create tables
python3 -m app.startup
echo "✅ Database tables ready"

# 6. Run
echo ""
echo "🟢 Starting server at http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
