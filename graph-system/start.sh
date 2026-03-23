#!/usr/bin/env bash
# start.sh — Start both backend and frontend in dev mode

set -e

echo "🔷 GraphIQ Startup"
echo "=================="

# Check for .env
if [ ! -f backend/.env ]; then
  echo "⚠️  No backend/.env found."
  echo "   Copy backend/.env.example → backend/.env and add your GEMINI_API_KEY"
  echo ""
  read -p "Continue anyway? (y/n): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# Install backend deps
echo ""
echo "📦 Installing backend dependencies..."
cd backend
pip install -r requirements.txt -q
cd ..

# Install frontend deps
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..

echo ""
echo "🚀 Starting servers..."
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""

# Start backend in background
cd backend && python main.py &
BACKEND_PID=$!

# Start frontend
cd ../frontend && npm start &
FRONTEND_PID=$!

# Wait and cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
