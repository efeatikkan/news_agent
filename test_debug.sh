#!/bin/bash

# Simple test script for debugging LangGraph

echo "🚀 Starting LangGraph Debug Tests"
echo "================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create one with OPENAI_API_KEY"
    exit 1
fi

# Check if OpenAI API key is set
if grep -q "OPENAI_API_KEY=" .env; then
    echo "✅ OPENAI_API_KEY found in .env"
else
    echo "❌ OPENAI_API_KEY not found in .env"
    exit 1
fi

echo ""
echo "1. Running Python debug script..."
python3 debug_langgraph.py

echo ""
echo "2. Starting FastAPI server in background for API tests..."
cd /Users/efeatikkan/Documents/projects/news_discuss

# Start the server in background
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "📡 Server started with PID: $SERVER_PID"
echo "⏳ Waiting for server to start..."
sleep 5

echo ""
echo "3. Testing API endpoints..."

# Test health endpoint
echo "🔍 Testing /health endpoint..."
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo "🔍 Testing /debug/graph-visualization endpoint..."
curl -s http://localhost:8000/debug/graph-visualization | python3 -m json.tool

echo ""
echo "🔍 Testing chat endpoint..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Bonjour! Comment ça va?"}' | python3 -m json.tool

echo ""
echo "🔍 Testing debug executions endpoint..."
curl -s http://localhost:8000/debug/graph-executions | python3 -m json.tool

echo ""
echo "🛑 Stopping server..."
kill $SERVER_PID

echo ""
echo "✅ Debug tests completed!"
echo "📝 Check debug_langgraph.log for detailed logs"
