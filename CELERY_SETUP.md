# 🔄 Celery Integration - Automated News Processing

This document explains the new Celery-powered background processing features added to the French News Discussion app.

## ✨ What's New

### **Automated News Processing**
- 🕐 **Every 30 seconds**: Fetches fresh BBC news automatically
- 🔤 **Smart Translation**: Converts to French B1 level for learners
- 🧮 **Vector Embeddings**: Creates semantic search capabilities
- 📊 **Real-time Monitoring**: Track processing with Celery Flower

### **Background Tasks**
- **News Fetching**: Runs every 30 seconds (configurable)
- **Health Checks**: System monitoring every 5 minutes
- **Cleanup**: Daily removal of articles older than 30 days
- **Retry Logic**: Automatic retries with exponential backoff

## 🚀 Quick Start

### **With Docker (Recommended)**
```bash
# Start all services including Celery
docker-compose up -d

# Monitor tasks at:
# - API: http://localhost:8000
# - Flower: http://localhost:5555
```

### **Local Development**
```bash
# Install dependencies
uv sync

# Start Celery services
./scripts/start_celery.sh

# In another terminal, start FastAPI
uv run python main.py
```

## 📊 Monitoring & Control

### **Celery Flower Dashboard**
Visit `http://localhost:5555` for real-time monitoring:
- Active tasks and workers
- Task history and results
- Performance metrics
- Queue management

### **API Endpoints**
- `GET /celery/status` - Worker and task status
- `POST /celery/trigger-news-fetch` - Manual news processing
- `GET /celery/task/{task_id}` - Track specific tasks

### **Example Usage**
```bash
# Trigger manual news fetch
curl -X POST "http://localhost:8000/celery/trigger-news-fetch?limit=10"

# Check task status
curl "http://localhost:8000/celery/task/{task_id}"

# View worker status
curl "http://localhost:8000/celery/status"
```

## 🛠️ Configuration

### **Scheduling (src/celery_app.py)**
```python
beat_schedule={
    'fetch-news-every-30-seconds': {
        'task': 'src.tasks.news_tasks.fetch_and_process_news',
        'schedule': 30.0,  # Change frequency here
    },
    # ... other tasks
}
```

### **Environment Variables**
```bash
REDIS_URL=redis://localhost:6379/0  # Redis connection
OPENAI_API_KEY=your_key_here        # For translations
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │  Celery Beat    │
│                 │    │                 │    │   (Scheduler)   │
│ - Chat API      │    │ - News Tasks    │    │                 │
│ - Status API    │    │ - Translation   │    │ - Every 30s     │
│ - Trigger Tasks │    │ - Embeddings    │    │ - Daily Cleanup │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │      Redis      │
                    │   (Message      │
                    │    Broker)      │
                    └─────────────────┘
```

## 📝 Task Details

### **News Processing Task**
- **Frequency**: Every 30 seconds
- **Function**: Fetch BBC news, translate, create embeddings, store
- **Retry**: 3 attempts with exponential backoff
- **Queue**: `news_processing`

### **Maintenance Tasks**
- **Health Check**: Every 5 minutes
- **Cleanup**: Daily at 3 AM
- **Queue**: `maintenance`

## 🎯 Benefits

1. **🔄 Always Fresh Content**: News updates automatically
2. **⚡ Better Performance**: Background processing doesn't block API
3. **🔧 Fault Tolerance**: Automatic retries and error handling
4. **📊 Observability**: Full monitoring and logging
5. **🎛️ Control**: Manual triggers and real-time status

## 🆕 Language Learning Features

The automated processing ensures:
- **Fresh B1 Content**: New articles translated to learner level
- **Better Conversations**: More relevant content for chat
- **Consistent Quality**: Standardized translation process
- **Real-time Updates**: Always current news topics

## 🔧 Development Tips

- Monitor logs: `docker-compose logs -f celery-worker`
- Restart workers: `docker-compose restart celery-worker`
- Scale workers: `docker-compose up --scale celery-worker=3`
- Debug tasks: Use Flower's task inspection features

## 🎉 What's Next

Future Celery integrations could include:
- User progress tracking
- Personalized content recommendations
- Email notifications
- Advanced analytics
- Multi-language support

---

**The French News Discussion app now runs 24/7, continuously updating with fresh content for an optimal language learning experience!** 🇫🇷✨
