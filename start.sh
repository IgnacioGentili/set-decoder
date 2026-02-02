#!/bin/bash

echo "🎧 Set Decoder - Starting..."
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg not found. Install it with: brew install ffmpeg"
    exit 1
fi

echo "✅ ffmpeg found"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r backend/requirements.txt --break-system-packages -q

echo "✅ Dependencies installed"
echo ""

# Start backend in background
echo "🚀 Starting backend server on http://localhost:8000..."
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "🌐 Starting frontend on http://localhost:3000..."
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd ..

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Set Decoder is running!"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "   Press Ctrl+C to stop"
echo "═══════════════════════════════════════════════════"
echo ""

# Handle shutdown
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# Keep running
wait
