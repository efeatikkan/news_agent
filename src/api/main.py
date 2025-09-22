from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import logging
from contextlib import asynccontextmanager

from src.services.conversation import FrenchNewsConversationAgent
from src.services.news_processor import news_processor
from src.database.client import db_client
from src.celery_app import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global conversation agent
conversation_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global conversation_agent
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    conversation_agent = FrenchNewsConversationAgent(openai_api_key)
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="French News Discussion API",
    description="API for discussing French news at B1 level using LangGraph and Celery",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class NewsSource(BaseModel):
    id: int
    title_fr: str
    url: str
    published_at: str

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    relevant_articles: List[str] = []
    sources_used: List[NewsSource] = []


class NewsProcessingRequest(BaseModel):
    limit: Optional[int] = 10


class NewsArticleResponse(BaseModel):
    id: str
    title: str
    title_fr: Optional[str]
    content: str
    content_fr: Optional[str]
    url: str
    published_at: str


@app.get("/")
async def root():
    return {
        "message": "French News Discussion API with Celery", 
        "status": "running",
        "endpoints": [
            "POST /chat - Start or continue a conversation",
            "GET /conversation/{conversation_id} - Get conversation history",
            "POST /process-news - Process daily news",
            "GET /news - Get recent news articles",
            "GET /celery/status - Get Celery worker status",
            "POST /celery/trigger-news-fetch - Manually trigger news fetching",
            "GET /celery/task/{task_id} - Get task status",
            "GET /health - Health check"
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Start or continue a conversation about French news"""
    if not conversation_agent:
        raise HTTPException(status_code=500, detail="Conversation agent not initialized")
    
    result = await conversation_agent.chat(
        message.message, 
        message.conversation_id
    )

    if result["relevant_articles"]:
        result["relevant_articles"] = result["relevant_articles"]["documents"][0]

    # Format sources for API response
    sources_formatted = []
    for source in result.get("sources_used", []):
        sources_formatted.append(NewsSource(
            id=source["id"],
            title_fr=source["title_fr"],
            url=source["url"],
            published_at=source["published_at"][:10] if source["published_at"] else ""
        ))
    
    result["sources_used"] = sources_formatted

    return ChatResponse(**result)



@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    try:
        if not conversation_agent:
            raise HTTPException(status_code=500, detail="Conversation agent not initialized")
        
        result = await conversation_agent.get_conversation_history(conversation_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-news")
async def process_news(
    request: NewsProcessingRequest, 
    background_tasks: BackgroundTasks
):
    """Process daily news articles"""
    try:
        # Run news processing in background
        background_tasks.add_task(
            news_processor.process_daily_news, 
            request.limit
        )
        
        return {
            "message": f"News processing started for {request.limit} articles",
            "status": "processing"
        }
    
    except Exception as e:
        logger.error(f"Process news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news")
async def get_recent_news(limit: int = 20):
    """Get recent news articles"""
    try:
        async with db_client:
            articles = await db_client.get_recent_news_articles(limit)
        
        return [
            {
                "id": article["id"],
                "title": article["title"],
                "title_fr": article["titleFr"],
                "url": article["url"],
                "published_at": article["publishedAt"].isoformat(),
                "content_preview": article["content"][:200] + "..." if len(article["content"]) > 200 else article["content"]
            }
            for article in articles
        ]
    
    except Exception as e:
        logger.error(f"Get news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news/{article_id}")
async def get_article(article_id: str):
    """Get a specific news article"""
    try:
        async with db_client:
            # We need to implement this method in the database client
            # For now, let's return an error
            raise HTTPException(status_code=501, detail="Not implemented yet")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get article error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        async with db_client:
            pass
        
        return {
            "status": "healthy",
            "database": "connected",
            "conversation_agent": "initialized" if conversation_agent else "not_initialized"
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Celery-related endpoints
@app.get("/celery/status")
async def celery_status():
    """Get Celery worker and task status"""
    try:
        # Get active tasks
        active_tasks = celery_app.control.inspect().active()
        
        # Get worker stats
        worker_stats = celery_app.control.inspect().stats()
        
        # Get scheduled tasks
        scheduled_tasks = celery_app.control.inspect().scheduled()
        
        return {
            "status": "running" if worker_stats else "no_workers",
            "active_tasks": active_tasks or {},
            "worker_stats": worker_stats or {},
            "scheduled_tasks": scheduled_tasks or {},
            "registered_tasks": list(celery_app.tasks.keys())
        }
        
    except Exception as e:
        logger.error(f"Celery status error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/celery/trigger-news-fetch")
async def trigger_manual_news_fetch(limit: int = 5):
    """Manually trigger news fetching task"""
    try:
        from src.tasks.news_tasks import fetch_and_process_news
        
        task = fetch_and_process_news.delay(limit)
        
        return {
            "message": f"News fetching task triggered with limit {limit}",
            "task_id": task.id,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Manual news fetch trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/celery/task/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific Celery task"""
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.ready() else None,
            "traceback": task_result.traceback if task_result.failed() else None
        }
        
    except Exception as e:
        logger.error(f"Task status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True,
        reload_dirs=["src"]
    )