#!/bin/bash
# Start Celery components for development

echo "🚀 Starting Celery services..."

# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "📡 Starting Redis..."
    redis-server --daemonize yes
fi

# Start Celery worker
echo "👷 Starting Celery worker..."
uv run celery -A src.celery_app worker --loglevel=info --queues=news_processing,maintenance &

# Start Celery beat
echo "⏰ Starting Celery beat scheduler..."
uv run celery -A src.celery_app beat --loglevel=info &

# Start Celery flower
echo "🌸 Starting Celery Flower monitoring..."
uv run celery -A src.celery_app flower --port=5555 &

echo "✅ All Celery services started!"
echo "📊 Flower monitoring: http://localhost:5555"
echo "🔄 News processing will run every 30 seconds"
echo ""
echo "To stop all services: pkill -f celery"
